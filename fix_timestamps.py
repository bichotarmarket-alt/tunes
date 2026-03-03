"""
Converter colunas TEXT para TIMESTAMP no PostgreSQL
"""
import asyncpg
import asyncio

async def fix_timestamps():
    conn = await asyncpg.connect('postgresql://postgres:root@localhost:5432/tunestrade')
    
    print("Convertendo colunas de TEXT para TIMESTAMP...")
    
    try:
        # Converter expires_at
        print("1. Alterando trades.expires_at...")
        await conn.execute('''
            ALTER TABLE trades 
            ALTER COLUMN expires_at TYPE TIMESTAMP 
            USING expires_at::TIMESTAMP;
        ''')
        print("   OK!")
    except Exception as e:
        print(f"   Erro: {e}")
    
    try:
        # Converter placed_at
        print("2. Alterando trades.placed_at...")
        await conn.execute('''
            ALTER TABLE trades 
            ALTER COLUMN placed_at TYPE TIMESTAMP 
            USING placed_at::TIMESTAMP;
        ''')
        print("   OK!")
    except Exception as e:
        print(f"   Erro: {e}")
    
    try:
        # Converter closed_at
        print("3. Alterando trades.closed_at...")
        await conn.execute('''
            ALTER TABLE trades 
            ALTER COLUMN closed_at TYPE TIMESTAMP 
            USING closed_at::TIMESTAMP;
        ''')
        print("   OK!")
    except Exception as e:
        print(f"   Erro: {e}")
    
    print("\nConversão concluída!")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(fix_timestamps())
