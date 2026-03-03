#!/usr/bin/env python3
"""
Script para inserir contas de monitoramento PAYOUT e ATIVOS
com o SSID fornecido pelo usuário.
Execute: python scripts/insert_monitoring_accounts.py
"""

import asyncio
import sys
import uuid
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from core.database import get_db_context

# SSID fornecido pelo usuário
# Formato: 42["auth",{"session":"...","isDemo":1,"uid":...,"platform":2,...}]
PAYOUT_SSID = '42["auth",{"session":"3ukili81v4ej0epvv08fstd4oj","isDemo":1,"uid":125379914,"platform":2,"isFastHistory":true,"isOptimized":true}]'

# Para ATIVOS, podemos usar o mesmo SSID (conta demo)
ATIVOS_SSID = PAYOUT_SSID


async def insert_monitoring_accounts():
    """Inserir contas de monitoramento PAYOUT e ATIVOS"""
    
    print("=" * 60)
    print("INSERINDO CONTAS DE MONITORAMENTO")
    print("=" * 60)
    
    async with get_db_context() as db:
        try:
            # Verificar se já existem contas
            result = await db.execute(
                text("SELECT COUNT(*) FROM monitoring_accounts")
            )
            count = result.scalar()
            
            if count > 0:
                print(f"⚠️  Já existem {count} contas na tabela.")
                print("Desativando contas antigas...")
                await db.execute(
                    text("UPDATE monitoring_accounts SET is_active = 0")
                )
                await db.commit()
                print("✅ Contas antigas desativadas.")
            
            # Criar conta PAYOUT
            payout_id = str(uuid.uuid4())
            await db.execute(
                text("""
                    INSERT INTO monitoring_accounts 
                    (id, ssid, account_type, name, is_active, uid, platform)
                    VALUES (:id, :ssid, 'payout', 'PAYOUT Monitor', 1, :uid, 2)
                """),
                {
                    "id": payout_id, 
                    "ssid": PAYOUT_SSID,
                    "uid": 125379914
                }
            )
            print(f"✅ Conta PAYOUT criada: {payout_id[:8]}...")
            
            # Criar conta ATIVOS
            ativos_id = str(uuid.uuid4())
            await db.execute(
                text("""
                    INSERT INTO monitoring_accounts 
                    (id, ssid, account_type, name, is_active, uid, platform)
                    VALUES (:id, :ssid, 'ativos', 'ATIVOS Monitor', 1, :uid, 2)
                """),
                {
                    "id": ativos_id, 
                    "ssid": ATIVOS_SSID,
                    "uid": 125379914
                }
            )
            print(f"✅ Conta ATIVOS criada: {ativos_id[:8]}...")
            
            await db.commit()
            
            # Verificar inserção
            result = await db.execute(
                text("""
                    SELECT id, account_type, name, is_active, uid, platform,
                           substr(ssid, 1, 60) as ssid_preview
                    FROM monitoring_accounts
                    WHERE is_active = 1
                """)
            )
            rows = result.fetchall()
            
            print("\n" + "=" * 60)
            print("CONTAS CRIADAS:")
            print("=" * 60)
            for row in rows:
                print(f"\n📊 {row.account_type.upper()}")
                print(f"   ID: {row.id[:8]}...")
                print(f"   Nome: {row.name}")
                print(f"   UID: {row.uid}")
                print(f"   Platform: {row.platform}")
                print(f"   SSID: {row.ssid_preview}...")
            
            print("\n" + "=" * 60)
            print("✅ CONTAS DE MONITORAMENTO INSERIDAS COM SUCESSO!")
            print("=" * 60)
            print("\n⚠️  IMPORTANTE: Reinicie o data_collector para aplicar!")
            
        except Exception as e:
            print(f"\n❌ Erro: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(insert_monitoring_accounts())
