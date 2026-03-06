"""Migration: Add performance indexes for high load support (1000+ users)

Run this migration to add indexes that will significantly improve query performance
when the system scales to many users.
"""

from sqlalchemy import text

# SQL statements to create indexes
CREATE_INDEXES_SQL = """
-- Indexes for strategies table (frequently queried)
CREATE INDEX IF NOT EXISTS idx_strategies_user_id ON strategies(user_id);
CREATE INDEX IF NOT EXISTS idx_strategies_account_id ON strategies(account_id);
CREATE INDEX IF NOT EXISTS idx_strategies_user_active ON strategies(user_id, is_active);

-- Indexes for accounts table
CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_accounts_user_active ON accounts(user_id, is_active);

-- Indexes for trades table (heavy read operations)
CREATE INDEX IF NOT EXISTS idx_trades_account_id ON trades(account_id);
CREATE INDEX IF NOT EXISTS idx_trades_strategy_id ON trades(strategy_id);
CREATE INDEX IF NOT EXISTS idx_trades_user_connection_type ON trades(user_id, connection_type);
CREATE INDEX IF NOT EXISTS idx_trades_placed_at ON trades(placed_at);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_account_placed ON trades(account_id, placed_at DESC);

-- Indexes for autotrade_configs table
CREATE INDEX IF NOT EXISTS idx_autotrade_configs_account_id ON autotrade_configs(account_id);
CREATE INDEX IF NOT EXISTS idx_autotrade_configs_strategy_id ON autotrade_configs(strategy_id);
CREATE INDEX IF NOT EXISTS idx_autotrade_configs_active ON autotrade_configs(is_active);

-- Indexes for users table
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_users_is_superuser ON users(is_superuser) WHERE is_superuser = true;

-- Indexes for strategy_indicators association table
CREATE INDEX IF NOT EXISTS idx_strategy_indicators_strategy_id ON strategy_indicators(strategy_id);
CREATE INDEX IF NOT EXISTS idx_strategy_indicators_indicator_id ON strategy_indicators(indicator_id);

-- Composite indexes for common query patterns
CREATE INDEX IF NOT EXISTS idx_trades_user_status_placed ON trades(user_id, status, placed_at DESC);
CREATE INDEX IF NOT EXISTS idx_strategies_user_type_active ON strategies(user_id, type, is_active);

-- Partial indexes for active records (saves space and improves performance)
CREATE INDEX IF NOT EXISTS idx_autotrade_configs_account_active ON autotrade_configs(account_id) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_trades_recent ON trades(placed_at) WHERE placed_at > NOW() - INTERVAL '30 days';
"""

# SQL to analyze tables after creating indexes (updates query planner statistics)
ANALYZE_SQL = """
ANALYZE strategies;
ANALYZE accounts;
ANALYZE trades;
ANALYZE autotrade_configs;
ANALYZE users;
ANALYZE strategy_indicators;
"""

async def create_performance_indexes(db_session):
    """Create all performance indexes"""
    print("Creating performance indexes for 1000+ users support...")
    
    # Split and execute each statement
    statements = [s.strip() for s in CREATE_INDEXES_SQL.split(';') if s.strip()]
    
    for statement in statements:
        if statement.startswith('CREATE INDEX'):
            try:
                await db_session.execute(text(statement))
                print(f"✓ Created: {statement[:60]}...")
            except Exception as e:
                if 'already exists' in str(e).lower():
                    print(f"⊘ Already exists: {statement[:50]}...")
                else:
                    print(f"✗ Error creating index: {e}")
    
    await db_session.commit()
    print("\nIndexes created successfully!")
    
    # Analyze tables
    print("\nAnalyzing tables...")
    await db_session.execute(text(ANALYZE_SQL))
    await db_session.commit()
    print("✓ Tables analyzed!")


# For running as a standalone script
if __name__ == "__main__":
    import asyncio
    import sys
    sys.path.insert(0, '/app')
    
    from core.database import get_db
    
    async def main():
        async with get_db() as db:
            await create_performance_indexes(db)
    
    asyncio.run(main())
