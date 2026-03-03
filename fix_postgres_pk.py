"""
Script para corrigir constraint PRIMARY KEY no PostgreSQL

Este script remove duplicatas e adiciona PRIMARY KEY na tabela daily_signal_summary
"""
import asyncio
import asyncpg
import os
from dotenv import load_dotenv

# Carregar variáveis do .env
load_dotenv()


async def fix_database():
    """Corrigir constraint PRIMARY KEY no PostgreSQL"""
    
    # Obter URL do banco de dados do .env
    db_url = os.getenv('DATABASE_URL', 'postgresql+asyncpg://postgres:root@localhost:5432/tunestrade')
    
    # Converter postgresql+asyncpg para formato asyncpg
    # De: postgresql+asyncpg://user:pass@host:port/db
    # Para: postgres://user:pass@host:port/db
    connection_url = db_url.replace('postgresql+asyncpg://', 'postgresql://')
    
    print(f"[FIX DB] Conectando ao PostgreSQL...")
    print(f"[FIX DB] URL: {connection_url.replace('://', '://***:***@')}")
    
    conn = await asyncpg.connect(connection_url)
    
    try:
        print("[FIX DB] Verificando duplicatas...")
        
        # Verificar duplicatas
        duplicates = await conn.fetch("""
            SELECT id, COUNT(*) as count 
            FROM daily_signal_summary 
            GROUP BY id 
            HAVING COUNT(*) > 1
        """)
        
        if duplicates:
            print(f"[FIX DB] Encontradas {len(duplicates)} IDs duplicados")
            for row in duplicates:
                print(f"  - ID: {row['id']} ({row['count']} registros)")
            
            # Remover duplicatas mantendo o mais recente (menor ctid = primeiro inserido)
            print("[FIX DB] Removendo duplicatas...")
            await conn.execute("""
                DELETE FROM daily_signal_summary a
                USING (
                    SELECT MIN(ctid) as min_ctid, id
                    FROM daily_signal_summary
                    GROUP BY id
                    HAVING COUNT(*) > 1
                ) b
                WHERE a.id = b.id AND a.ctid != b.min_ctid
            """)
            print("[FIX DB] Duplicatas removidas")
        else:
            print("[FIX DB] Nenhuma duplicata encontrada")
        
        # Verificar se PRIMARY KEY já existe
        print("[FIX DB] Verificando constraint PRIMARY KEY...")
        pk_exists = await conn.fetchval("""
            SELECT COUNT(*) 
            FROM information_schema.table_constraints 
            WHERE table_name = 'daily_signal_summary' 
            AND constraint_type = 'PRIMARY KEY'
        """)
        
        if pk_exists:
            print("[FIX DB] PRIMARY KEY já existe")
        else:
            print("[FIX DB] Adicionando PRIMARY KEY...")
            await conn.execute("""
                ALTER TABLE daily_signal_summary 
                ADD PRIMARY KEY (id)
            """)
            print("[FIX DB] PRIMARY KEY adicionada com sucesso")
        
        # Verificar contagem final
        count = await conn.fetchval("SELECT COUNT(*) FROM daily_signal_summary")
        print(f"[FIX DB] Total de registros na tabela: {count}")
        
        print("[FIX DB] Correção concluída!")
        
    except Exception as e:
        print(f"[FIX DB] Erro: {e}")
        raise
    finally:
        await conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("CORREÇÃO DE CONSTRAINT - daily_signal_summary")
    print("=" * 60)
    asyncio.run(fix_database())
