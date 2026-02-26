"""Redis cache para candles"""
from typing import List, Dict, Any, Optional
from loguru import logger
from services.redis_client import redis_client


class CandlesCache:
    """Cache para candles usando Redis"""

    def __init__(self, ttl: int = 300):
        """
        Initialize cache

        Args:
            ttl: Time to live in seconds (default: 5 minutos)
        """
        self.ttl = ttl
        self._prefix = "candles_cache:"

    async def get(self, asset: str, timeframe: int) -> Optional[List[Dict[str, Any]]]:
        """
        Obter candles do cache

        Args:
            asset: Símbolo do asset
            timeframe: Timeframe em segundos

        Returns:
            Lista de candles ou None
        """
        key = f"{self._prefix}{asset}_{timeframe}"
        candles = await redis_client.get_json(key)

        if candles is None:
            return None

        logger.debug(f"Cache hit para candles: {asset} {timeframe}s ({len(candles)} candles)")
        return candles

    async def set(self, asset: str, timeframe: int, candles: List[Dict[str, Any]]):
        """
        Definir candles no cache

        Args:
            asset: Símbolo do asset
            timeframe: Timeframe em segundos
            candles: Lista de candles
        """
        key = f"{self._prefix}{asset}_{timeframe}"
        await redis_client.set_json(key, candles, ttl=self.ttl)
        logger.debug(f"Cache set para candles: {asset} {timeframe}s ({len(candles)} candles)")

    async def invalidate(self, asset: str, timeframe: Optional[int] = None):
        """
        Invalidar cache de candles

        Args:
            asset: Símbolo do asset
            timeframe: Timeframe em segundos (opcional, se None invalida todos)
        """
        if timeframe:
            key = f"{self._prefix}{asset}_{timeframe}"
            await redis_client.delete(key)
            logger.debug(f"Cache invalidado: {asset} {timeframe}s")
        else:
            await redis_client.clear_pattern(f"{self._prefix}{asset}_*")
            logger.debug(f"Cache invalidado: {asset} (todos timeframes)")


# Instância global
candles_cache = CandlesCache()
