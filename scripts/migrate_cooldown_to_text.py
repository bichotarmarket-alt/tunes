"""Script para alterar cooldown_seconds de INTEGER para TEXT"""
import sqlite3

def migrate_cooldown_seconds():
    conn = sqlite3.connect('autotrade.db')
    cursor = conn.cursor()
    
    try:
        # Verificar o tipo atual da coluna
        cursor.execute("PRAGMA table_info(autotrade_configs)")
        columns = cursor.fetchall()
        
        cooldown_col = None
        for col in columns:
            if col[1] == 'cooldown_seconds':
                cooldown_col = col
                break
        
        if not cooldown_col:
            print("Coluna cooldown_seconds não encontrada")
            return False
        
        print(f"Tipo atual de cooldown_seconds: {cooldown_col[2]}")
        
        if cooldown_col[2].upper() == 'TEXT':
            print("Coluna já é TEXT, não precisa migrar")
            return True
        
        # Criar nova tabela com cooldown_seconds como TEXT
        print("Criando nova tabela...")
        cursor.execute("""
            CREATE TABLE autotrade_configs_new (
                id TEXT NOT NULL PRIMARY KEY,
                account_id TEXT NOT NULL,
                strategy_id TEXT,
                amount REAL NOT NULL DEFAULT 1.0,
                stop1 INTEGER NOT NULL DEFAULT 3,
                stop2 INTEGER NOT NULL DEFAULT 5,
                no_hibernate_on_consecutive_stop BOOLEAN NOT NULL DEFAULT 0,
                stop_amount_win REAL NOT NULL DEFAULT 0.0,
                stop_amount_loss REAL NOT NULL DEFAULT 0.0,
                soros INTEGER NOT NULL DEFAULT 0,
                martingale INTEGER NOT NULL DEFAULT 0,
                timeframe INTEGER NOT NULL DEFAULT 5,
                min_confidence REAL NOT NULL DEFAULT 0.7,
                cooldown_seconds TEXT DEFAULT '0',
                trade_timing TEXT NOT NULL DEFAULT 'on_signal',
                all_win_percentage REAL NOT NULL DEFAULT 0.0,
                highest_balance REAL,
                is_active BOOLEAN DEFAULT 0,
                daily_trades_count INTEGER DEFAULT 0,
                last_trade_date DATETIME,
                last_trade_time DATETIME,
                consecutive_stop_cooldown_until DATETIME,
                last_activity_timestamp DATETIME,
                soros_level INTEGER DEFAULT 0,
                soros_amount REAL DEFAULT 0.0,
                martingale_level INTEGER DEFAULT 0,
                martingale_amount REAL DEFAULT 0.0,
                loss_consecutive INTEGER DEFAULT 0,
                win_consecutive INTEGER DEFAULT 0,
                total_wins INTEGER DEFAULT 0,
                total_losses INTEGER DEFAULT 0,
                created_at DATETIME,
                updated_at DATETIME
            )
        """)
        
        # Copiar dados
        print("Copiando dados...")
        cursor.execute("""
            INSERT INTO autotrade_configs_new
            SELECT id, account_id, strategy_id, amount, stop1, stop2,
                   no_hibernate_on_consecutive_stop, stop_amount_win, stop_amount_loss,
                   soros, martingale, timeframe, min_confidence,
                   CAST(cooldown_seconds AS TEXT) AS cooldown_seconds,
                   trade_timing, all_win_percentage, highest_balance,
                   is_active, daily_trades_count, last_trade_date, last_trade_time,
                   consecutive_stop_cooldown_until, last_activity_timestamp,
                   soros_level, soros_amount, martingale_level, martingale_amount,
                   loss_consecutive, win_consecutive, total_wins, total_losses,
                   created_at, updated_at
            FROM autotrade_configs
        """)
        
        # Drop tabela antiga
        print("Removendo tabela antiga...")
        cursor.execute("DROP TABLE autotrade_configs")
        
        # Renomear tabela nova
        print("Renomeando tabela...")
        cursor.execute("ALTER TABLE autotrade_configs_new RENAME TO autotrade_configs")
        
        # Recriar índices
        print("Recriando índices...")
        cursor.execute("CREATE INDEX ix_autotrade_configs_account_id ON autotrade_configs (account_id)")
        cursor.execute("CREATE INDEX ix_autotrade_configs_strategy_id ON autotrade_configs (strategy_id)")
        
        conn.commit()
        print("\n[OK] Migration concluida com sucesso!")
        return True
        
    except Exception as e:
        print(f"\n[ERRO] Erro durante migration: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_cooldown_seconds()
