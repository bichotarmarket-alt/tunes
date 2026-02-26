"""
Script para verificar as contas de monitoramento no banco de dados
Execute: python scripts/check_monitoring_accounts.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from sqlalchemy import text
from core.database import get_db_context

async def check_monitoring_accounts():
    """Verificar contas de monitoramento no banco"""
    
    print("=" * 60)
    print("VERIFICAÇÃO DE CONTAS DE MONITORAMENTO")
    print("=" * 60)
    
    async with get_db_context() as db:
        try:
            # Verificar todas as contas na tabela
            result = await db.execute(
                text("""
                    SELECT id, ssid, account_type, name, is_active, created_at
                    FROM monitoring_accounts
                    ORDER BY created_at DESC
                """)
            )
            rows = result.fetchall()
            
            print(f"\nTotal de contas na tabela: {len(rows)}")
            print("-" * 60)
            
            for row in rows:
                id_, ssid, account_type, name, is_active, created_at = row
                print(f"\nID: {id_}")
                print(f"  Type: {account_type}")
                print(f"  Name: {name}")
                print(f"  Active: {is_active}")
                print(f"  SSID: {ssid[:50] if ssid else 'VAZIO'}...")
                print(f"  Created: {created_at}")
            
            # Verificar especificamente contas ativas
            print("\n" + "=" * 60)
            print("CONTAS ATIVAS (is_active = 1)")
            print("=" * 60)
            
            result = await db.execute(
                text("""
                    SELECT id, ssid, account_type, name
                    FROM monitoring_accounts
                    WHERE is_active = 1
                """)
            )
            active_rows = result.fetchall()
            
            if not active_rows:
                print("NENHUMA CONTA ATIVA ENCONTRADA!")
                print("\nPara ativar contas, execute:")
                print("UPDATE monitoring_accounts SET is_active = 1;")
            else:
                for row in active_rows:
                    id_, ssid, account_type, name = row
                    print(f"\n✅ {account_type.upper()}: {name}")
                    print(f"   ID: {id_[:8]}...")
                    print(f"   SSID: {ssid[:50] if ssid else 'VAZIO'}...")
            
            # Verificar contas payout ativas
            print("\n" + "=" * 60)
            print("CONTAS PAYOUT ATIVAS")
            print("=" * 60)
            
            result = await db.execute(
                text("""
                    SELECT id, ssid, name
                    FROM monitoring_accounts
                    WHERE account_type = 'payout' AND is_active = 1
                """)
            )
            payout_rows = result.fetchall()
            
            if payout_rows:
                for row in payout_rows:
                    id_, ssid, name = row
                    print(f"✅ {name}: SSID configurado = {ssid is not None and len(ssid) > 0}")
            else:
                print("❌ Nenhuma conta PAYOUT ativa")
            
            # Verificar contas ativos ativas
            print("\n" + "=" * 60)
            print("CONTAS ATIVOS ATIVAS")
            print("=" * 60)
            
            result = await db.execute(
                text("""
                    SELECT id, ssid, name
                    FROM monitoring_accounts
                    WHERE account_type = 'ativos' AND is_active = 1
                """)
            )
            ativos_rows = result.fetchall()
            
            if ativos_rows:
                for row in ativos_rows:
                    id_, ssid, name = row
                    print(f"✅ {name}: SSID configurado = {ssid is not None and len(ssid) > 0}")
            else:
                print("❌ Nenhuma conta ATIVOS ativa")
            
            print("\n" + "=" * 60)
            print("DIAGNÓSTICO")
            print("=" * 60)
            
            if not payout_rows and not ativos_rows:
                print("\n❌ PROBLEMA: Nenhuma conta de monitoramento ativa!")
                print("\nSolução:")
                print("1. Ative as contas existentes:")
                print("   UPDATE monitoring_accounts SET is_active = 1;")
                print("\n2. Ou adicione SSIDs às contas existentes:")
                print("   UPDATE monitoring_accounts SET ssid = 'SEU_SSID_AQUI' WHERE id = 'ID_DA_CONTA';")
            elif payout_rows and not any(r[1] for r in payout_rows):
                print("\n❌ PROBLEMA: Conta PAYOUT existe mas SSID está vazio!")
                print("\nSolução: Adicione o SSID:")
                print("   UPDATE monitoring_accounts SET ssid = 'SEU_SSID' WHERE account_type = 'payout';")
            elif ativos_rows and not any(r[1] for r in ativos_rows):
                print("\n❌ PROBLEMA: Contas ATIVOS existem mas SSIDs estão vazios!")
                print("\nSolução: Adicione os SSIDs:")
                print("   UPDATE monitoring_accounts SET ssid = 'SEU_SSID' WHERE account_type = 'ativos';")
            else:
                print("\n✅ Contas de monitoramento configuradas corretamente!")
                print("Se ainda não funcionar, reinicie o sistema.")
            
        except Exception as e:
            print(f"❌ Erro ao verificar contas: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_monitoring_accounts())
