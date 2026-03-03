"""
Script para ativar todos os autotrades dos usuários
Execute: python scripts/enable_all_autotrades.py

Funciona como o botão "Turn On" no aplicativo - ativa as estratégias e notifica o sistema em tempo real.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Adicionar root ao path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_context
from models import AutoTradeConfig, Account
from sqlalchemy import update, select
from sqlalchemy.orm import selectinload
from loguru import logger


async def enable_all_autotrades():
    """Ativar todos os autotrades no banco e notificar o sistema em tempo real"""
    logger.info("🔧 Ativando todos os autotrades...")
    
    activated_accounts = []
    
    async with get_db_context() as db:
        # Buscar configs com suas contas
        result = await db.execute(
            select(AutoTradeConfig).options(selectinload(AutoTradeConfig.account))
        )
        configs = result.scalars().all()
        
        # Coletar account_ids antes de ativar
        for config in configs:
            if config.account_id:
                activated_accounts.append(config.account_id)
        
        # Remover duplicatas
        activated_accounts = list(set(activated_accounts))
        
        # Atualizar todos os autotrades para is_active=True
        result = await db.execute(
            update(AutoTradeConfig)
            .values(is_active=True, updated_at=datetime.utcnow())
        )
        await db.commit()
        
        # Atualizar last_activity das contas usando SQL nativo (evita problemas de schema)
        if activated_accounts:
            try:
                from sqlalchemy import text
                # Construir string com placeholders corretos para PostgreSQL
                placeholders = ','.join([f":id_{i}" for i in range(len(activated_accounts))])
                params = {f"id_{i}": account_id for i, account_id in enumerate(activated_accounts)}
                
                await db.execute(
                    text(f"UPDATE accounts SET last_activity_timestamp = NOW() WHERE id IN ({placeholders})"),
                    params
                )
                await db.commit()
                logger.info(f"📋 {len(activated_accounts)} conta(s) marcada(s) como ativas")
            except Exception as e:
                logger.warning(f"⚠️ Não foi possível atualizar last_activity: {e}")
                logger.info("📋 Contas serão conectadas na próxima verificação do sistema")
        
        updated_count = result.rowcount
        logger.success(f"✅ {updated_count} autotrade(s) ativado(s) no banco!")
        
        return updated_count, activated_accounts


async def notify_system(activated_accounts):
    """Notificar o sistema em tempo real sobre os usuários ativados"""
    logger.info("📡 Notificando sistema em tempo real...")
    
    try:
        # Importar e invalidar cache do realtime data collector
        from services.data_collector.realtime import get_realtime_data_collector
        
        realtime_collector = get_realtime_data_collector()
        if realtime_collector and hasattr(realtime_collector, 'invalidate_autotrade_configs_cache'):
            realtime_collector.invalidate_autotrade_configs_cache()
            logger.success("🔄 Cache de configs invalidado - sistema recarregará configs imediatamente")
        else:
            logger.warning("⚠️ Realtime collector não disponível (sistema pode estar offline)")
        
        # Notificar connection manager para verificar contas imediatamente
        if realtime_collector and hasattr(realtime_collector, 'connection_manager'):
            cm = realtime_collector.connection_manager
            if cm and hasattr(cm, '_last_check_time'):
                # Resetar timestamp para forçar verificação imediata
                cm._last_check_time = 0
                logger.success("⏱️ Connection manager notificado - verificação de conexões acelerada")
        
        logger.success(f"✅ Sistema notificado sobre {len(activated_accounts)} usuário(s) ativado(s)")
        logger.info("⏳ As conexões serão estabelecidas em até 5-10 segundos...")
        
    except Exception as e:
        logger.error(f"❌ Erro ao notificar sistema: {e}")
        logger.warning("⚠️ Configs ativadas no banco, mas sistema em tempo real pode demorar para detectar")


if __name__ == "__main__":    
    try:
        count, accounts = asyncio.run(enable_all_autotrades())
        
        # Notificar sistema em tempo real
        if accounts:
            asyncio.run(notify_system(accounts))
        
        print(f"\n🎉 {count} autotrade(s) ativado(s)!")
        print(f"👥 {len(accounts)} conta(s) notificada(s) ao sistema")
        print("🔌 Conexões WebSocket serão estabelecidas automaticamente em breve")
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Erro ao ativar autotrades: {e}")
        sys.exit(1)
