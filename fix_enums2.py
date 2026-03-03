"""
Fix PostgreSQL enums - corrigir tipos de colunas
"""
import asyncpg
import asyncio

async def fix_enums():
    conn = await asyncpg.connect('postgresql://postgres:root@localhost:5432/tunestrade')
    
    print('Verificando colunas existentes...')
    
    # Verificar quais colunas existem em signals
    cols = await conn.fetch('''
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'signals' AND column_name IN ('signal_type', 'direction')
    ''')
    signal_cols = [r['column_name'] for r in cols]
    print(f'Colunas em signals: {signal_cols}')
    
    # Verificar quais colunas existem em trades  
    cols = await conn.fetch('''
        SELECT column_name FROM information_schema.columns 
        WHERE table_name = 'trades' AND column_name IN ('status', 'direction')
    ''')
    trade_cols = [r['column_name'] for r in cols]
    print(f'Colunas em trades: {trade_cols}')
    
    print('Criando enums...')
    
    # Criar enums
    await conn.execute('''
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tradestatus') THEN
                CREATE TYPE tradestatus AS ENUM ('pending', 'active', 'closed', 'win', 'loss', 'draw', 'cancelled');
            END IF;
        END $$;
    ''')
    
    await conn.execute('''
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'signaltype') THEN
                CREATE TYPE signaltype AS ENUM ('buy', 'sell', 'hold');
            END IF;
        END $$;
    ''')
    
    await conn.execute('''
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'tradedirection') THEN
                CREATE TYPE tradedirection AS ENUM ('call', 'put');
            END IF;
        END $$;
    ''')
    
    # Alterar apenas colunas que existem
    if 'status' in trade_cols:
        print('Alterando trades.status...')
        await conn.execute('''
            ALTER TABLE trades ALTER COLUMN status TYPE tradestatus 
            USING status::tradestatus;
        ''')
    
    if 'signal_type' in signal_cols:
        print('Alterando signals.signal_type...')
        await conn.execute('''
            ALTER TABLE signals ALTER COLUMN signal_type TYPE signaltype 
            USING signal_type::signaltype;
        ''')
    
    if 'direction' in signal_cols:
        print('Alterando signals.direction...')
        await conn.execute('''
            ALTER TABLE signals ALTER COLUMN direction TYPE tradedirection 
            USING direction::tradedirection;
        ''')
    
    if 'direction' in trade_cols:
        print('Alterando trades.direction...')
        await conn.execute('''
            ALTER TABLE trades ALTER COLUMN direction TYPE tradedirection 
            USING direction::tradedirection;
        ''')
    
    print('Concluido!')
    await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_enums())
