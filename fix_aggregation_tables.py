"""
Script para criar as tabelas do aggregation job manualmente
"""
import asyncio
import sqlite3
from pathlib import Path

async def create_aggregation_tables():
    """Criar tabelas aggregation_job_log e daily_signal_summary manualmente"""
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
        # Verificar e criar tabela aggregation_job_log
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='aggregation_job_log'")
        if not cursor.fetchone():
            print("Criando tabela aggregation_job_log...")
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
            print("✅ Tabela aggregation_job_log criada!")
        else:
            print("✓ Tabela aggregation_job_log já existe")
        
        # Verificar e criar tabela daily_signal_summary
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_signal_summary'")
        if not cursor.fetchone():
            print("Criando tabela daily_signal_summary...")
            cursor.execute("""
                CREATE TABLE daily_signal_summary (
                    id VARCHAR PRIMARY KEY,
                    date DATE NOT NULL,
                    strategy_id VARCHAR NOT NULL DEFAULT 'all',
                    asset_id VARCHAR NOT NULL DEFAULT 'all',
                    timeframe INTEGER NOT NULL DEFAULT 0,
                    total_signals INTEGER DEFAULT 0,
                    buy_signals INTEGER DEFAULT 0,
                    sell_signals INTEGER DEFAULT 0,
                    hold_signals INTEGER DEFAULT 0,
                    executed_signals INTEGER DEFAULT 0,
                    avg_confidence FLOAT DEFAULT 0.0,
                    avg_confluence FLOAT DEFAULT 0.0,
                    min_confidence FLOAT DEFAULT 0.0,
                    max_confidence FLOAT DEFAULT 0.0,
                    updated_at DATE NOT NULL
                )
            """)
            
            # Criar índices
            cursor.execute("CREATE INDEX idx_daily_summary_date ON daily_signal_summary (date)")
            cursor.execute("CREATE INDEX idx_daily_summary_date_strategy ON daily_signal_summary (date, strategy_id)")
            cursor.execute("CREATE INDEX idx_daily_summary_date_asset ON daily_signal_summary (date, asset_id)")
            cursor.execute("CREATE INDEX idx_daily_summary_updated ON daily_signal_summary (updated_at)")
            
            print("✅ Tabela daily_signal_summary criada com índices!")
        else:
            print("✓ Tabela daily_signal_summary já existe")
        
        conn.commit()
        print("\n✅ Todas as tabelas do Aggregation Job estão prontas!")
        return True
        
    except Exception as e:
        print(f"❌ Erro ao criar tabelas: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    asyncio.run(create_aggregation_tables())
