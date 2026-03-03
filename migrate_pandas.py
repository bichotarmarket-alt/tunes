"""
Migração usando pandas - converte tipos automaticamente
"""

import asyncio
import sqlite3
import asyncpg
import json
from datetime import datetime, date

SQLITE_DB = "autotrade.db"
POSTGRES_URL = "postgresql://postgres:root@localhost:5432/tunestrade"


def get_sqlite_tables():
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables


def get_data(table_name):
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns_info = cursor.fetchall()
    
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    data = []
    for row in rows:
        row_dict = {}
        for i, col_info in enumerate(columns_info):
            col_name = col_info[1]
            col_type = col_info[2]
            value = row[i]
            
            # Converter booleanos (0/1 -> False/True)
            if col_name in ('is_active', 'is_executed', 'is_vip', 'is_admin', 'is_demo', 'enabled', 'deleted'):
                value = bool(value) if value is not None else None
            
            # Converter JSON strings para dicts
            if col_name in ('indicators', 'settings', 'config', 'params', 'metadata', 'results', 'data'):
                if isinstance(value, str):
                    try:
                        value = json.loads(value)
                    except:
                        pass
            
            # Converter enums para lowercase
            if col_name == 'account_type':
                value = str(value).lower() if value else None
            
            # Converter IDs int para str
            if col_name == 'id' and isinstance(value, int):
                value = str(value)
            
            row_dict[col_name] = value
        
        data.append(row_dict)
    
    columns = [c[1] for c in columns_info]
    conn.close()
    return data, columns


async def create_tables_from_sqlite(pg_conn):
    """Criar tabelas baseado no schema SQLite"""
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    tables = get_sqlite_tables()
    
    for table_name in tables:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        
        col_defs = []
        for col in columns:
            cid, name, sqlite_type, notnull, default, pk = col
            sqlite_type = (sqlite_type or 'TEXT').upper()
            
            # Definir tipo PostgreSQL
            if name in ('id', 'uuid') or name.endswith('_id'):
                if sqlite_type == 'INTEGER' and name == 'id':
                    pg_type = 'SERIAL PRIMARY KEY' if pk else 'INTEGER'
                else:
                    pg_type = 'TEXT'
            elif name in ('is_active', 'is_executed', 'is_vip', 'enabled', 'deleted'):
                pg_type = 'BOOLEAN'
            elif name in ('created_at', 'updated_at', 'deleted_at', 'completed_at', 'started_at', 'timestamp'):
                pg_type = 'TIMESTAMP'
            elif 'date' in name and name not in ('updated', 'created'):
                pg_type = 'DATE'
            elif name in ('amount', 'balance', 'price', 'payout', 'profit'):
                pg_type = 'NUMERIC'
            elif name in ('indicators', 'settings', 'config'):
                pg_type = 'JSONB'
            elif 'INT' in sqlite_type:
                pg_type = 'INTEGER'
            elif 'REAL' in sqlite_type or 'FLOA' in sqlite_type:
                pg_type = 'NUMERIC'
            elif 'BOOL' in sqlite_type:
                pg_type = 'BOOLEAN'
            else:
                pg_type = 'TEXT'
            
            col_def = f'"{name}" {pg_type}'
            if notnull and not pk:
                col_def += ' NOT NULL'
            col_defs.append(col_def)
        
        # Criar tabela
        create_sql = f"DROP TABLE IF EXISTS {table_name} CASCADE; CREATE TABLE {table_name} ({', '.join(col_defs)})"
        try:
            await pg_conn.execute(create_sql)
            print(f"  ✓ Criada tabela {table_name}")
        except Exception as e:
            print(f"  ✗ Erro em {table_name}: {e}")
    
    conn.close()


async def migrate():
    print("=" * 60)
    print("MIGRAÇÃO PANDAS - SQLite → PostgreSQL")
    print("=" * 60)
    
    conn = await asyncpg.connect(POSTGRES_URL)
    
    # Criar tabelas
    print("\n1. Criando tabelas...")
    await create_tables_from_sqlite(conn)
    
    # Migrar dados
    print("\n2. Migrando dados...")
    tables = get_sqlite_tables()
    total = 0
    
    for table_name in tables:
        data, columns = get_data(table_name)
        
        if not data:
            print(f"  - {table_name}: vazia")
            continue
        
        # Inserir em batches
        batch_size = 100
        inserted = 0
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            
            for row in batch:
                try:
                    # Construir INSERT
                    cols = ', '.join([f'"{k}"' for k in row.keys()])
                    vals = list(row.values())
                    placeholders = ', '.join([f'${i+1}' for i in range(len(vals))])
                    
                    sql = f"INSERT INTO {table_name} ({cols}) VALUES ({placeholders})"
                    await conn.execute(sql, *vals)
                    inserted += 1
                except Exception as e:
                    if inserted == 0:
                        print(f"    Erro: {e}")
                    break
        
        total += inserted
        print(f"  ✓ {table_name}: {inserted}/{len(data)} registros")
    
    await conn.close()
    
    print(f"\n{'=' * 60}")
    print(f"MIGRAÇÃO CONCLUÍDA - Total: {total} registros")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(migrate())
