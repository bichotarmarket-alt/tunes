"""
Script para criar índices no PostgreSQL para otimizar queries lentas
"""
import asyncpg
import asyncio

async def create_indexes():
    conn = await asyncpg.connect('postgresql://postgres:root@localhost:5432/tunestrade')
    
    indexes = [
        # Índices para signals (tabela existe)
        ("idx_signals_asset_timeframe", 
         "CREATE INDEX IF NOT EXISTS idx_signals_asset_timeframe ON signals(asset_id, timeframe, created_at DESC)"),
        
        # Índices para trades (tabela existe)
        ("idx_trades_account_status", 
         "CREATE INDEX IF NOT EXISTS idx_trades_account_status ON trades(account_id, status)"),
        
        # Índices para autotrade_configs (tabela existe)
        ("idx_autotrade_active", 
         "CREATE INDEX IF NOT EXISTS idx_autotrade_active ON autotrade_configs(is_active, account_id)"),
        # Índice composto para JOIN com strategies
        ("idx_autotrade_strategy_id", 
         "CREATE INDEX IF NOT EXISTS idx_autotrade_strategy_id ON autotrade_configs(strategy_id) WHERE strategy_id IS NOT NULL"),
        
        # Índices para strategies
        ("idx_strategies_user_active", 
         "CREATE INDEX IF NOT EXISTS idx_strategies_user_active ON strategies(user_id, is_active)"),
        
        # Índices para users
        ("idx_users_email", 
         "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)"),
        
        # Índices para strategy_indicators (tabela de associação)
        ("idx_strategy_indicators_strategy_id", 
         "CREATE INDEX IF NOT EXISTS idx_strategy_indicators_strategy_id ON strategy_indicators(strategy_id)"),
        ("idx_strategy_indicators_indicator_id", 
         "CREATE INDEX IF NOT EXISTS idx_strategy_indicators_indicator_id ON strategy_indicators(indicator_id)"),
        
        # Índices para indicators
        ("idx_indicators_type", 
         "CREATE INDEX IF NOT EXISTS idx_indicators_type ON indicators(type)"),
        
        # Índices para accounts
        ("idx_accounts_user_id", 
         "CREATE INDEX IF NOT EXISTS idx_accounts_user_id ON accounts(user_id)"),
        ("idx_accounts_id", 
         "CREATE INDEX IF NOT EXISTS idx_accounts_id ON accounts(id)"),
        
        # Índices para assets
        ("idx_assets_symbol", 
         "CREATE INDEX IF NOT EXISTS idx_assets_symbol ON assets(symbol)"),
        ("idx_assets_is_active", 
         "CREATE INDEX IF NOT EXISTS idx_assets_is_active ON assets(is_active) WHERE is_active = true"),
    ]
    
    print("Criando índices para otimização...\n")
    
    for idx_name, idx_sql in indexes:
        try:
            await conn.execute(idx_sql)
            print(f"✅ {idx_name}: CRIADO")
        except Exception as e:
            print(f"⚠️  {idx_name}: {e}")
    
    print("\n✅ Índices criados com sucesso!")
    
    # Analisar tabelas para atualizar estatísticas
    print("\nAtualizando estatísticas das tabelas...")
    tables = ['signals', 'trades', 'autotrade_configs', 'strategies', 'users']
    for table in tables:
        try:
            await conn.execute(f"ANALYZE {table}")
            print(f"✅ {table} analisada")
        except Exception as e:
            print(f"⚠️  {table}: {e}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(create_indexes())
