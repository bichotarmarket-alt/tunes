"""
Verificar e corrigir tipos das colunas
"""
import asyncpg
import asyncio

async def check_and_fix():
    conn = await asyncpg.connect('postgresql://postgres:root@localhost:5432/tunestrade')
    
    print("Verificando colunas...")
    
    # Check current types
    result = await conn.fetch('''
        SELECT column_name, data_type, udt_name 
        FROM information_schema.columns 
        WHERE table_name = 'trades' AND column_name = 'asset_id'
    ''')
    
    for r in result:
        print(f"  trades.asset_id: {r['data_type']} ({r['udt_name']})")
        
        if r['data_type'] == 'text':
            print("  -> Convertendo para INTEGER...")
            try:
                await conn.execute('''
                    ALTER TABLE trades 
                    ALTER COLUMN asset_id TYPE INTEGER 
                    USING asset_id::INTEGER;
                ''')
                print("  -> OK!")
            except Exception as e:
                print(f"  -> Erro: {e}")
    
    # Check signals.asset_id too
    result = await conn.fetch('''
        SELECT column_name, data_type, udt_name 
        FROM information_schema.columns 
        WHERE table_name = 'signals' AND column_name = 'asset_id'
    ''')
    
    for r in result:
        print(f"  signals.asset_id: {r['data_type']} ({r['udt_name']})")
        
        if r['data_type'] == 'text':
            print("  -> Convertendo para INTEGER...")
            try:
                await conn.execute('''
                    ALTER TABLE signals 
                    ALTER COLUMN asset_id TYPE INTEGER 
                    USING asset_id::INTEGER;
                ''')
                print("  -> OK!")
            except Exception as e:
                print(f"  -> Erro: {e}")
    
    await conn.close()
    print("\nConcluido!")

if __name__ == "__main__":
    asyncio.run(check_and_fix())
