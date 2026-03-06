"""
Serviço de cache em memória OTIMIZADO para reduzir queries no banco de dados
Ideal para sistemas com 1000+ usuários no Railway (sem Redis)

Features:
- LRU eviction (Least Recently Used)
- Max size limit (evita estouro de memória)
- TTL (Time To Live) por entrada
- Thread-safe com asyncio.Lock
"""
import time
import asyncio
from typing import Any, Optional, Callable, Dict
from collections import OrderedDict
from loguru import logger
from functools import wraps


class MemoryCache:
    """
    Cache LRU em memória com TTL e limite de tamanho.
    
    Quando atinge max_size, remove as entradas mais antigas (LRU).
    Quando TTL expira, entrada é removida no próximo get.
    """
    
    def __init__(self, max_size: int = 10000, default_ttl: int = 300):
        """
        Args:
            max_size: Número máximo de entradas no cache (padrão: 10k)
            default_ttl: TTL padrão em segundos (padrão: 5 min)
        """
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Busca valor do cache se não expirou. Atualiza LRU."""
        async with self._lock:
            if key not in self._cache:
                return None
            
            entry = self._cache[key]
            if entry['expires_at'] < time.time():
                del self._cache[key]
                return None
            
            # Move para o final (mais recente no LRU)
            self._cache.move_to_end(key)
            return entry['value']
    
    async def set(self, key: str, value: Any, ttl_seconds: int = None):
        """Armazena valor no cache com TTL. Evita se exceder max_size."""
        if ttl_seconds is None:
            ttl_seconds = self._default_ttl
            
        async with self._lock:
            # Se já existe, atualiza e move para o final
            if key in self._cache:
                self._cache[key] = {
                    'value': value,
                    'expires_at': time.time() + ttl_seconds,
                    'created_at': time.time()
                }
                self._cache.move_to_end(key)
                return
            
            # Se atingiu limite, remove o mais antigo (LRU)
            if len(self._cache) >= self._max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                logger.debug(f"Cache LRU eviction: removed {oldest_key}")
            
            # Adiciona nova entrada
            self._cache[key] = {
                'value': value,
                'expires_at': time.time() + ttl_seconds,
                'created_at': time.time()
            }
    
    async def delete(self, key: str):
        """Remove chave do cache"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
    
    async def clear(self):
        """Limpa todo o cache"""
        async with self._lock:
            self._cache.clear()
    
    async def clear_pattern(self, pattern: str):
        """Limpa chaves que contêm o padrão"""
        async with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_delete:
                del self._cache[key]
            return len(keys_to_delete)
    
    def get_stats(self) -> Dict[str, int]:
        """Retorna estatísticas do cache"""
        now = time.time()
        valid_entries = sum(1 for v in self._cache.values() if v['expires_at'] > now)
        expired_entries = len(self._cache) - valid_entries
        
        return {
            'total_entries': len(self._cache),
            'valid_entries': valid_entries,
            'expired_entries': expired_entries
        }


# Instância global do cache - limitado a 10k entradas (ajustar conforme memória disponível)
# Para 1000 usuários, isso permite ~10 entradas por usuário em média
memory_cache = MemoryCache(max_size=10000, default_ttl=300)


def cached(ttl_seconds: int = None, key_prefix: str = ""):
    """Decorator para cachear resultados de funções async"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Gerar chave baseada nos argumentos
            cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"
            
            # Tentar buscar do cache
            cached_value = await memory_cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_value
            
            # Executar função e armazenar no cache
            result = await func(*args, **kwargs)
            await memory_cache.set(cache_key, result, ttl_seconds)
            logger.debug(f"Cache MISS: {cache_key}")
            return result
        
        return wrapper
    return decorator


def invalidate_cache(pattern: str):
    """Invalida chaves do cache que contêm o padrão"""
    async def _invalidate():
        count = await memory_cache.clear_pattern(pattern)
        logger.info(f"Invalidated {count} cache entries with pattern: {pattern}")
        return count
    
    # Retorna coroutine para ser awaited
    return _invalidate()


# Cache específico para dados frequentes
class DataCache:
    """Cache estruturado para dados específicos do TunesTrade"""
    
    @staticmethod
    async def get_user_strategies(user_id: str) -> Optional[list]:
        """Busca estratégias do usuário do cache"""
        return await memory_cache.get(f"user:{user_id}:strategies")
    
    @staticmethod
    async def set_user_strategies(user_id: str, strategies: list, ttl: int = 120):
        """Armazena estratégias do usuário no cache"""
        await memory_cache.set(f"user:{user_id}:strategies", strategies, ttl)
    
    @staticmethod
    async def get_user_stats(user_id: str) -> Optional[dict]:
        """Busca estatísticas do usuário do cache"""
        return await memory_cache.get(f"user:{user_id}:stats")
    
    @staticmethod
    async def set_user_stats(user_id: str, stats: dict, ttl: int = 300):
        """Armazena estatísticas do usuário no cache"""
        await memory_cache.set(f"user:{user_id}:stats", stats, ttl)
    
    @staticmethod
    async def get_indicator_rankings(user_id: str) -> Optional[list]:
        """Busca rankings de indicadores do cache"""
        return await memory_cache.get(f"user:{user_id}:rankings")
    
    @staticmethod
    async def set_indicator_rankings(user_id: str, rankings: list, ttl: int = 600):
        """Armazena rankings de indicadores no cache"""
        await memory_cache.set(f"user:{user_id}:rankings", rankings, ttl)
    
    @staticmethod
    async def invalidate_user_data(user_id: str):
        """Invalida todos os dados em cache de um usuário"""
        pattern = f"user:{user_id}:"
        count = await memory_cache.clear_pattern(pattern)
        logger.info(f"Invalidated {count} cache entries for user {user_id}")
        return count


# Instância global
data_cache = DataCache()
