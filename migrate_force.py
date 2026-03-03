"""
Script de migração forçada - limpa tabelas existentes e migra tudo do SQLite
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
    tables = [(row[0],) for row in cursor.fetchall()]
    conn.close()
    return tables


def get_table_info(table_name):
    """Obter schema e dados da tabela"""
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Schema
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    
    # Dados
    try:
        cursor.execute(f"SELECT * FROM {table_name};")
        rows = cursor.fetchall()
        data = [dict(row) for row in rows]
    except:
        data = []
    
    conn.close()
    return columns, data


def infer_pg_type(col):
    """Inferir tipo PostgreSQL"""
    cid, name, sqlite_type, notnull, default, pk = col
    sqlite_type = (sqlite_type or "TEXT").upper()
    name_lower = name.lower()
    
    if pk == 1:
        if name_lower == "id" and sqlite_type == "INTEGER":
            return "SERIAL PRIMARY KEY"
        return "TEXT PRIMARY KEY"
    
    if name_lower in ("is_active", "is_executed", "is_vip", "enabled", "deleted"):
        return "BOOLEAN"
    
    if name_lower in ("created_at", "updated_at", "deleted_at", "completed_at", "started_at"):
        return "TIMESTAMP"
    
    if name_lower in ("date",) or "_date" in name_lower:
        return "DATE"
    
    if name_lower in ("amount", "balance", "price", "payout", "profit", "confidence", "confluence"):
        return "NUMERIC"
    
    if "json" in name_lower or name_lower in ("indicators", "settings", "config"):
        return "JSONB"
    
    if "INT" in sqlite_type:
        return "INTEGER"
    if "REAL" in sqlite_type or "FLOA" in sqlite_type:
        return "NUMERIC"
    if "BOOL" in sqlite_type:
        return "BOOLEAN"
    
    return "TEXT"


def convert_for_pg(value, pg_type):
    """Converter valor para PostgreSQL"""
    if value is None:
        return None
    
    if pg_type == "BOOLEAN":
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes")
        return bool(int(value)) if str(value).isdigit() else bool(value)
    
    if pg_type == "JSONB":
        if isinstance(value, str):
            try:
                return json.loads(value)
            except:
                return value
        return value
    
    if pg_type == "TIMESTAMP" and isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    
    if pg_type == "DATE" and isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except:
            return value
    
    return value


async def migrate():
    print("=" * 60)
    print("MIGRAÇÃO FORÇADA - SQLite → PostgreSQL")
    print("=" * 60)
    
    # Conectar
    conn = await asyncpg.connect(POSTGRES_URL)
    
    # Obter tabelas
    tables = get_sqlite_tables()
    print(f"\nTabelas a migrar: {len(tables)}")
    
    total_records = 0
    
    for (table_name,) in tables:
        columns, data = get_table_info(table_name)
        
        if not data:
            print(f"  - {table_name}: vazia")
            continue
        
        col_names = [c[1] for c in columns]
        pg_types = {c[1]: infer_pg_type(c) for c in columns}
        
        # Criar tabela se não existir
        col_defs = []
        for c in columns:
            name = c[1]
            pg_type = infer_pg_type(c)
            col_defs.append(f'"{name}" {pg_type}')
        
        create_sql = f"CREATE TABLE IF NOT EXISTS {table_name} ({', '.join(col_defs)})"
        try:
            await conn.execute(create_sql)
        except Exception as e:
            print(f"  ✗ {table_name} - erro ao criar: {e}")
            continue
        
        # Limpar tabela existente
        try:
            await conn.execute(f"TRUNCATE TABLE {table_name} CASCADE")
        except:
            pass
        
        # Inserir dados
        placeholders = ", ".join([f"${i+1}" for i in range(len(col_names))])
        col_list = ", ".join([f'"{c}"' for c in col_names])
        insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"
        
        inserted = 0
        errors = 0
        
        for row in data:
            values = []
            for col_name in col_names:
                pg_type = pg_types.get(col_name, "TEXT")
                value = row.get(col_name)
                values.append(convert_for_pg(value, pg_type))
            
            try:
                await conn.execute(insert_sql, *values)
                inserted += 1
            except Exception as e:
                errors += 1
                if errors <= 3:  # Mostrar apenas primeiros erros
                    print(f"    Erro em {table_name}: {e}")
        
        total_records += inserted
        
        if errors > 0:
            print(f"  ⚠ {table_name}: {inserted}/{len(data)} registros ({errors} erros)")
        else:
            print(f"  ✓ {table_name}: {inserted}/{len(data)} registros")
    
    await conn.close()
    
    print(f"\n{'=' * 60}")
    print(f"MIGRAÇÃO CONCLUÍDA - Total: {total_records} registros")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(migrate())
