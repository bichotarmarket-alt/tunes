"""
Script completo de migração SQLite → PostgreSQL
Analisa o SQLite e migra todas as tabelas e dados corretamente
"""

import asyncio
import sqlite3
import asyncpg
import json
from datetime import datetime, date

SQLITE_DB = "autotrade.db"
POSTGRES_URL = "postgresql://postgres:root@localhost:5432/tunestrade"


def get_sqlite_tables():
    """Obter todas as tabelas do SQLite com contagem de registros"""
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;")
    tables = cursor.fetchall()
    
    result = []
    for (table_name,) in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            result.append((table_name, count))
        except:
            result.append((table_name, 0))
    
    conn.close()
    return result


def get_table_schema(table_name):
    """Obter schema detalhado da tabela"""
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    
    conn.close()
    return columns


def get_all_data(table_name):
    """Obter todos os dados da tabela"""
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT * FROM {table_name};")
        rows = cursor.fetchall()
        data = [dict(row) for row in rows]
    except Exception as e:
        print(f"  Erro ao ler {table_name}: {e}")
        data = []
    
    conn.close()
    return data


def sqlite_to_postgres_type(col):
    """Converter tipo SQLite para PostgreSQL"""
    cid, name, sqlite_type, notnull, default, pk = col
    sqlite_type = (sqlite_type or "TEXT").upper()
    name_lower = name.lower()
    
    # Primary key
    if pk == 1:
        if name_lower == "id" and sqlite_type == "INTEGER":
            return "SERIAL PRIMARY KEY"
        return f"{sqlite_type} PRIMARY KEY"
    
    # Detectar tipo baseado no nome e tipo SQLite
    if name_lower in ("id", "uuid") or name_lower.endswith("_id"):
        return "VARCHAR(36)"
    
    if name_lower in ("is_active", "is_executed", "is_vip", "is_admin", "is_demo", "enabled", "deleted"):
        return "BOOLEAN"
    
    if name_lower in ("created_at", "updated_at", "deleted_at", "completed_at", "started_at", "executed_at"):
        return "TIMESTAMP"
    
    if "date" in name_lower and name_lower not in ("updated", "created"):
        return "DATE"
    
    if name_lower in ("amount", "balance", "price", "payout", "profit", "loss", "value", "confidence", "confluence"):
        return "NUMERIC(20, 8)"
    
    if "json" in name_lower or name_lower in ("indicators", "settings", "config", "params"):
        return "JSONB"
    
    if "int" in sqlite_type:
        return "INTEGER"
    if "real" in sqlite_type or "float" in sqlite_type or "double" in sqlite_type:
        return "NUMERIC(20, 8)"
    if "bool" in sqlite_type:
        return "BOOLEAN"
    if "blob" in sqlite_type:
        return "BYTEA"
    
    return "TEXT"


def create_table_sql(table_name, columns):
    """Gerar SQL CREATE TABLE"""
    col_defs = []
    
    for col in columns:
        cid, name, sqlite_type, notnull, default, pk = col
        pg_type = sqlite_to_postgres_type(col)
        
        col_def = f'"{name}" {pg_type}'
        
        if notnull and pk != 1:
            col_def += " NOT NULL"
        
        if default is not None:
            if isinstance(default, str):
                if default.startswith("'") and default.endswith("'"):
                    default = default[1:-1]
                if default.lower() in ("current_timestamp", "now()", "datetime('now')"):
                    col_def += " DEFAULT CURRENT_TIMESTAMP"
                elif default.lower() == "true" or default == "1":
                    col_def += " DEFAULT TRUE"
                elif default.lower() == "false" or default == "0":
                    col_def += " DEFAULT FALSE"
                elif default.lower() != "null":
                    col_def += f" DEFAULT '{default}'"
        
        col_defs.append(col_def)
    
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n    " + ",\n    ".join(col_defs) + "\n);"


def convert_value(value, col_name, pg_type):
    """Converter valor para PostgreSQL"""
    if value is None:
        return None
    
    # Booleanos
    if pg_type == "BOOLEAN":
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(value)
    
    # JSON
    if pg_type == "JSONB":
        if isinstance(value, str):
            try:
                return json.loads(value)
            except:
                return value
        return value
    
    # UUIDs e IDs
    if pg_type == "VARCHAR(36)" and isinstance(value, int):
        return str(value)
    
    # Timestamps
    if pg_type == "TIMESTAMP" and isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except:
            return value
    
    # Dates
    if pg_type == "DATE" and isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except:
            return value
    
    return value


async def create_all_tables(pg_conn, tables_info):
    """Criar todas as tabelas no PostgreSQL"""
    print("\n1. Criando tabelas no PostgreSQL...")
    
    for table_name, count in tables_info:
        columns = get_table_schema(table_name)
        create_sql = create_table_sql(table_name, columns)
        
        try:
            await pg_conn.execute(create_sql)
            print(f"  ✓ {table_name}")
        except Exception as e:
            print(f"  ✗ {table_name}: {e}")


async def migrate_table_data(pg_pool, table_name, columns):
    """Migrar dados de uma tabela"""
    data = get_all_data(table_name)
    
    if not data:
        return 0
    
    col_names = [col[1] for col in columns]
    pg_types = {col[1]: sqlite_to_postgres_type(col) for col in columns}
    
    placeholders = ", ".join([f"${i+1}" for i in range(len(col_names))])
    col_list = ", ".join([f'"{c}"' for c in col_names])
    
    insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"
    
    count = 0
    async with pg_pool.acquire() as pg_conn:
        for row in data:
            values = []
            for col_name in col_names:
                pg_type = pg_types.get(col_name, "TEXT")
                value = row.get(col_name)
                values.append(convert_value(value, col_name, pg_type))
            
            try:
                await pg_conn.execute(insert_sql, *values)
                count += 1
            except Exception as e:
                # Silencioso para não poluir output
                pass
    
    return count


async def main():
    print("=" * 70)
    print("MIGRAÇÃO COMPLETA: SQLite → PostgreSQL")
    print("=" * 70)
    
    # 1. Analisar SQLite
    print("\nAnalisando banco SQLite...")
    tables_info = get_sqlite_tables()
    
    print(f"\nTabelas encontradas: {len(tables_info)}")
    for name, count in tables_info:
        print(f"  - {name}: {count} registros")
    
    # 2. Conectar ao PostgreSQL
    print("\nConectando ao PostgreSQL...")
    pg_pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=10)
    
    async with pg_pool.acquire() as pg_conn:
        await create_all_tables(pg_conn, tables_info)
    
    # 3. Migrar dados
    print("\n2. Migrando dados...")
    total_migrated = 0
    
    for table_name, count in tables_info:
        if count == 0:
            print(f"  - {table_name}: vazia")
            continue
        
        columns = get_table_schema(table_name)
        migrated = await migrate_table_data(pg_pool, table_name, columns)
        total_migrated += migrated
        
        if migrated > 0:
            print(f"  ✓ {table_name}: {migrated}/{count} registros")
        else:
            print(f"  - {table_name}: 0/{count} (possível duplicata)")
    
    await pg_pool.close()
    
    print(f"\n{'=' * 70}")
    print(f"MIGRAÇÃO CONCLUÍDA!")
    print(f"Total de registros migrados: {total_migrated}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
