"""
Verificar estratégias do usuário Leandro Souza
"""
import asyncpg
import asyncio

async def check_strategies():
    conn = await asyncpg.connect('postgresql://postgres:root@localhost:5432/tunestrade')
    
    # Buscar usuário Leandro Souza
    user = await conn.fetchrow(
        "SELECT id, email, name FROM users WHERE name ILIKE '%leandro%' OR email ILIKE '%leandro%'"
    )
    
    if not user:
        print("Usuário Leandro Souza não encontrado")
        await conn.close()
        return
    
    print(f"Usuário encontrado: {user['name']} ({user['email']}) - ID: {user['id']}")
    
    # Buscar estratégias do usuário
    strategies = await conn.fetch(
        "SELECT id, name, description, is_active, created_at FROM strategies WHERE user_id = $1",
        user['id']
    )
    
    print(f"\nTotal de estratégias: {len(strategies)}")
    print("-" * 60)
    
    for s in strategies:
        print(f"\nID: {s['id']}")
        print(f"Nome: {s['name']}")
        print(f"Descrição: {s['description']}")
        print(f"Ativa: {s['is_active']}")
        print(f"Criada em: {s['created_at']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_strategies())
