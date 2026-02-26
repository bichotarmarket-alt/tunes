"""Cache system for indicator calculations using Redis"""
from typing import Any, Dict, Optional
import hashlib
import json
from loguru import logger
from services.redis_client import redis_client


class IndicatorCache:
    """Cache for indicator calculations using Redis"""

    def __init__(self, max_size: int = 1000, ttl: int = 300):
        """
        Initialize indicator cache

        Args:
            max_size: Maximum number of cached items (Redis handles this)
            ttl: Time to live in seconds (default: 5 minutes)
        """
        self.max_size = max_size
        self.ttl = ttl
        self.hits = 0
        self.misses = 0
        self._prefix = "indicator_cache:"

    def _generate_key(self, indicator_name: str, params: Dict[str, Any], data_hash: str) -> str:
        """Generate cache key for indicator calculation"""
        # Sort params for consistent key generation
        try:
            sorted_params = json.dumps(params, sort_keys=True)
        except (TypeError, ValueError):
            sorted_params = str(sorted(params.items()))

        key_string = f"{indicator_name}:{sorted_params}:{data_hash}"
        key_hash = hashlib.md5(key_string.encode()).hexdigest()
        return f"{self._prefix}{key_hash}"

    async def get(self, indicator_name: str, params: Dict[str, Any], data_hash: str) -> Optional[Any]:
        """
        Get cached value from Redis

        Args:
            indicator_name: Name of the indicator
            params: Indicator parameters
            data_hash: Hash of the input data

        Returns:
            Cached value or None
        """
        key = self._generate_key(indicator_name, params, data_hash)

        value = await redis_client.get_json(key)

        if value is None:
            self.misses += 1
            return None

        self.hits += 1
        logger.debug(f"Cache hit for {indicator_name}: {self.hits}/{self.hits + self.misses}")
        return value

    async def set(self, indicator_name: str, params: Dict[str, Any], data_hash: str, value: Any):
        """
        Set cached value in Redis

        Args:
            indicator_name: Name of the indicator
            params: Indicator parameters
            data_hash: Hash of the input data
            value: Value to cache
        """
        key = self._generate_key(indicator_name, params, data_hash)

        await redis_client.set_json(key, value, ttl=self.ttl)
        logger.debug(f"Cache set for {indicator_name}")

    async def clear(self):
        """Clear all cache entries"""
        await redis_client.clear_pattern(f"{self._prefix}*")
        logger.info("🗑️ Indicator cache cleared")

    async def get_stats(self) -> Dict[str, int]:
        """Get cache statistics"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hits / (self.hits + self.misses) if (self.hits + self.misses) > 0 else 0
        }


# Global cache instance
indicator_cache = IndicatorCache()


def hash_dataframe(df) -> str:
    """
    Generate hash for DataFrame for caching

    Args:
        df: DataFrame to hash

    Returns:
        str: Hash string
    """
    import hashlib

    # Criar hash que inclui dados, nomes das colunas E índice
    h = hashlib.md5()

    # Adicionar nomes das colunas em ordem
    h.update(','.join(df.columns.tolist()).encode())

    # Adicionar índice para garantir unicidade
    h.update(df.index.to_numpy().tobytes())

    # Adicionar dados
    h.update(df.to_numpy().tobytes())

    return h.hexdigest()


async def cached_indicator(indicator_name: str):
    """
    Decorator to cache indicator calculations

    Args:
        indicator_name: Name of the indicator
    """
    def decorator(func):
        async def wrapper(self, data, **kwargs):
            # Gerar hash que inclui dados do DataFrame E parâmetros do indicador
            data_hash = hash_dataframe(data)

            # Incluir parâmetros da instância do indicador no cache key
            instance_params = {}
            if hasattr(self, 'period'):
                instance_params['period'] = self.period
            if hasattr(self, 'smooth'):
                instance_params['smooth'] = self.smooth
            if hasattr(self, 'dynamic_levels'):
                instance_params['dynamic_levels'] = self.dynamic_levels
            if hasattr(self, 'use_true_levels'):
                instance_params['use_true_levels'] = self.use_true_levels
            if hasattr(self, 'swing_period'):
                instance_params['swing_period'] = self.swing_period
            if hasattr(self, 'zone_strength'):
                instance_params['zone_strength'] = self.zone_strength
            if hasattr(self, 'zone_tolerance'):
                instance_params['zone_tolerance'] = self.zone_tolerance
            if hasattr(self, 'min_zone_width'):
                instance_params['min_zone_width'] = self.min_zone_width
            if hasattr(self, 'atr_multiplier'):
                instance_params['atr_multiplier'] = self.atr_multiplier
            if hasattr(self, 'fast'):
                instance_params['fast'] = self.fast
            if hasattr(self, 'slow'):
                instance_params['slow'] = self.slow
            if hasattr(self, 'signal'):
                instance_params['signal'] = self.signal
            if hasattr(self, 'k_period'):
                instance_params['k_period'] = self.k_period
            if hasattr(self, 'd_period'):
                instance_params['d_period'] = self.d_period
            if hasattr(self, 'std_dev'):
                instance_params['std_dev'] = self.std_dev

            # Combinar parâmetros da instância com kwargs
            all_params = {**instance_params, **kwargs}

            # Check cache
            cached_value = await indicator_cache.get(
                indicator_name,
                all_params,
                data_hash
            )

            if cached_value is not None:
                logger.debug(f"Cache hit for {indicator_name}")
                return cached_value

            # Calculate value
            result = await func(self, data, **kwargs)

            # Cache result
            await indicator_cache.set(
                indicator_name,
                all_params,
                data_hash,
                result
            )

            logger.debug(f"Cache miss for {indicator_name}, calculated and cached")
            return result

        return wrapper
    return decorator
