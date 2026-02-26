"""
CSRF Protection Middleware
"""

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from typing import Optional
import secrets
import time


class CSRFProtection:
    """CSRF protection middleware"""
    
    def __init__(self):
        self.tokens: dict = {}
        self.token_expiry = 3600  # 1 hour
    
    def generate_token(self) -> str:
        """Generate a new CSRF token
        
        Returns:
            str: CSRF token
        """
        token = secrets.token_urlsafe(32)
        self.tokens[token] = time.time()
        return token
    
    def validate_token(self, token: str) -> bool:
        """Validate CSRF token
        
        Args:
            token: CSRF token to validate
            
        Returns:
            bool: True if token is valid
        """
        if not token or token not in self.tokens:
            return False
        
        # Check if token is expired
        if time.time() - self.tokens[token] > self.token_expiry:
            del self.tokens[token]
            return False
        
        return True
    
    def cleanup_expired_tokens(self):
        """Remove expired tokens"""
        now = time.time()
        expired_tokens = [
            token for token, timestamp in self.tokens.items()
            if now - timestamp > self.token_expiry
        ]
        for token in expired_tokens:
            del self.tokens[token]


# Global CSRF protection instance
csrf_protection = CSRFProtection()


async def csrf_middleware(
    request: Request,
    call_next
):
    """CSRF protection middleware
    
    Adds CSRF protection to state-changing requests
    
    Args:
        request: FastAPI request
        call_next: Next middleware or route handler
        
    Returns:
        Response
    """
    # Skip CSRF for GET, HEAD, OPTIONS requests
    if request.method in ["GET", "HEAD", "OPTIONS"]:
        return await call_next(request)
    
    # Skip CSRF for API endpoints that use JWT
    if "/api/" in request.url.path:
        return await call_next(request)
    
    # Skip CSRF for WebSocket connections
    if "/ws/" in request.url.path:
        return await call_next(request)
    
    # Check for CSRF token in state-changing requests
    csrf_token = request.headers.get("X-CSRF-Token") or request.cookies.get("csrf_token")
    
    if not csrf_token or not csrf_protection.validate_token(csrf_token):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "detail": "CSRF token missing or invalid",
                "error": "csrf_token_invalid"
            }
        )
    
    # Clean up expired tokens
    csrf_protection.cleanup_expired_tokens()
    
    return await call_next(request)


def get_csrf_token() -> str:
    """Generate a new CSRF token
    
    Returns:
        str: CSRF token
    """
    return csrf_protection.generate_token()
