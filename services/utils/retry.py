"""Retry mechanism for resilient connections"""
import asyncio
from typing import Callable, Optional, Type, Tuple, Any
from functools import wraps
from loguru import logger
import time


class RetryConfig:
    """Configuration for retry behavior"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_backoff: bool = True,
        jitter: bool = True
    ):
        """
        Initialize retry configuration
        
        Args:
            max_attempts: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
            exponential_backoff: Whether to use exponential backoff
            jitter: Whether to add jitter to delay
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_backoff = exponential_backoff
        self.jitter = jitter


class RetryableError(Exception):
    """Base exception for retryable errors"""
    pass


class ConnectionError(RetryableError):
    """Connection error that can be retried"""
    pass


class TimeoutError(RetryableError):
    """Timeout error that can be retried"""
    pass


def retry_on_exception(
    config: RetryConfig,
    exceptions: Tuple[Type[Exception], ...] = (RetryableError,),
    on_retry: Optional[Callable] = None
):
    """
    Decorator to retry function on exception
    
    Args:
        config: Retry configuration
        exceptions: Tuple of exception types to retry on
        on_retry: Callback function called on each retry
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts - 1:
                        logger.error(f"Max retries ({config.max_attempts}) reached for {func.__name__}")
                        raise
                    
                    # Calculate delay
                    delay = _calculate_delay(attempt, config)
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {str(e)}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    # Call on_retry callback if provided
                    if on_retry:
                        await on_retry(attempt + 1, e)
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == config.max_attempts - 1:
                        logger.error(f"Max retries ({config.max_attempts}) reached for {func.__name__}")
                        raise
                    
                    # Calculate delay
                    delay = _calculate_delay(attempt, config)
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{config.max_attempts} failed for {func.__name__}: {str(e)}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    # Call on_retry callback if provided
                    if on_retry:
                        on_retry(attempt + 1, e)
                    
                    # Wait before retry
                    time.sleep(delay)
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def _calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate delay for retry attempt
    
    Args:
        attempt: Current attempt number (0-indexed)
        config: Retry configuration
    
    Returns:
        float: Delay in seconds
    """
    delay = config.base_delay
    
    if config.exponential_backoff:
        delay = config.base_delay * (2 ** attempt)
    
    # Cap at max delay
    delay = min(delay, config.max_delay)
    
    # Add jitter
    if config.jitter:
        import random
        jitter = random.uniform(0.1, 0.3) * delay
        delay += jitter
    
    return delay


# Default retry configuration for different scenarios
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
    exponential_backoff=True,
    jitter=True
)

CONNECTION_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=2.0,
    max_delay=60.0,
    exponential_backoff=True,
    jitter=True
)

API_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=0.5,
    max_delay=10.0,
    exponential_backoff=True,
    jitter=True
)
