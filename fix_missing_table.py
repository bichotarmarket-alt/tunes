import asyncio
import asyncpg

async def check_and_create_table():
    conn = await asyncpg.connect('postgresql://postgres:root@localhost:5432/tunestrade')
    
    # Verificar se aggregation_job_log existe
    exists = await conn.fetchval("""
        SELECT EXISTS (
            SELECT 1 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'aggregation_job_log'
        )
    """)
    
    print(f'aggregation_job_log existe: {exists}')
    
    if not exists:
        print('Criando tabela aggregation_job_log...')
        await conn.execute("""
            CREATE TABLE aggregation_job_log (
                id SERIAL PRIMARY KEY,
                job_name VARCHAR NOT NULL,
                started_at DATE,
                completed_at DATE,
                records_processed INTEGER DEFAULT 0,
                status VARCHAR DEFAULT 'running',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print('Tabela criada com sucesso!')
    else:
        print('Tabela já existe.')
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_and_create_table())
