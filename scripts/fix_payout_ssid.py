#!/usr/bin/env python3
"""
Script para corrigir o SSID de monitoramento de payout
Atualiza o SSID para usar a conta correta: 11a2fbab-0433-4da4-9061-3353a229ace3
SSID correto: h4r0h63q8kou614d0n8aec7l29
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from database.database import get_async_session
from models.models import MonitoringAccount, MonitoringAccountType


async def fix_payout_monitoring_ssid():
    """Corrige o SSID de monitoramento de payout para usar a conta correta"""
    
    # Dados da conta correta
    CORRECT_ACCOUNT_ID = "11a2fbab-0433-4da4-9061-3353a229ace3"
    CORRECT_SSID = '42["auth",{"session":"h4r0h63q8kou614d0n8aec7l29","isDemo":1,"uid":121124095,"platform":2,"isFastHistory":true,"isOptimized":true}]'
    CORRECT_NAME = "Payout Monitor"
    CORRECT_IS_DEMO = True
    
    async with get_async_session() as session:
        # Buscar a conta de monitoramento atual
        result = await session.execute(
            select(MonitoringAccount).where(
                MonitoringAccount.account_type == MonitoringAccountType.PAYOUT
            )
        )
        payout_account = result.scalar_one_or_none()
        
        if payout_account:
            print(f"[INFO] Conta de PAYOUT encontrada:")
            print(f"  - ID: {payout_account.id}")
            print(f"  - Nome atual: {payout_account.name}")
            print(f"  - SSID atual: {payout_account.ssid[:50]}..." if len(payout_account.ssid) > 50 else f"  - SSID atual: {payout_account.ssid}")
            print(f"  - Is Demo: {payout_account.is_demo}")
            
            # Verificar se precisa atualizar
            if payout_account.id == CORRECT_ACCOUNT_ID and "h4r0h63q8kou614d0n8aec7l29" in payout_account.ssid:
                print(f"\n[OK] Conta de PAYOUT já está correta!")
                return
            
            # Atualizar a conta existente
            payout_account.id = CORRECT_ACCOUNT_ID
            payout_account.name = CORRECT_NAME
            payout_account.ssid = CORRECT_SSID
            payout_account.is_demo = CORRECT_IS_DEMO
            
            await session.commit()
            print(f"\n[SUCCESS] Conta de PAYOUT atualizada com sucesso!")
            print(f"  - Novo ID: {CORRECT_ACCOUNT_ID}")
            print(f"  - Novo nome: {CORRECT_NAME}")
            print(f"  - Novo SSID: {CORRECT_SSID[:50]}...")
        else:
            # Criar nova conta de monitoramento
            print(f"[INFO] Criando nova conta de monitoramento PAYOUT...")
            
            new_account = MonitoringAccount(
                id=CORRECT_ACCOUNT_ID,
                name=CORRECT_NAME,
                ssid=CORRECT_SSID,
                account_type=MonitoringAccountType.PAYOUT,
                is_demo=CORRECT_IS_DEMO,
            )
            
            session.add(new_account)
            await session.commit()
            
            print(f"\n[SUCCESS] Nova conta de PAYOUT criada com sucesso!")
            print(f"  - ID: {CORRECT_ACCOUNT_ID}")
            print(f"  - Nome: {CORRECT_NAME}")
            print(f"  - SSID: {CORRECT_SSID[:50]}...")


if __name__ == "__main__":
    print("=" * 60)
    print("CORREÇÃO DO SSID DE MONITORAMENTO PAYOUT")
    print("=" * 60)
    print()
    
    asyncio.run(fix_payout_monitoring_ssid())
    
    print()
    print("=" * 60)
    print("IMPORTANTE: Reinicie o data_collector para aplicar as mudanças!")
    print("=" * 60)
