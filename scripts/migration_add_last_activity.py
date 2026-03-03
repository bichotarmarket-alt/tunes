"""
Migração: Adicionar coluna last_activity_timestamp na tabela accounts
Execute: python scripts/migration_add_last_activity.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.database import get_db_context
from sqlalchemy import text
from loguru import logger


async def migrate():
    """Adicionar coluna last_activity_timestamp na tabela accounts"""
    logger.info("🔧 Executando migração...")
    
    async with get_db_context() as db:
        # Verificar se coluna já existe
        try:
            result = await db.execute(
                text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'accounts' AND column_name = 'last_activity_timestamp'
                """)
            )
            exists = result.fetchone()
            
            if exists:
                logger.info("✅ Coluna last_activity_timestamp já existe!")
                return
            
            # Adicionar coluna
            await db.execute(
                text("""
                    ALTER TABLE accounts 
                    ADD COLUMN last_activity_timestamp TIMESTAMP DEFAULT NOW()
                """)
            )
            await db.commit()
            logger.success("✅ Coluna last_activity_timestamp adicionada com sucesso!")
            
        except Exception as e:
            logger.error(f"❌ Erro na migração: {e}")
            await db.rollback()
            raise


if __name__ == "__main__":
    try:
        asyncio.run(migrate())
        print("\n🎉 Migração concluída!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        sys.exit(1)
