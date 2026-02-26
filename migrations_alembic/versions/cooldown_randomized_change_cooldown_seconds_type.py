"""Change cooldown_seconds from INTEGER to TEXT to support randomized cooldown format (X-X)

Revision ID: cooldown_randomized
Revises: add_trade_timing
Create Date: 2026-02-16

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cooldown_randomized'
down_revision = 'add_trade_timing'
branch_labels = None
depends_on = None


def upgrade():
    """Convert cooldown_seconds from INTEGER to TEXT to support format "X-X" for randomized cooldown."""
    # SQLite doesn't support ALTER COLUMN directly, need to recreate table
    op.execute("""
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
            updated_at DATETIME,
            FOREIGN KEY(account_id) REFERENCES accounts (id),
            FOREIGN KEY(strategy_id) REFERENCES strategies (id)
        )
    """)

    # Copy data from old table to new table, converting INTEGER cooldown_seconds to TEXT
    op.execute("""
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

    # Drop old table and rename new table
    op.execute("DROP TABLE autotrade_configs")
    op.execute("ALTER TABLE autotrade_configs_new RENAME TO autotrade_configs")

    # Recreate indexes
    op.execute("CREATE INDEX ix_autotrade_configs_account_id ON autotrade_configs (account_id)")
    op.execute("CREATE INDEX ix_autotrade_configs_strategy_id ON autotrade_configs (strategy_id)")


def downgrade():
    """Revert cooldown_seconds back to INTEGER."""
    # Recreate table with INTEGER cooldown_seconds
    op.execute("""
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
            FOREIGN KEY(account_id) REFERENCES accounts (id),
            FOREIGN KEY(strategy_id) REFERENCES strategies (id)
        )
    """)

    # Copy data, converting TEXT cooldown_seconds to INTEGER (use 0 if invalid)
    op.execute("""
        INSERT INTO autotrade_configs_new
        SELECT id, account_id, strategy_id, amount, stop1, stop2,
               no_hibernate_on_consecutive_stop, stop_amount_win, stop_amount_loss,
               soros, martingale, timeframe, min_confidence,
               CAST(CASE 
                   WHEN cooldown_seconds IS NULL OR cooldown_seconds = '' THEN '0'
                   WHEN cooldown_seconds LIKE '%-%' THEN '0'
                   ELSE COALESCE(
                       (SELECT SUBSTR(cooldown_seconds, 1, INSTR(cooldown_seconds, '-') - 1) 
                        WHERE cooldown_seconds LIKE '%-%'),
                       cooldown_seconds
                   )
               END AS INTEGER) AS cooldown_seconds,
               trade_timing, all_win_percentage, highest_balance,
               is_active, daily_trades_count, last_trade_date, last_trade_time,
               consecutive_stop_cooldown_until, last_activity_timestamp,
               soros_level, soros_amount, martingale_level, martingale_amount,
               loss_consecutive, win_consecutive, total_wins, total_losses,
               created_at, updated_at
        FROM autotrade_configs
    """)

    # Drop old table and rename new table
    op.execute("DROP TABLE autotrade_configs")
    op.execute("ALTER TABLE autotrade_configs_new RENAME TO autotrade_configs")

    # Recreate indexes
    op.execute("CREATE INDEX ix_autotrade_configs_account_id ON autotrade_configs (account_id)")
    op.execute("CREATE INDEX ix_autotrade_configs_strategy_id ON autotrade_configs (strategy_id)")
