"""
Security Headers Middleware
"""

from fastapi import Request, Response
from fastapi.responses import JSONResponse


async def security_headers_middleware(
    request: Request,
    call_next
):
    """Security headers middleware
    
    Adds security headers to all responses
    
    Args:
        request: FastAPI request
        call_next: Next middleware or route handler
        
    Returns:
        Response with security headers
    """
    # Bypass WebSocket connections - let them through without security headers
    if request.url.path.startswith("/ws/"):
        return await call_next(request)
    
    response = await call_next(request)
    
    # X-Content-Type-Options: Prevents MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # X-Frame-Options: Prevents clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    
    # X-XSS-Protection: XSS protection
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    # Content-Security-Policy: Prevents XSS and data injection
    csp = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self' data:; "
        "connect-src 'self' https://*.pocketoption.com; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "base-uri 'self'; "
        "block-all-mixed-content"
    )
    response.headers["Content-Security-Policy"] = csp
    
    # Strict-Transport-Security: Enforce HTTPS
    if request.url.scheme == "https":
        hsts = "max-age=31536000; includeSubDomains; preload"
        response.headers["Strict-Transport-Security"] = hsts
    
    # Referrer-Policy: Control referrer information
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Permissions-Policy: Control browser features
    permissions_policy = (
        "geolocation=(), "
        "microphone=(), "
        "camera=(), "
        "payment=(), "
        "usb=(), "
        "magnetometer=(), "
        "gyroscope=(), "
        "accelerometer=()"
    )
    response.headers["Permissions-Policy"] = permissions_policy
    
    # X-Permitted-Cross-Domain-Policies: Restrict cross-domain policies
    response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
    
    # Cache-Control for sensitive endpoints
    if request.url.path in ["/api/v1/auth/login", "/api/v1/auth/register"]:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, proxy-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    
    return response
