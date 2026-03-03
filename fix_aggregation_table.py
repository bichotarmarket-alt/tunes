"""
Script para criar a tabela aggregation_job_log manualmente
"""
import asyncio
import sqlite3
from pathlib import Path

async def create_aggregation_job_log_table():
    """Criar tabela aggregation_job_log manualmente"""
    # Possíveis caminhos do banco de dados
    possible_paths = [
        Path("data/autotrade.db"),
        Path("autotrade.db"),
        Path("../data/autotrade.db"),
        Path("instance/autotrade.db"),
    ]
    
    db_path = None
    for path in possible_paths:
        if path.exists():
            db_path = path
            break
    
    if not db_path:
        print("Banco de dados não encontrado. Procurando em:")
        for path in possible_paths:
            print(f"  - {path.absolute()}")
        return False
    
    print(f"Conectando ao banco: {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Verificar se a tabela já existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='aggregation_job_log'")
        if cursor.fetchone():
            print("Tabela aggregation_job_log já existe!")
            return True
        
        # Criar a tabela
        cursor.execute("""
            CREATE TABLE aggregation_job_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_name VARCHAR NOT NULL,
                started_at DATE NOT NULL,
                completed_at DATE,
                records_processed INTEGER DEFAULT 0,
                status VARCHAR NOT NULL,
                error_message VARCHAR
            )
        """)
        
        conn.commit()
        print("✅ Tabela aggregation_job_log criada com sucesso!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabela: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    asyncio.run(create_aggregation_job_log_table())
