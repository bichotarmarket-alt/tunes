"""
Script de migração: SQLite → PostgreSQL
Copia todos os dados do banco SQLite antigo para o PostgreSQL novo
"""

import asyncio
import sqlite3
import asyncpg
from datetime import datetime, date
from decimal import Decimal
import json
import uuid

# Configuração
SQLITE_DB = "autotrade.db"
POSTGRES_URL = "postgresql://postgres:root@localhost:5432/tunestrade"


def get_sqlite_tables():
    """Obter lista de tabelas do SQLite"""
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables


def get_sqlite_schema(table_name):
    """Obter schema de uma tabela SQLite"""
    conn = sqlite3.connect(SQLITE_DB)
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name});")
    columns = cursor.fetchall()
    conn.close()
    return columns


def convert_value(value, col_type):
    """Converter valor do SQLite para formato PostgreSQL"""
    if value is None:
        return None

    col_type = col_type.upper() if col_type else "TEXT"

    # Converter booleanos (SQLite armazena como 0/1)
    if col_type == "BOOLEAN":
        return bool(value) if value is not None else None

    # Converter JSON
    if col_type in ("JSON", "JSONB"):
        if isinstance(value, str):
            return json.loads(value)
        return value

    # Converter UUID
    if col_type == "UUID":
        if isinstance(value, str):
            return value
        return str(value)

    # Converter Decimal/Numeric
    if col_type in ("DECIMAL", "NUMERIC", "REAL", "FLOAT"):
        return float(value) if value is not None else None

    # Converter datas
    if col_type in ("DATE", "DATETIME", "TIMESTAMP"):
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace('Z', '+00:00'))
            except:
                return value
        return value

    # Converter INTEGER
    if col_type == "INTEGER":
        return int(value) if value is not None else None

    return value


def get_sqlite_data(table_name):
    """Obter todos os dados de uma tabela SQLite"""
    conn = sqlite3.connect(SQLITE_DB)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute(f"SELECT * FROM {table_name};")
        rows = cursor.fetchall()
        data = [dict(row) for row in rows]
    except Exception as e:
        print(f"  Erro ao ler tabela {table_name}: {e}")
        data = []

    conn.close()
    return data


def infer_postgres_type(sqlite_type, col_name):
    """Inferir tipo PostgreSQL baseado no tipo SQLite e nome da coluna"""
    sqlite_type = (sqlite_type or "TEXT").upper()
    col_name = col_name.lower()

    # Tipos especiais baseados no nome da coluna
    if "id" in col_name and ("uuid" in col_name or col_name.endswith("_id")):
        return "UUID"
    if col_name in ("id", "uuid"):
        return "UUID"
    if "created_at" in col_name or "updated_at" in col_name or "deleted_at" in col_name:
        return "TIMESTAMP WITH TIME ZONE"
    if col_name.endswith("_at") or col_name in ("timestamp", "datetime"):
        return "TIMESTAMP WITH TIME ZONE"
    if "date" in col_name and col_name not in ("updated", "created"):
        return "DATE"
    if col_name in ("is_active", "is_executed", "is_vip", "is_admin", "is_demo", "enabled", "deleted"):
        return "BOOLEAN"
    if col_name in ("amount", "balance", "price", "payout", "profit", "loss", "value"):
        return "NUMERIC(20, 8)"
    if "json" in col_name or "indicators" in col_name or "settings" in col_name or "config" in col_name:
        return "JSONB"

    # Mapear tipos SQLite para PostgreSQL
    if "INT" in sqlite_type:
        return "INTEGER"
    if "REAL" in sqlite_type or "FLOA" in sqlite_type or "DOUB" in sqlite_type:
        return "NUMERIC(20, 8)"
    if "BOOL" in sqlite_type:
        return "BOOLEAN"
    if "BLOB" in sqlite_type:
        return "BYTEA"
    if "NUMERIC" in sqlite_type or "DECIMAL" in sqlite_type:
        return "NUMERIC(20, 8)"

    return "TEXT"


def create_table_sql(table_name, columns):
    """Gerar SQL CREATE TABLE para PostgreSQL"""
    col_defs = []
    primary_key = None

    for col in columns:
        # SQLite PRAGMA: cid, name, type, notnull, dflt_value, pk
        cid, name, sqlite_type, notnull, default, pk = col

        pg_type = infer_postgres_type(sqlite_type, name)

        # Mapear nomes de tipos específicos
        if sqlite_type:
            sqlite_type_upper = sqlite_type.upper()
            if "VARCHAR" in sqlite_type_upper:
                pg_type = sqlite_type  # Manter VARCHAR(n)
            elif "CHAR" in sqlite_type_upper:
                pg_type = sqlite_type
            elif "NUMERIC" in sqlite_type_upper or "DECIMAL" in sqlite_type_upper:
                pg_type = sqlite_type

        # Coluna ID/UUID → PRIMARY KEY
        if pk == 1 or name.lower() in ("id", "uuid"):
            primary_key = name
            col_def = f'"{name}" {pg_type} PRIMARY KEY'
        else:
            col_def = f'"{name}" {pg_type}'

        # NOT NULL
        if notnull:
            col_def += " NOT NULL"

        # DEFAULT
        if default is not None:
            if isinstance(default, str):
                # Remover aspas se for um literal de string
                if default.startswith("'") and default.endswith("'"):
                    default = default[1:-1]
                if default.lower() in ("current_timestamp", "now()", "datetime('now')"):
                    col_def += " DEFAULT CURRENT_TIMESTAMP"
                elif default.lower() in ("true", "1"):
                    col_def += " DEFAULT TRUE"
                elif default.lower() in ("false", "0"):
                    col_def += " DEFAULT FALSE"
                elif default.lower() == "null":
                    pass  # NULL é default implícito
                else:
                    col_def += f" DEFAULT '{default}'"
            else:
                col_def += f" DEFAULT {default}"

        col_defs.append(col_def)

    sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n    " + ",\n    ".join(col_defs) + "\n);"

    return sql


async def migrate_table(pg_pool, table_name, sqlite_data, columns):
    """Migrar dados de uma tabela do SQLite para PostgreSQL"""
    if not sqlite_data:
        print(f"  Tabela {table_name}: vazia")
        return 0

    # Obter nomes das colunas
    col_names = [col[1] for col in columns]  # col[1] = nome da coluna

    # Construir INSERT
    placeholders = ", ".join([f"${i+1}" for i in range(len(col_names))])
    col_list = ", ".join([f'"{c}"' for c in col_names])

    insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

    count = 0
    async with pg_pool.acquire() as pg_conn:
        for row in sqlite_data:
            # Converter valores
            values = []
            for i, col in enumerate(columns):
                col_name = col[1]
                col_type = col[2] if len(col) > 2 else None
                value = row.get(col_name)

                # Converter valor
                if value is not None:
                    # Converter booleanos (SQLite usa 0/1)
                    if col_name.lower() in ("is_active", "is_executed", "is_vip", "is_admin", "is_demo", "enabled", "deleted"):
                        value = bool(int(value)) if str(value).isdigit() else bool(value)
                    # Converter JSON
                    elif isinstance(value, str) and (value.startswith("{") or value.startswith("[")):
                        try:
                            value = json.loads(value)
                        except:
                            pass
                    # Converter UUID
                    elif col_name.lower() in ("id", "uuid") or col_name.lower().endswith("_id"):
                        if isinstance(value, str):
                            try:
                                uuid.UUID(value)
                                value = value
                            except:
                                pass

                values.append(value)

            try:
                await pg_conn.execute(insert_sql, *values)
                count += 1
            except Exception as e:
                print(f"  Erro ao inserir em {table_name}: {e}")
                print(f"  Valores: {values}")
                # Continuar com próxima linha

    return count


async def main():
    print("=" * 60)
    print("MIGRAÇÃO: SQLite → PostgreSQL")
    print("=" * 60)

    # Verificar se SQLite existe
    import os
    if not os.path.exists(SQLITE_DB):
        print(f"ERRO: Banco SQLite '{SQLITE_DB}' não encontrado!")
        return

    print(f"\n1. Conectando ao SQLite: {SQLITE_DB}")
    tables = get_sqlite_tables()
    print(f"   Encontradas {len(tables)} tabelas: {', '.join(tables)}")

    print(f"\n2. Conectando ao PostgreSQL...")
    try:
        pg_pool = await asyncpg.create_pool(POSTGRES_URL, min_size=1, max_size=5)
        print("   Conectado!")
    except Exception as e:
        print(f"   ERRO: {e}")
        return

    # Criar extensão UUID se necessário
    async with pg_pool.acquire() as conn:
        try:
            await conn.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
            print("   Extensão UUID habilitada")
        except:
            pass

    print(f"\n3. Criando tabelas no PostgreSQL...")
    for table_name in tables:
        columns = get_sqlite_schema(table_name)
        create_sql = create_table_sql(table_name, columns)

        async with pg_pool.acquire() as conn:
            try:
                await conn.execute(create_sql)
                print(f"   ✓ {table_name}")
            except Exception as e:
                print(f"   ✗ {table_name}: {e}")

    print(f"\n4. Migrando dados...")
    total_rows = 0
    for table_name in tables:
        columns = get_sqlite_schema(table_name)
        data = get_sqlite_data(table_name)

        if data:
            count = await migrate_table(pg_pool, table_name, data, columns)
            total_rows += count
            print(f"   ✓ {table_name}: {count}/{len(data)} registros")
        else:
            print(f"   - {table_name}: vazia")

    await pg_pool.close()

    print(f"\n{'=' * 60}")
    print(f"MIGRAÇÃO CONCLUÍDA!")
    print(f"Total de registros migrados: {total_rows}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    asyncio.run(main())
