import asyncpg
import asyncio

async def check():
    conn = await asyncpg.connect('postgresql://postgres:root@localhost:5432/tunestrade')
    
    print("Verificando tipos das colunas...")
    
    # Check trades columns
    result = await conn.fetch('''
        SELECT column_name, data_type, udt_name 
        FROM information_schema.columns 
        WHERE table_name = 'trades' 
        AND column_name IN ('expires_at', 'placed_at', 'closed_at', 'status')
        ORDER BY column_name
    ''')
    print("\ntrades table columns:")
    for r in result:
        print(f"  {r['column_name']}: {r['data_type']} ({r['udt_name']})")
    
    # Check signals columns
    result = await conn.fetch('''
        SELECT column_name, data_type, udt_name 
        FROM information_schema.columns 
        WHERE table_name = 'signals' 
        AND column_name IN ('created_at', 'signal_type')
        ORDER BY column_name
    ''')
    print("\nsignals table columns:")
    for r in result:
        print(f"  {r['column_name']}: {r['data_type']} ({r['udt_name']})")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check())
