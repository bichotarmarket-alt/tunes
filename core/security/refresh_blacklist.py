"""Refresh token blacklist management"""
from typing import Set
import hashlib
from core.cache import cache_get, cache_set, cache_delete, cache_exists


class RefreshTokenBlacklist:
    """Blacklist for refresh tokens to prevent reuse after logout"""
    
    _cache_prefix = "refresh_blacklist:"
    _cache_ttl = 7 * 24 * 60 * 60  # 7 days
    
    @classmethod
    def _get_key(cls, refresh_token: str) -> str:
        """Generate cache key for refresh token"""
        # Hash the token to avoid storing sensitive data
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        return f"{cls._cache_prefix}{token_hash}"
    
    @classmethod
    async def add(cls, refresh_token: str) -> bool:
        """Add refresh token to blacklist"""
        key = cls._get_key(refresh_token)
        return await cache_set(key, "blacklisted", ttl=cls._cache_ttl)
    
    @classmethod
    async def is_blacklisted(cls, refresh_token: str) -> bool:
        """Check if refresh token is blacklisted"""
        key = cls._get_key(refresh_token)
        return await cache_exists(key)
    
    @classmethod
    async def remove(cls, refresh_token: str) -> bool:
        """Remove refresh token from blacklist"""
        key = cls._get_key(refresh_token)
        return await cache_delete(key)
    
    @classmethod
    async def clear_all(cls) -> bool:
        """Clear all blacklisted tokens"""
        cache = __import__('core.cache').cache.get_cache()
        return await cache.clear()


refresh_token_blacklist = RefreshTokenBlacklist()
