"""
Exponential Backoff Retry Decorator for Hyperliquid API Calls

This module provides a robust retry mechanism with exponential backoff
specifically designed to handle rate limiting (429 errors) and transient
network failures when interacting with the Hyperliquid API.

Author: NovaBot Team
Date: 2026-01-01
"""

import time
import random
from functools import wraps
from typing import Callable, Any, Tuple, Type


def exponential_backoff(
    max_retries: int = 5,
    base_delay: float = 1.0,
    max_delay: float = 32.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retry_on: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """
    Decorator that implements exponential backoff retry logic for API calls.
    
    This decorator is critical for preventing 429 Rate Limit errors from
    CloudFront when executing trades on Hyperliquid. It implements:
    - Exponential delay increase: 1s → 2s → 4s → 8s → 16s
    - Special handling for 429 errors (doubled delay)
    - Jitter to prevent thundering herd problem
    - Configurable retry behavior
    
    Args:
        max_retries: Maximum number of retry attempts (default: 5)
        base_delay: Initial delay in seconds (default: 1.0)
        max_delay: Maximum delay between retries in seconds (default: 32.0)
        exponential_base: Base for exponential calculation (default: 2.0)
        jitter: Add random jitter (±25%) to prevent synchronized retries (default: True)
        retry_on: Tuple of exception types to retry on (default: all exceptions)
    
    Returns:
        Decorated function with retry logic
    
    Example:
        >>> @exponential_backoff(max_retries=3, base_delay=2.0)
        ... def close_position(symbol: str):
        ...     return exchange.market_close(symbol)
        
        >>> # If the call fails with 429, it will retry with delays:
        >>> # Attempt 1: Immediate
        >>> # Attempt 2: Wait ~4s (2s base * 2x for 429)
        >>> # Attempt 3: Wait ~8s
        >>> # Attempt 4: Raise exception
    
    Raises:
        Exception: After max_retries exhausted, re-raises the last exception
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    # Execute the wrapped function
                    result = func(*args, **kwargs)
                    
                    # Log success if this was a retry
                    if attempt > 0:
                        print(f"✅ {func.__name__} succeeded on attempt {attempt + 1}")
                    
                    return result
                    
                except retry_on as e:
                    last_exception = e
                    
                    # Check if this is the last attempt
                    if attempt == max_retries:
                        print(f"❌ {func.__name__} failed after {max_retries + 1} attempts: {e}")
                        raise
                    
                    # Detect rate limit errors (429)
                    is_rate_limit = _is_rate_limit_error(e)
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter (±25% randomness) to prevent thundering herd
                    if jitter:
                        jitter_factor = 0.75 + random.random() * 0.5  # Range: 0.75 to 1.25
                        delay = delay * jitter_factor
                    
                    # Double delay for rate limit errors
                    if is_rate_limit:
                        delay *= 2.0
                        print(
                            f"⚠️ RATE LIMIT (429) detected in {func.__name__}, "
                            f"waiting {delay:.2f}s before retry {attempt + 2}/{max_retries + 1}"
                        )
                    else:
                        print(
                            f"⚠️ {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}), "
                            f"retrying in {delay:.2f}s: {e}"
                        )
                    
                    # Sleep before retry
                    time.sleep(delay)
            
            # This should never be reached, but just in case
            if last_exception:
                raise last_exception
            raise Exception(f"{func.__name__} failed after {max_retries + 1} retries")
        
        return wrapper
    return decorator


def _is_rate_limit_error(exception: Exception) -> bool:
    """
    Detect if an exception is a rate limit (429) error.
    
    Hyperliquid SDK may raise exceptions in various formats:
    - Exception((429, None, 'null', None, {...}))
    - Exception with .status_code attribute
    - String containing "429"
    
    Args:
        exception: The exception to check
    
    Returns:
        True if this is a 429 rate limit error, False otherwise
    """
    # Check tuple format: (429, None, 'null', None, {...})
    if hasattr(exception, 'args') and len(exception.args) > 0:
        first_arg = exception.args[0]
        
        # Direct tuple check
        if isinstance(first_arg, tuple) and len(first_arg) > 0:
            if first_arg[0] == 429:
                return True
        
        # Integer check
        if isinstance(first_arg, int) and first_arg == 429:
            return True
    
    # Check status_code attribute (some HTTP libraries)
    if hasattr(exception, 'status_code') and exception.status_code == 429:
        return True
    
    # Check string representation
    error_str = str(exception).lower()
    if '429' in error_str or 'rate limit' in error_str:
        return True
    
    return False


# Convenience decorators for common use cases

def critical_operation(func: Callable) -> Callable:
    """
    Decorator for critical operations (e.g., close_position, cancel_orders).
    Uses aggressive retry strategy: 5 retries, 2s base delay.
    
    Example:
        >>> @critical_operation
        ... def close_position(symbol: str):
        ...     return exchange.market_close(symbol)
    """
    return exponential_backoff(
        max_retries=5,
        base_delay=2.0,
        max_delay=32.0
    )(func)


def standard_operation(func: Callable) -> Callable:
    """
    Decorator for standard operations (e.g., execute_order, set_sl_tp).
    Uses moderate retry strategy: 3 retries, 1s base delay.
    
    Example:
        >>> @standard_operation
        ... def execute_order(symbol: str, side: str, size: float):
        ...     return exchange.market_open(symbol, side, size)
    """
    return exponential_backoff(
        max_retries=3,
        base_delay=1.0,
        max_delay=16.0
    )(func)


def lightweight_operation(func: Callable) -> Callable:
    """
    Decorator for lightweight operations (e.g., get_positions, cancel_single_order).
    Uses minimal retry strategy: 2 retries, 0.5s base delay.
    
    Example:
        >>> @lightweight_operation
        ... def get_positions():
        ...     return exchange.get_positions()
    """
    return exponential_backoff(
        max_retries=2,
        base_delay=0.5,
        max_delay=8.0
    )(func)
