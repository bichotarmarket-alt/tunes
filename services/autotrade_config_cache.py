"""Redis cache para configurações de autotrade"""
from typing import Dict, List, Any, Optional
from loguru import logger
from services.redis_client import redis_client


class AutotradeConfigCache:
    """Cache para configurações de autotrade usando Redis"""

    def __init__(self, ttl: int = 1):
        """
        Initialize cache

        Args:
            ttl: Time to live in seconds (default: 1 segundo para sincronização rápida)
        """
        self.ttl = ttl
        self._prefix = "autotrade_config:"

    async def get_all_configs(self) -> Optional[Dict[str, List[Dict[str, Any]]]]:
        """
        Obter todas as configurações de autotrade do cache

        Returns:
            Dict com configurações ou None se não existir
        """
        key = f"{self._prefix}all"
        configs = await redis_client.get_json(key)

        if configs is None:
            return None

        logger.debug(f"Cache hit para configs: {len(configs)} configurações")
        return configs

    async def set_all_configs(self, configs: Dict[str, List[Dict[str, Any]]]):
        """
        Definir todas as configurações de autotrade no cache

        Args:
            configs: Dict com configurações
        """
        key = f"{self._prefix}all"
        await redis_client.set_json(key, configs, ttl=self.ttl)
        logger.debug(f"Cache set para configs: {len(configs)} configurações")

    async def invalidate(self):
        """Invalidar o cache de configurações"""
        await redis_client.clear_pattern(f"{self._prefix}*")
        logger.info("🔄 Cache de configs invalidado")

    async def get_timeframes(self) -> Optional[List[int]]:
        """
        Obter timeframes configurados do cache

        Returns:
            Lista de timeframes ou None
        """
        key = f"{self._prefix}timeframes"
        timeframes = await redis_client.get_json(key)

        if timeframes is None:
            return None

        logger.debug(f"Cache hit para timeframes: {timeframes}")
        return timeframes

    async def set_timeframes(self, timeframes: List[int]):
        """
        Definir timeframes configurados no cache

        Args:
            timeframes: Lista de timeframes
        """
        key = f"{self._prefix}timeframes"
        await redis_client.set_json(key, timeframes, ttl=self.ttl)
        logger.debug(f"Cache set para timeframes: {timeframes}")


# Instância global
autotrade_config_cache = AutotradeConfigCache()
