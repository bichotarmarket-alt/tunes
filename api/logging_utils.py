"""Logging utilities for API endpoints"""
from loguru import logger
from typing import Optional


def log_request(endpoint: str, method: str, user_id: Optional[str] = None, details: Optional[dict] = None):
    """
    Log API request in a standardized format
    
    Args:
        endpoint: API endpoint path
        method: HTTP method (GET, POST, etc.)
        user_id: User ID if authenticated
        details: Additional details to log
    """
    user_info = f" | user={user_id}" if user_id else ""
    details_info = f" | {details}" if details else ""
    logger.info(f"[API] {method} {endpoint}{user_info}{details_info}")


def log_error(endpoint: str, method: str, error: Exception, user_id: Optional[str] = None):
    """
    Log API error in a standardized format
    
    Args:
        endpoint: API endpoint path
        method: HTTP method
        error: Exception that occurred
        user_id: User ID if authenticated
    """
    user_info = f" | user={user_id}" if user_id else ""
    logger.error(f"[API] {method} {endpoint} - ERROR{user_info}: {str(error)}", exc_info=True)


def log_success(endpoint: str, method: str, message: str, user_id: Optional[str] = None):
    """
    Log API success in a standardized format
    
    Args:
        endpoint: API endpoint path
        method: HTTP method
        message: Success message
        user_id: User ID if authenticated
    """
    user_info = f" | user={user_id}" if user_id else ""
    logger.success(f"[API] {method} {endpoint} - SUCCESS{user_info}: {message}")


def log_warning(endpoint: str, method: str, message: str, user_id: Optional[str] = None):
    """
    Log API warning in a standardized format
    
    Args:
        endpoint: API endpoint path
        method: HTTP method
        message: Warning message
        user_id: User ID if authenticated
    """
    user_info = f" | user={user_id}" if user_id else ""
    logger.warning(f"[API] {method} {endpoint} - WARNING{user_info}: {message}")


def log_info(endpoint: str, method: str, message: str, user_id: Optional[str] = None):
    """
    Log API info in a standardized format
    
    Args:
        endpoint: API endpoint path
        method: HTTP method
        message: Info message
        user_id: User ID if authenticated
    """
    user_info = f" | user={user_id}" if user_id else ""
    logger.info(f"[API] {method} {endpoint} - INFO{user_info}: {message}")
