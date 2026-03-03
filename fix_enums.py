"""
Fix PostgreSQL enums - corrigir tipos de colunas
"""
import asyncpg
import asyncio

async def fix_enums():
    conn = await asyncpg.connect('postgresql://postgres:root@localhost:5432/tunestrade')
    
    print('Criando enums e alterando colunas...')
    
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
    
    # Alterar colunas
    print('Alterando trades.status para tradestatus...')
    await conn.execute('''
        ALTER TABLE trades 
        ALTER COLUMN status TYPE tradestatus 
        USING status::tradestatus;
    ''')
    
    print('Alterando signals.signal_type para signaltype...')
    await conn.execute('''
        ALTER TABLE signals 
        ALTER COLUMN signal_type TYPE signaltype 
        USING signal_type::signaltype;
    ''')
    
    print('Alterando signals.direction para tradedirection...')
    await conn.execute('''
        ALTER TABLE signals 
        ALTER COLUMN direction TYPE tradedirection 
        USING direction::tradedirection;
    ''')
    
    print('Alterando trades.direction para tradedirection...')
    await conn.execute('''
        ALTER TABLE trades 
        ALTER COLUMN direction TYPE tradedirection 
        USING direction::tradedirection;
    ''')
    
    print('Enums criados e colunas alteradas!')
    await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_enums())
