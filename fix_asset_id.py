"""
Fix trades.asset_id column type
"""
import asyncpg
import asyncio

async def fix():
    conn = await asyncpg.connect('postgresql://postgres:root@localhost:5432/tunestrade')
    
    print("Verificando trades.asset_id...")
    result = await conn.fetch('''
        SELECT column_name, data_type, udt_name 
        FROM information_schema.columns 
        WHERE table_name = 'trades' AND column_name = 'asset_id'
    ''')
    for r in result:
        print(f"  {r['column_name']}: {r['data_type']} ({r['udt_name']})")
    
    print("\nAlterando trades.asset_id para INTEGER...")
    try:
        await conn.execute('''
            ALTER TABLE trades 
            ALTER COLUMN asset_id TYPE INTEGER 
            USING asset_id::INTEGER;
        ''')
        print("  OK!")
    except Exception as e:
        print(f"  Erro: {e}")
    
    print("\nVerificando signals.asset_id...")
    result = await conn.fetch('''
        SELECT column_name, data_type, udt_name 
        FROM information_schema.columns 
        WHERE table_name = 'signals' AND column_name = 'asset_id'
    ''')
    for r in result:
        print(f"  {r['column_name']}: {r['data_type']} ({r['udt_name']})")
    
    try:
        await conn.execute('''
            ALTER TABLE signals 
            ALTER COLUMN asset_id TYPE INTEGER 
            USING asset_id::INTEGER;
        ''')
        print("  signals.asset_id OK!")
    except Exception as e:
        print(f"  Erro: {e}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(fix())
