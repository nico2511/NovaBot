"""
Formatters utilities for notifications and display
"""

def format_price_for_notification(price: float, symbol: str = "") -> str:
    """
    Format price with appropriate decimals for Discord notifications
    
    Rules based on price magnitude:
    - < $0.001: 8 decimals (micro-caps)
    - $0.001 - $0.01: 6 decimals (very small)
    - $0.01 - $1: 4 decimals (small)
    - $1 - $100: 2 decimals (medium)
    - > $100: 2 decimals with comma separator (large)
    
    Args:
        price: Price value to format
        symbol: Optional symbol for context
        
    Returns:
        Formatted price string with $ prefix
        
    Examples:
        >>> format_price_for_notification(0.00032)
        '$0.00032000'
        >>> format_price_for_notification(0.31716)
        '$0.3172'
        >>> format_price_for_notification(26.131)
        '$26.13'
        >>> format_price_for_notification(87834.0)
        '$87,834.00'
    """
    if price == 0:
        return "$0.00"
    
    abs_price = abs(price)
    
    if abs_price < 0.001:
        # Micro-caps: 8 decimals
        return f"${price:.8f}"
    elif abs_price < 0.01:
        # Very small: 6 decimals
        return f"${price:.6f}"
    elif abs_price < 1:
        # Small: 4 decimals
        return f"${price:.4f}"
    elif abs_price < 100:
        # Medium: 2 decimals
        return f"${price:.2f}"
    else:
        # Large: 2 decimals with comma separator
        return f"${price:,.2f}"


def format_pnl_for_notification(pnl: float, pnl_percent: float = None) -> str:
    """
    Format PnL with sign and appropriate decimals
    
    Args:
        pnl: PnL value in USDC
        pnl_percent: Optional PnL percentage
        
    Returns:
        Formatted PnL string with sign and optional percentage
        
    Examples:
        >>> format_pnl_for_notification(1500.0, 1.58)
        '+$1,500.00 (+1.58%)'
        >>> format_pnl_for_notification(-0.358, -1.37)
        '-$0.36 (-1.37%)'
    """
    sign = "+" if pnl >= 0 else ""
    
    # Format PnL value
    if abs(pnl) < 1:
        pnl_str = f"{sign}${pnl:.2f}"
    else:
        pnl_str = f"{sign}${pnl:,.2f}"
    
    # Add percentage if provided
    if pnl_percent is not None:
        percent_sign = "+" if pnl_percent >= 0 else ""
        pnl_str += f" ({percent_sign}{pnl_percent:.2f}%)"
    
    return pnl_str


def format_size_for_notification(size: float, symbol: str = "") -> str:
    """
    Format position size with appropriate decimals
    
    Args:
        size: Position size
        symbol: Trading symbol
        
    Returns:
        Formatted size string
        
    Examples:
        >>> format_size_for_notification(0.00085, "BTC")
        '0.00085 BTC'
        >>> format_size_for_notification(47.0, "WIF")
        '47.00 WIF'
    """
    if size < 0.001:
        size_str = f"{size:.8f}"
    elif size < 1:
        size_str = f"{size:.6f}"
    else:
        size_str = f"{size:.2f}"
    
    if symbol:
        return f"{size_str} {symbol}"
    return size_str


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    Format percentage with sign
    
    Args:
        value: Percentage value
        decimals: Number of decimal places
        
    Returns:
        Formatted percentage string with sign
        
    Examples:
        >>> format_percentage(1.58)
        '+1.58%'
        >>> format_percentage(-0.067)
        '-0.07%'
    """
    sign = "+" if value >= 0 else ""
    return f"{sign}{value:.{decimals}f}%"
