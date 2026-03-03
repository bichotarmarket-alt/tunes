"""
Migração usando SQLAlchemy - garante compatibilidade de tipos
"""
import asyncio
import sqlite3
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, inspect
from core.database import Base
from core.config import settings

# Importar todos os models para registrar no Base
import importlib
import os
import glob

# Conectar ao SQLite
SQLITE_DB = "autotrade.db"
POSTGRES_URL = "postgresql+asyncpg://postgres:root@localhost:5432/tunestrade"


def get_sqlite_data(table_name):
    """Obter dados do SQLite como dicionários"""
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns_info = cursor.fetchall()
    col_names = [c[1] for c in columns_info]
    
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    data = []
    for row in rows:
        row_dict = {}
        for i, col_name in enumerate(col_names):
            value = row[i]
            
            # Converter JSON strings
            if isinstance(value, str) and (value.startswith('{') or value.startswith('[')):
                try:
                    value = json.loads(value)
                except:
                    pass
            
            # Converter booleans
            if col_name in ('is_active', 'is_executed', 'is_vip', 'enabled', 'deleted'):
                value = bool(value) if value is not None else None
            
            # Converter enums para lowercase
            if col_name == 'account_type' and value:
                value = str(value).lower()
            
            row_dict[col_name] = value
        
        data.append(row_dict)
    
    conn.close()
    return data, col_names


async def migrate():
    print("=" * 60)
    print("MIGRAÇÃO SQLALCHEMY - SQLite → PostgreSQL")
    print("=" * 60)
    
    # Criar engine PostgreSQL
    engine = create_async_engine(POSTGRES_URL)
    
    # Dropar e recriar todas as tabelas
    async with engine.begin() as conn:
        print("\n1. Limpando banco PostgreSQL...")
        await conn.run_sync(Base.metadata.drop_all)
        print("   Tabelas removidas")
        
        print("\n2. Criando tabelas...")
        await conn.run_sync(Base.metadata.create_all)
        print("   Tabelas criadas com sucesso")
    
    # Obter lista de tabelas
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    print(f"\n3. Migrando dados de {len(tables)} tabelas...")
    total = 0
    
    # Criar session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    for table_name in tables:
        data, columns = get_sqlite_data(table_name)
        
        if not data:
            print(f"  - {table_name}: vazia")
            continue
        
        # Mapear para model SQLAlchemy
        model_class = None
        for mapper in Base.registry.mappers:
            if mapper.class_.__tablename__ == table_name:
                model_class = mapper.class_
                break
        
        if not model_class:
            print(f"  ⚠ {table_name}: model não encontrado, pulando")
            continue
        
        async with async_session() as session:
            try:
                # Desabilitar triggers de FK temporariamente
                await session.execute(f"ALTER TABLE {table_name} DISABLE TRIGGER ALL")
            except:
                pass
            
            inserted = 0
            for row_data in data:
                try:
                    obj = model_class(**row_data)
                    session.add(obj)
                    inserted += 1
                except Exception as e:
                    if inserted == 0:
                        print(f"    Erro: {e}")
            
            await session.commit()
            total += inserted
            print(f"  ✓ {table_name}: {inserted}/{len(data)} registros")
    
    await engine.dispose()
    
    print(f"\n{'=' * 60}")
    print(f"MIGRAÇÃO CONCLUÍDA - Total: {total} registros")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(migrate())
