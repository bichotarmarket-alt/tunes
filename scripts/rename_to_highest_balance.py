import sqlite3

def rename_column():
    conn = sqlite3.connect('autotrade.db')
    cursor = conn.cursor()

    try:
        # Verificar se a coluna initial_balance existe
        cursor.execute("PRAGMA table_info(autotrade_configs)")
        columns = [col[1] for col in cursor.fetchall()]

        if 'initial_balance' not in columns:
            print('Coluna initial_balance não existe, nada a fazer')
            return

        if 'highest_balance' in columns:
            print('Coluna highest_balance já existe')
            return

        # SQLite não suporta ALTER TABLE RENAME COLUMN diretamente
        # Precisamos criar uma nova tabela, copiar os dados e renomear
        cursor.execute("""
            CREATE TABLE autotrade_configs_new (
                id TEXT PRIMARY KEY,
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
                cooldown_seconds INTEGER DEFAULT 0,
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
                updated_at DATETIME,
                FOREIGN KEY (account_id) REFERENCES accounts(id),
                FOREIGN KEY (strategy_id) REFERENCES strategies(id)
            )
        """)

        # Copiar dados
        cursor.execute("""
            INSERT INTO autotrade_configs_new
            SELECT id, account_id, strategy_id, amount, stop1, stop2,
                   no_hibernate_on_consecutive_stop, stop_amount_win, stop_amount_loss,
                   soros, martingale, timeframe, min_confidence, cooldown_seconds,
                   trade_timing, all_win_percentage, initial_balance AS highest_balance,
                   is_active, daily_trades_count, last_trade_date, last_trade_time,
                   consecutive_stop_cooldown_until, last_activity_timestamp,
                   soros_level, soros_amount, martingale_level, martingale_amount,
                   loss_consecutive, win_consecutive, total_wins, total_losses,
                   created_at, updated_at
            FROM autotrade_configs
        """)

        # Deletar tabela antiga e renomear a nova
        cursor.execute("DROP TABLE autotrade_configs")
        cursor.execute("ALTER TABLE autotrade_configs_new RENAME TO autotrade_configs")

        conn.commit()
        print('✓ Coluna initial_balance renomeada para highest_balance com sucesso')

    except Exception as e:
        print(f'Erro: {e}')
        conn.rollback()
    finally:
        conn.close()

if __name__ == '__main__':
    rename_column()
