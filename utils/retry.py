"""Utilitário para retry com timeout em operações de banco de dados"""
import asyncio
from functools import wraps
from typing import Callable, Any
from loguru import logger
from sqlalchemy.exc import OperationalError


def retry_on_db_lock(max_retries: int = 3, retry_delay: float = 1.0, timeout: float = 10.0):
    """
    Decorator para retry operações de banco de dados com timeout
    
    Args:
        max_retries: Número máximo de tentativas (default: 3)
        retry_delay: Tempo de espera entre tentativas em segundos (default: 1.0)
        timeout: Timeout máximo para cada tentativa em segundos (default: 10.0)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            for attempt in range(max_retries):
                try:
                    # Executar com timeout
                    result = await asyncio.wait_for(
                        func(*args, **kwargs),
                        timeout=timeout
                    )
                    return result
                except asyncio.TimeoutError:
                    logger.warning(f"[DB] Timeout ao executar {func.__name__} (tentativa {attempt + 1}/{max_retries})")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        logger.error(f"[DB] Timeout após {max_retries} tentativas em {func.__name__}")
                        raise
                except OperationalError as e:
                    if 'database is locked' in str(e):
                        logger.warning(f"[DB] Database locked ao executar {func.__name__} (tentativa {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            logger.error(f"[DB] Database locked após {max_retries} tentativas em {func.__name__}")
                            raise
                    else:
                        # Outros erros de banco de dados, não fazer retry
                        logger.error(f"[DB] Erro de banco de dados em {func.__name__}: {e}")
                        raise
                except Exception as e:
                    logger.error(f"[DB] Erro inesperado ao executar {func.__name__}: {e}")
                    raise
        return wrapper
    return decorator


def retry_sync_on_db_lock(max_retries: int = 3, retry_delay: float = 1.0):
    """
    Decorator para retry operações síncronas de banco de dados
    
    Args:
        max_retries: Número máximo de tentativas (default: 3)
        retry_delay: Tempo de espera entre tentativas em segundos (default: 1.0)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            for attempt in range(max_retries):
                try:
                    result = func(*args, **kwargs)
                    return result
                except OperationalError as e:
                    if 'database is locked' in str(e):
                        logger.warning(f"[DB] Database locked ao executar {func.__name__} (tentativa {attempt + 1}/{max_retries})")
                        if attempt < max_retries - 1:
                            import time
                            time.sleep(retry_delay)
                            continue
                        else:
                            logger.error(f"[DB] Database locked após {max_retries} tentativas em {func.__name__}")
                            raise
                    else:
                        # Outros erros de banco de dados, não fazer retry
                        logger.error(f"[DB] Erro de banco de dados em {func.__name__}: {e}")
                        raise
                except Exception as e:
                    logger.error(f"[DB] Erro inesperado ao executar {func.__name__}: {e}")
                    raise
        return wrapper
    return decorator
