"""
Verificar dados no PostgreSQL
"""
import asyncpg
import asyncio

async def check_data():
    conn = await asyncpg.connect('postgresql://postgres:root@localhost:5432/tunestrade')
    
    print("=" * 60)
    print("VERIFICAÇÃO DOS DADOS NO POSTGRESQL")
    print("=" * 60)
    
    # Verificar tabelas e contagem de registros
    tables = [
        'users', 'accounts', 'assets', 'strategies', 'trades', 
        'signals', 'indicators', 'autotrade_configs', 'monitoring_accounts'
    ]
    
    for table in tables:
        try:
            count = await conn.fetchval(f'SELECT COUNT(*) FROM {table}')
            print(f"✓ {table}: {count} registros")
        except Exception as e:
            print(f"✗ {table}: ERRO - {e}")
    
    # Verificar enums
    print("\n" + "=" * 60)
    print("ENUMS CRIADOS:")
    print("=" * 60)
    
    enums = await conn.fetch('''
        SELECT typname FROM pg_type 
        WHERE typname IN ('tradestatus', 'signaltype', 'tradedirection')
    ''')
    for enum in enums:
        print(f"✓ {enum['typname']}")
    
    # Verificar tipos das colunas
    print("\n" + "=" * 60)
    print("TIPOS DE COLUNAS:")
    print("=" * 60)
    
    cols = await conn.fetch('''
        SELECT table_name, column_name, data_type, udt_name 
        FROM information_schema.columns 
        WHERE table_name IN ('trades', 'signals') 
        AND column_name IN ('status', 'signal_type', 'direction')
        ORDER BY table_name, column_name
    ''')
    
    for col in cols:
        print(f"✓ {col['table_name']}.{col['column_name']}: {col['udt_name']}")
    
    await conn.close()
    print("\n" + "=" * 60)
    print("VERIFICAÇÃO CONCLUÍDA!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(check_data())
