"""Cache decorators for API endpoints"""
from functools import wraps
from typing import Callable, Any
from fastapi import Request
from core.cache import cache_get, cache_set
from loguru import logger


def cache_response(ttl: int = 60, key_prefix: str = None):
    """
    Decorator to cache API responses
    
    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Try to get request object for generating cache key
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            # Generate cache key
            if key_prefix:
                cache_key = f"{key_prefix}:{func.__name__}"
            else:
                cache_key = f"cache:{func.__name__}"
            
            # Add user ID to cache key if available
            current_user = kwargs.get('current_user')
            if current_user:
                cache_key = f"{cache_key}:{current_user.id}"
            
            # Try to get from cache
            cached = await cache_get(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit: {cache_key}")
                return cached
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            await cache_set(cache_key, result, ttl=ttl)
            logger.debug(f"Cache set: {cache_key} (TTL: {ttl}s)")
            
            return result
        return wrapper
    return decorator


def invalidate_cache(pattern: str):
    """
    Invalidate cache entries matching pattern
    
    Args:
        pattern: Pattern to match (e.g., "cache:users:*")
    """
    # This would require pattern matching in cache backend
    # For now, just log the invalidation
    logger.info(f"Cache invalidation requested: {pattern}")
