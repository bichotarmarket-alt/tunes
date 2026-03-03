"""
Migração FINAL - SQLite → PostgreSQL
Ordena tabelas por dependência e converte tipos corretamente
"""

import asyncio
import sqlite3
import asyncpg
import json
from datetime import datetime, date

SQLITE_DB = "autotrade.db"
POSTGRES_URL = "postgresql://postgres:root@localhost:5432/tunestrade"

# Ordem de migração (tabelas sem FK primeiro)
MIGRATION_ORDER = [
    "alembic_version",
    "users",           # independente
    "assets",          # independente
    "indicators",      # independente
    "strategies",      # independente (mas tem user_id FK opcional)
    "aggregation_job_log",  # independente
    "daily_signal_summary", # independente
    "accounts",        # FK: users
    "autotrade_configs",  # FK: users
    "monitoring_accounts",  # FK: users
    "signals",         # FK: strategies, assets
    "strategy_indicators",  # FK: strategies, indicators
    "strategy_performance_snapshots",  # FK: strategies
    "trades",          # FK: strategies, accounts
]


def get_sqlite_data(table_name):
    """Obter todos os dados da tabela SQLite"""
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description]
        data = []
        for row in rows:
            row_dict = {}
            for i, col in enumerate(columns):
                row_dict[col] = row[i]
            data.append(row_dict)
    except Exception as e:
        print(f"  Erro ao ler {table_name}: {e}")
        data = []
    
    conn.close()
    return data, columns


def convert_value(value, col_name, table_name):
    """Converter valor para PostgreSQL"""
    if value is None:
        return None
    
    # Booleanos
    if col_name in ("is_active", "is_executed", "is_vip", "is_admin", "is_demo", "enabled", "deleted", "is_read"):
        if isinstance(value, str):
            return value.lower() in ("true", "1", "yes", "on")
        return bool(int(value)) if str(value).isdigit() else bool(value)
    
    # Enums - lowercase para PostgreSQL
    if col_name == "account_type" and table_name == "monitoring_accounts":
        return str(value).lower() if value else None
    
    if col_name in ("role", "status", "trade_result", "signal_type", "asset_type"):
        return str(value).lower() if value else None
    
    # Timestamps - converter string para datetime
    if col_name in ("created_at", "updated_at", "deleted_at", "completed_at", "started_at", 
                    "executed_at", "timestamp", "last_used", "last_login", "expires_at"):
        if isinstance(value, str):
            try:
                # Tentar formato ISO
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except:
                try:
                    # Tentar formato comum
                    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f")
                except:
                    try:
                        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
                    except:
                        return value
        return value
    
    # Dates
    if col_name in ("date", "start_date", "end_date") or col_name.endswith("_date"):
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except:
                return value
        return value
    
    # JSON - converter lista/dict para string JSON
    if col_name in ("indicators", "settings", "config", "params", "metadata", "results", "data"):
        if isinstance(value, (list, dict)):
            return json.dumps(value)
        return value
    
    # UUIDs como string
    if col_name in ("id", "uuid") or col_name.endswith("_id"):
        if isinstance(value, int):
            return str(value)
        return str(value) if value else None
    
    return value


async def migrate():
    print("=" * 60)
    print("MIGRAÇÃO FINAL - SQLite → PostgreSQL")
    print("=" * 60)
    
    conn = await asyncpg.connect(POSTGRES_URL)
    
    # Desabilitar foreign key checks
    await conn.execute("SET session_replication_role = 'replica';")
    
    total = 0
    
    for table_name in MIGRATION_ORDER:
        data, columns = get_sqlite_data(table_name)
        
        if not data:
            print(f"  - {table_name}: vazia")
            continue
        
        # Limpar tabela
        try:
            await conn.execute(f"TRUNCATE TABLE {table_name} CASCADE")
        except:
            pass
        
        # Inserir dados
        placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])
        col_list = ", ".join([f'"{c}"' for c in columns])
        insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"
        
        inserted = 0
        errors = 0
        
        for row in data:
            values = [convert_value(row.get(col), col, table_name) for col in columns]
            
            try:
                await conn.execute(insert_sql, *values)
                inserted += 1
            except Exception as e:
                errors += 1
                if errors <= 2:
                    print(f"    Erro: {e}")
        
        total += inserted
        status = "✓" if errors == 0 else "⚠"
        print(f"  {status} {table_name}: {inserted}/{len(data)} registros")
    
    # Reabilitar foreign key checks
    await conn.execute("SET session_replication_role = 'origin';")
    
    await conn.close()
    
    print(f"\n{'=' * 60}")
    print(f"MIGRAÇÃO CONCLUÍDA - Total: {total} registros")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(migrate())
