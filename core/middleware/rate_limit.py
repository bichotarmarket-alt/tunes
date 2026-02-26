"""
Rate Limiting Middleware
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Dict, Optional
import time
from collections import defaultdict
from functools import wraps
import asyncio

from core.config import settings
from core.security import decode_token


class RateLimiter:
    """Rate limiter using sliding window algorithm with per-key locks"""
    
    def __init__(self):
        self.requests: Dict[str, list] = defaultdict(list)
        self._locks: Dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()
    
    async def _get_lock(self, key: str) -> asyncio.Lock:
        """Get or create lock for a specific key"""
        async with self._global_lock:
            if key not in self._locks:
                self._locks[key] = asyncio.Lock()
            return self._locks[key]
    
    async def is_allowed(
        self,
        key: str,
        limit: int,
        window: int = 60
    ) -> bool:
        """Check if request is allowed within rate limit
        
        Args:
            key: Unique identifier (IP, user_id, etc.)
            limit: Maximum requests allowed
            window: Time window in seconds
            
        Returns:
            bool: True if request is allowed
        """
        lock = await self._get_lock(key)
        async with lock:
            now = time.time()
            # Remove requests outside the window
            self.requests[key] = [
                timestamp for timestamp in self.requests[key]
                if now - timestamp < window
            ]
            
            # Check if under limit
            if len(self.requests[key]) >= limit:
                return False
            
            # Add current request
            self.requests[key].append(now)
            return True


# Global rate limiter instance
rate_limiter = RateLimiter()


def _get_rate_limit_key(request: Request) -> tuple[str, bool]:
    """Obter chave de rate limit e status de autenticação."""
    client_ip = request.client.host if request.client else "unknown"
    auth_header = request.headers.get("authorization")

    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            payload = decode_token(parts[1])
            subject = payload.get("sub") if payload else None
            if subject:
                return f"user:{subject}", True

    return f"ip:{client_ip}", False


async def rate_limit_middleware(
    request: Request,
    call_next,
):
    """Rate limiting middleware
    
    Args:
        request: FastAPI request
        call_next: Next middleware or route handler
        
    Returns:
        Response
    """
    # Bypass WebSocket connections
    if request.url.path.startswith("/ws/"):
        return await call_next(request)
    
    key, is_authenticated = _get_rate_limit_key(request)
    
    # Get rate limit based on authentication status
    limit = settings.RATE_LIMIT_PER_MINUTE_AUTH if is_authenticated else settings.RATE_LIMIT_PER_MINUTE
    
    # Check rate limit
    if not await rate_limiter.is_allowed(key, limit):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "Too many requests",
                "error": "rate_limit_exceeded",
                "retry_after": 60
            },
            headers={
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + 60)
            }
        )
    
    response = await call_next(request)
    
    # Add rate limit headers
    remaining = max(limit - len(rate_limiter.requests[key]), 0)
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
    
    return response


def rate_limit(limit: int = 100, window: int = 60):
    """Decorator for rate limiting specific endpoints
    
    Args:
        limit: Maximum requests allowed
        window: Time window in seconds
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Get request from first argument (usually self)
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            if not request:
                return await func(*args, **kwargs)
            
            key, _ = _get_rate_limit_key(request)

            if not await rate_limiter.is_allowed(key, limit, window):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests"
                )
            
            return await func(*args, **kwargs)
        
        return wrapper
    return decorator
