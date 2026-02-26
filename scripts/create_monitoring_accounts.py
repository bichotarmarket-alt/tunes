"""
Script para criar contas de monitoramento no banco de dados
Execute: python scripts/create_monitoring_accounts.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import uuid
from sqlalchemy import text
from core.database import get_db_context

async def create_monitoring_accounts():
    """Criar contas de monitoramento PAYOUT e ATIVOS"""
    
    # Você precisa fornecer os SSIDs reais aqui
    # Pode obter os SSIDs do console do navegador (localStorage.getItem('token'))
    # ou da interface da Pocket Option
    
    PAYOUT_SSID = ""  # <-- COLOQUE O SSID DO PAYOUT AQUI
    ATIVOS_SSID = ""  # <-- COLOQUE O SSID DOS ATIVOS AQUI (pode ser o mesmo da conta demo)
    
    if not PAYOUT_SSID or not ATIVOS_SSID:
        print("=" * 60)
        print("ERRO: Você precisa configurar os SSIDs no script!")
        print("=" * 60)
        print("\nPara obter o SSID:")
        print("1. Abra o site Pocket Option no navegador")
        print("2. Faça login na conta demo")
        print("3. Abra o console do navegador (F12)")
        print("4. Digite: localStorage.getItem('token')")
        print("5. Copie o valor (é o SSID)")
        print("\nOu use o SSID de uma das contas já conectadas:")
        print("- Leandro Souza: 2e201d77-af1f-4640-be6c-ba59dc6b0255")
        print("- Gabriel: 6586753b-47c9-4943-9d93-b26f0c9e03dd")
        print("- ricardo@gmail.com: f7906173-ca99-4de4-bbb5-d5411a01dc7d")
        print("=" * 60)
        return
    
    async with get_db_context() as db:
        try:
            # Verificar se já existem contas
            result = await db.execute(
                text("SELECT COUNT(*) FROM monitoring_accounts WHERE is_active = 1")
            )
            count = result.scalar()
            
            if count > 0:
                print(f"Já existem {count} contas de monitoramento ativas.")
                response = input("Deseja recriar? (s/n): ")
                if response.lower() != 's':
                    print("Operação cancelada.")
                    return
                
                # Desativar contas existentes
                await db.execute(
                    text("UPDATE monitoring_accounts SET is_active = 0")
                )
                await db.commit()
                print("Contas antigas desativadas.")
            
            # Criar conta PAYOUT
            payout_id = str(uuid.uuid4())
            await db.execute(
                text("""
                    INSERT INTO monitoring_accounts (id, ssid, account_type, name, is_active, platform)
                    VALUES (:id, :ssid, 'payout', 'PAYOUT Monitor', 1, 1)
                """),
                {"id": payout_id, "ssid": PAYOUT_SSID}
            )
            print(f"✅ Conta PAYOUT criada: {payout_id[:8]}...")
            
            # Criar conta ATIVOS
            ativos_id = str(uuid.uuid4())
            await db.execute(
                text("""
                    INSERT INTO monitoring_accounts (id, ssid, account_type, name, is_active, platform)
                    VALUES (:id, :ssid, 'ativos', 'ATIVOS Monitor 1', 1, 1)
                """),
                {"id": ativos_id, "ssid": ATIVOS_SSID}
            )
            print(f"✅ Conta ATIVOS criada: {ativos_id[:8]}...")
            
            await db.commit()
            print("\n" + "=" * 60)
            print("✅ Contas de monitoramento criadas com sucesso!")
            print("=" * 60)
            print("\nReinicie o sistema para aplicar as mudanças.")
            
        except Exception as e:
            print(f"❌ Erro: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(create_monitoring_accounts())
