"""
Migração CSV - Export SQLite para CSV, depois importa no PostgreSQL
"""

import sqlite3
import csv
import os
import asyncio
import asyncpg
from datetime import datetime, date

SQLITE_DB = "autotrade.db"
POSTGRES_URL = "postgresql://postgres:root@localhost:5432/tunestrade"
CSV_DIR = "migration_csv"


def export_sqlite_to_csv():
    """Exporta todas as tabelas do SQLite para CSV"""
    os.makedirs(CSV_DIR, exist_ok=True)
    
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    
    # Obter lista de tabelas
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
    tables = [row[0] for row in cursor.fetchall()]
    
    print(f"Exportando {len(tables)} tabelas para CSV...")
    
    for table in tables:
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        
        if not rows:
            print(f"  - {table}: vazia")
            continue
        
        # Obter nomes das colunas
        cursor.execute(f"PRAGMA table_info({table})")
        columns = [col[1] for col in cursor.fetchall()]
        
        # Exportar para CSV
        csv_file = os.path.join(CSV_DIR, f"{table}.csv")
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(columns)
            writer.writerows(rows)
        
        print(f"  ✓ {table}: {len(rows)} registros")
    
    conn.close()
    return tables


def get_pg_type(sqlite_type, col_name):
    """Converte tipo SQLite para PostgreSQL"""
    sqlite_type = (sqlite_type or 'TEXT').upper()
    name_lower = col_name.lower()
    
    # Detectar tipo baseado no nome
    if name_lower in ('is_active', 'is_executed', 'is_vip', 'is_admin', 'is_demo', 'enabled', 'deleted'):
        return 'BOOLEAN'
    
    if name_lower in ('created_at', 'updated_at', 'deleted_at', 'completed_at', 'started_at', 'timestamp', 'executed_at'):
        return 'TIMESTAMP'
    
    if name_lower in ('date',) or '_date' in name_lower:
        return 'DATE'
    
    if name_lower in ('amount', 'balance', 'price', 'payout', 'profit', 'loss', 'confidence', 'confluence'):
        return 'NUMERIC'
    
    if 'json' in name_lower or name_lower in ('indicators', 'settings', 'config', 'params'):
        return 'JSONB'
    
    if 'INT' in sqlite_type:
        if name_lower in ('id', 'uuid') or name_lower.endswith('_id'):
            return 'TEXT'  # IDs como texto
        return 'INTEGER'
    
    if 'REAL' in sqlite_type or 'FLOA' in sqlite_type:
        return 'NUMERIC'
    
    if 'BOOL' in sqlite_type:
        return 'BOOLEAN'
    
    return 'TEXT'


async def import_csv_to_postgres(tables):
    """Importa CSVs no PostgreSQL"""
    conn = await asyncpg.connect(POSTGRES_URL)
    
    # Desabilitar foreign key checks
    await conn.execute("SET session_replication_role = 'replica';")
    
    sqlite_conn = sqlite3.connect(SQLITE_DB)
    sqlite_cursor = sqlite_conn.cursor()
    
    total = 0
    
    for table in tables:
        csv_file = os.path.join(CSV_DIR, f"{table}.csv")
        if not os.path.exists(csv_file):
            continue
        
        # Obter schema do SQLite
        sqlite_cursor.execute(f"PRAGMA table_info({table})")
        columns_info = sqlite_cursor.fetchall()
        
        if not columns_info:
            continue
        
        # Dropar e recriar tabela
        await conn.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        
        # Criar tabela com tipos corretos
        col_defs = []
        for col in columns_info:
            cid, name, sqlite_type, notnull, default, pk = col
            pg_type = get_pg_type(sqlite_type, name)
            col_defs.append(f'"{name}" {pg_type}')
        
        create_sql = f"CREATE TABLE {table} ({', '.join(col_defs)})"
        await conn.execute(create_sql)
        
        # Ler CSV
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            
            inserted = 0
            errors = 0
            
            for row in reader:
                # Converter valores
                converted = []
                for i, (col_info, value) in enumerate(zip(columns_info, row)):
                    cid, name, sqlite_type, notnull, default, pk = col_info
                    pg_type = get_pg_type(sqlite_type, name)
                    
                    if value is None or value == '':
                        converted.append(None)
                        continue
                    
                    # Converter booleanos
                    if pg_type == 'BOOLEAN':
                        converted.append(value.lower() in ('true', '1', 'yes'))
                    # Converter JSON
                    elif pg_type == 'JSONB':
                        converted.append(value)
                    # Converter timestamps
                    elif pg_type == 'TIMESTAMP':
                        if value and value.strip():
                            try:
                                converted.append(datetime.fromisoformat(value.replace(' ', 'T')))
                            except:
                                converted.append(None)
                        else:
                            converted.append(None)
                    # Converter dates
                    elif pg_type == 'DATE':
                        if value and value.strip():
                            try:
                                converted.append(date.fromisoformat(value))
                            except:
                                converted.append(None)
                        else:
                            converted.append(None)
                    # Converter numeric
                    elif pg_type == 'NUMERIC':
                        converted.append(float(value) if value else None)
                    # Converter integer
                    elif pg_type == 'INTEGER':
                        converted.append(int(value) if value else None)
                    else:
                        converted.append(value)
                
                # Inserir
                placeholders = ', '.join([f'${i+1}' for i in range(len(converted))])
                col_list = ', '.join([f'"{h}"' for h in headers])
                
                try:
                    await conn.execute(
                        f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})",
                        *converted
                    )
                    inserted += 1
                except Exception as e:
                    errors += 1
                    if errors <= 2:
                        print(f"    Erro: {e}")
        
        total += inserted
        status = "✓" if errors == 0 else "⚠"
        print(f"  {status} {table}: {inserted} registros")
    
    # Reabilitar foreign key checks
    await conn.execute("SET session_replication_role = 'origin';")
    
    sqlite_conn.close()
    await conn.close()
    
    return total


async def main():
    print("=" * 60)
    print("MIGRAÇÃO CSV - SQLite → PostgreSQL")
    print("=" * 60)
    
    print("\n1. Exportando SQLite para CSV...")
    tables = export_sqlite_to_csv()
    
    print("\n2. Importando CSV para PostgreSQL...")
    total = await import_csv_to_postgres(tables)
    
    print(f"\n{'=' * 60}")
    print(f"MIGRAÇÃO CONCLUÍDA - Total: {total} registros")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
