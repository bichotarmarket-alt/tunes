"""Cache management using Redis or in-memory fallback"""
from typing import Optional, Any
import asyncio
import json
from core.config import settings


class CacheBackend:
    """Cache backend interface"""
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        raise NotImplementedError
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        raise NotImplementedError
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        raise NotImplementedError
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        raise NotImplementedError
    
    async def clear(self) -> bool:
        """Clear all cache"""
        raise NotImplementedError


class InMemoryCache(CacheBackend):
    """In-memory cache fallback when Redis is not available"""
    
    def __init__(self):
        self._cache: dict = {}
        self._ttl: dict = {}
        self._lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        async with self._lock:
            if key not in self._cache:
                return None

            # Check TTL
            if key in self._ttl:
                import time
                if time.time() > self._ttl[key]:
                    self._cache.pop(key, None)
                    self._ttl.pop(key, None)
                    return None

            return self._cache[key]
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        async with self._lock:
            self._cache[key] = value

            if ttl:
                import time
                self._ttl[key] = time.time() + ttl

            return True
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        async with self._lock:
            self._cache.pop(key, None)
            self._ttl.pop(key, None)
            return True
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        async with self._lock:
            return key in self._cache
    
    async def clear(self) -> bool:
        """Clear all cache"""
        async with self._lock:
            self._cache.clear()
            self._ttl.clear()
            return True


class RedisCache(CacheBackend):
    """Redis cache backend"""
    
    def __init__(self):
        self._redis = None
        self._enabled = settings.REDIS_ENABLED
        
        if self._enabled:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
            except ImportError:
                self._enabled = False
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        if not self._enabled or not self._redis:
            return None
        
        try:
            value = await self._redis.get(key)
            if value is None:
                return None
            
            # Try to parse as JSON
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        except Exception:
            return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache"""
        if not self._enabled or not self._redis:
            return False
        
        try:
            # Serialize to JSON if needed
            if not isinstance(value, (str, int, float, bool)):
                value = json.dumps(value)
            
            if ttl:
                await self._redis.setex(key, ttl, value)
            else:
                await self._redis.set(key, value)
            
            return True
        except Exception:
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache"""
        if not self._enabled or not self._redis:
            return False
        
        try:
            await self._redis.delete(key)
            return True
        except Exception:
            return False
    
    async def exists(self, key: str) -> bool:
        """Check if key exists"""
        if not self._enabled or not self._redis:
            return False
        
        try:
            return await self._redis.exists(key) > 0
        except Exception:
            return False
    
    async def clear(self) -> bool:
        """Clear all cache"""
        if not self._enabled or not self._redis:
            return False
        
        try:
            await self._redis.flushdb()
            return True
        except Exception:
            return False


# Global cache instance
_cache_backend: Optional[CacheBackend] = None


def get_cache() -> CacheBackend:
    """Get cache backend instance"""
    global _cache_backend
    
    if _cache_backend is None:
        if settings.REDIS_ENABLED:
            _cache_backend = RedisCache()
        else:
            _cache_backend = InMemoryCache()
    
    return _cache_backend


async def cache_get(key: str) -> Optional[Any]:
    """Get value from cache"""
    cache = get_cache()
    return await cache.get(key)


async def cache_set(key: str, value: Any, ttl: int = None) -> bool:
    """Set value in cache"""
    cache = get_cache()
    if ttl is None:
        ttl = settings.REDIS_CACHE_TTL
    return await cache.set(key, value, ttl)


async def cache_delete(key: str) -> bool:
    """Delete value from cache"""
    cache = get_cache()
    return await cache.delete(key)


async def cache_exists(key: str) -> bool:
    """Check if key exists in cache"""
    cache = get_cache()
    return await cache.exists(key)


async def cache_clear() -> bool:
    """Clear all cache"""
    cache = get_cache()
    return await cache.clear()
