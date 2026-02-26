"""Error handler for indicator calculations"""
from typing import Optional, Dict, Any, Callable
from functools import wraps
from loguru import logger
import traceback
import time


class IndicatorError(Exception):
    """Base exception for indicator errors"""
    pass


class InvalidDataError(IndicatorError):
    """Raised when input data is invalid"""
    pass


class CalculationError(IndicatorError):
    """Raised when calculation fails"""
    pass


class ParameterError(IndicatorError):
    """Raised when parameters are invalid"""
    pass


def handle_indicator_errors(
    indicator_name: str,
    fallback_value: Any = None,
    log_errors: bool = True,
    raise_on_error: bool = False
):
    """
    Decorator to handle indicator calculation errors gracefully
    
    Args:
        indicator_name: Name of the indicator for logging
        fallback_value: Value to return on error (default: None)
        log_errors: Whether to log errors (default: True)
        raise_on_error: Whether to raise exception on error (default: False)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (ValueError, TypeError, ZeroDivisionError, InvalidDataError) as e:
                error_msg = f"{indicator_name}: {type(e).__name__} - {str(e)}"
                
                if log_errors:
                    logger.error(error_msg)
                    logger.debug(f"Traceback:\n{traceback.format_exc()}")
                
                if raise_on_error:
                    raise CalculationError(error_msg) from e
                
                return fallback_value
            except Exception as e:
                error_msg = f"{indicator_name}: Unexpected error - {str(e)}"
                
                if log_errors:
                    logger.error(error_msg)
                    logger.debug(f"Traceback:\n{traceback.format_exc()}")
                
                if raise_on_error:
                    raise IndicatorError(error_msg) from e
                
                return fallback_value
        
        return wrapper
    return decorator


def validate_dataframe(df, required_columns: list, min_rows: int = 0):
    """
    Validate DataFrame for indicator calculation
    
    Args:
        df: DataFrame to validate
        required_columns: List of required column names
        min_rows: Minimum number of rows required
    
    Raises:
        InvalidDataError: If DataFrame is invalid
    """
    if df is None:
        raise InvalidDataError("DataFrame is None")
    
    if not isinstance(df, type(df)):
        raise InvalidDataError(f"Expected DataFrame, got {type(df)}")
    
    if len(df) < min_rows:
        raise InvalidDataError(f"DataFrame has {len(df)} rows, minimum {min_rows} required")
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        raise InvalidDataError(f"Missing required columns: {missing_columns}")
    
    # Check for NaN values in required columns
    for col in required_columns:
        if df[col].isna().all():
            raise InvalidDataError(f"Column '{col}' contains only NaN values")


def safe_divide(numerator, denominator, default: float = 0.0):
    """
    Safe division with fallback value
    
    Args:
        numerator: Numerator value
        denominator: Denominator value
        default: Fallback value if division by zero
    
    Returns:
        Result of division or default value
    """
    try:
        if denominator == 0 or denominator is None:
            return default
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return default


class IndicatorHealthMonitor:
    """Monitor health and performance of indicators"""
    
    def __init__(self):
        self.indicator_stats: Dict[str, Dict[str, Any]] = {}
    
    def record_call(self, indicator_name: str, success: bool, execution_time: float):
        """
        Record a call to an indicator
        
        Args:
            indicator_name: Name of the indicator
            success: Whether the call was successful
            execution_time: Time taken to execute in seconds
        """
        if indicator_name not in self.indicator_stats:
            self.indicator_stats[indicator_name] = {
                'total_calls': 0,
                'successful_calls': 0,
                'failed_calls': 0,
                'total_time': 0.0,
                'avg_time': 0.0,
                'success_rate': 0.0
            }
        
        stats = self.indicator_stats[indicator_name]
        stats['total_calls'] += 1
        stats['total_time'] += execution_time
        
        if success:
            stats['successful_calls'] += 1
        else:
            stats['failed_calls'] += 1
        
        stats['success_rate'] = stats['successful_calls'] / stats['total_calls'] if stats['total_calls'] > 0 else 0.0
        stats['avg_time'] = stats['total_time'] / stats['total_calls']
    
    def get_stats(self, indicator_name: str) -> Optional[Dict[str, Any]]:
        """Get statistics for an indicator"""
        return self.indicator_stats.get(indicator_name)
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all indicators"""
        return self.indicator_stats
    
    def reset_stats(self, indicator_name: Optional[str] = None):
        """Reset statistics for an indicator or all indicators"""
        if indicator_name:
            self.indicator_stats.pop(indicator_name, None)
        else:
            self.indicator_stats.clear()


# Global health monitor instance
health_monitor = IndicatorHealthMonitor()


def monitor_indicator_performance(indicator_name: str):
    """
    Decorator to monitor indicator performance
    
    Args:
        indicator_name: Name of the indicator
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            finally:
                execution_time = time.time() - start_time
                health_monitor.record_call(indicator_name, success, execution_time)
        
        return wrapper
    return decorator
