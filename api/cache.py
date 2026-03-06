"""Módulo de cache Redis para o backend."""
import json
import pickle
from typing import Any, Optional, Union
from functools import wraps
from datetime import timedelta

import redis.asyncio as redis
from loguru import logger

from core.config import settings


class RedisCache:
    """Cliente Redis para cache distribuído."""
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._is_connected = False
    
    async def connect(self) -> bool:
        """Conecta ao Redis."""
        try:
            redis_url = getattr(settings, 'REDIS_URL', None)
            
            if redis_url:
                self._client = redis.from_url(
                    redis_url,
                    decode_responses=False,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30
                )
            else:
                # Fallback para localhost (desenvolvimento)
                self._client = redis.Redis(
                    host=getattr(settings, 'REDIS_HOST', 'localhost'),
                    port=getattr(settings, 'REDIS_PORT', 6379),
                    db=getattr(settings, 'REDIS_DB', 0),
                    password=getattr(settings, 'REDIS_PASSWORD', None),
                    decode_responses=False,
                    socket_connect_timeout=5,
                    socket_keepalive=True,
                    health_check_interval=30
                )
            
            # Testar conexão
            await self._client.ping()
            self._is_connected = True
            logger.info("✅ Redis conectado com sucesso")
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Redis não disponível: {e}")
            self._is_connected = False
            return False
    
    async def disconnect(self):
        """Desconecta do Redis."""
        if self._client:
            await self._client.close()
            self._is_connected = False
            logger.info("🔌 Redis desconectado")
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Obtém valor do cache."""
        if not self._is_connected or not self._client:
            return default
        
        try:
            data = await self._client.get(key)
            if data is None:
                return default
            return pickle.loads(data)
        except Exception as e:
            logger.debug(f"Erro ao ler cache: {e}")
            return default
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[Union[int, timedelta]] = None
    ) -> bool:
        """Define valor no cache."""
        if not self._is_connected or not self._client:
            return False
        
        try:
            serialized = pickle.dumps(value)
            
            if ttl:
                if isinstance(ttl, timedelta):
                    ttl = int(ttl.total_seconds())
                await self._client.setex(key, ttl, serialized)
            else:
                await self._client.set(key, serialized)
            
            return True
        except Exception as e:
            logger.debug(f"Erro ao escrever cache: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Remove chave do cache."""
        if not self._is_connected or not self._client:
            return False
        
        try:
            await self._client.delete(key)
            return True
        except Exception:
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Remove chaves por pattern."""
        if not self._is_connected or not self._client:
            return 0
        
        try:
            keys = await self._client.keys(pattern)
            if keys:
                return await self._client.delete(*keys)
            return 0
        except Exception:
            return 0
    
    async def exists(self, key: str) -> bool:
        """Verifica se chave existe."""
        if not self._is_connected or not self._client:
            return False
        
        try:
            return await self._client.exists(key) > 0
        except Exception:
            return False
    
    async def ttl(self, key: str) -> int:
        """Retorna TTL restante da chave."""
        if not self._is_connected or not self._client:
            return -1
        
        try:
            return await self._client.ttl(key)
        except Exception:
            return -1
    
    async def expire(self, key: str, ttl: Union[int, timedelta]) -> bool:
        """Define TTL em chave existente."""
        if not self._is_connected or not self._client:
            return False
        
        try:
            if isinstance(ttl, timedelta):
                ttl = int(ttl.total_seconds())
            return await self._client.expire(key, ttl)
        except Exception:
            return False


# Instância global do cache
cache = RedisCache()


async def init_cache():
    """Inicializa o cache na startup."""
    await cache.connect()


async def close_cache():
    """Fecha o cache na shutdown."""
    await cache.disconnect()


def cached(
    ttl: Optional[Union[int, timedelta]] = 300,
    key_prefix: str = "",
    key_builder: Optional[callable] = None
):
    """
    Decorator para cachear resultados de funções.
    
    Args:
        ttl: Tempo de vida em segundos ou timedelta
        key_prefix: Prefixo para a chave do cache
        key_builder: Função opcional para construir chave customizada
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Construir chave do cache
            if key_builder:
                cache_key = key_builder(*args, **kwargs)
            else:
                # Chave padrão: prefixo + nome da função + argumentos
                key_parts = [key_prefix or func.__module__, func.__name__]
                
                # Adicionar args serializáveis
                for arg in args[1:] if hasattr(args[0], '__class__') else args:  # Skip self/cls
                    if isinstance(arg, (str, int, float, bool)):
                        key_parts.append(str(arg))
                
                # Adicionar kwargs ordenados
                for k, v in sorted(kwargs.items()):
                    if isinstance(v, (str, int, float, bool)):
                        key_parts.append(f"{k}={v}")
                
                cache_key = ":".join(key_parts)
            
            # Tentar obter do cache
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache HIT: {cache_key}")
                return cached_value
            
            # Executar função
            result = await func(*args, **kwargs)
            
            # Salvar no cache
            await cache.set(cache_key, result, ttl)
            logger.debug(f"Cache SET: {cache_key}")
            
            return result
        
        # Adicionar método para invalidar cache
        async_wrapper.invalidate = lambda *a, **kw: cache.delete(
            key_builder(*a, **kw) if key_builder else f"{key_prefix or func.__module__}:{func.__name__}"
        )
        
        return async_wrapper
    return decorator


def invalidate_cache_pattern(pattern: str):
    """Invalida cache por pattern."""
    async def _invalidate():
        deleted = await cache.delete_pattern(pattern)
        logger.info(f"Cache invalidado: {pattern} ({deleted} chaves)")
        return deleted
    return _invalidate
