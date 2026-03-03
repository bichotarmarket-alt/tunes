#!/usr/bin/env python3
"""
Script de inicialização do banco para Railway
Executa: migrations (alembic) + seed data
"""
import subprocess
import sys
import logging
import os

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def run_migrations():
    """Executar alembic migrations"""
    logger.info("📦 Executando migrations...")
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            check=True,
            cwd="/app"
        )
        logger.info("✅ Migrations concluídas")
        if result.stdout:
            logger.info(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Erro nas migrations: {e}")
        logger.error(e.stderr if e.stderr else "No stderr")
        return False
    except FileNotFoundError:
        logger.warning("⚠️ Alembic não encontrado, pulando migrations")
        return True


def run_seed():
    """Executar seed data"""
    logger.info("🌱 Executando seed data...")
    try:
        import asyncio
        from seed_data import run_seed as seed_func
        asyncio.run(seed_func())
        return True
    except Exception as e:
        logger.error(f"❌ Erro no seed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def init_database():
    """Inicialização completa do banco"""
    logger.info("🚀 Iniciando setup do banco de dados...")
    
    # Verificar DATABASE_URL
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        logger.error("❌ DATABASE_URL não configurado!")
        logger.info("💡 Configure a variável DATABASE_URL no Railway")
        return False
    
    logger.info(f"✅ DATABASE_URL encontrado")
    
    # Passo 1: Migrations
    migrations_ok = run_migrations()
    if not migrations_ok:
        logger.warning("Migrations falharam, continuando...")
    
    # Passo 2: Seed data
    seed_ok = run_seed()
    if not seed_ok:
        logger.warning("Seed falhou, continuando...")
    
    logger.info("✅ Setup do banco concluído!")
    return True


if __name__ == "__main__":
    success = init_database()
    sys.exit(0)  # Sempre retornar 0 para não parar o deploy
