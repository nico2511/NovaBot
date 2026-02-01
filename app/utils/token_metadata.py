"""
Token Metadata Helper - Single Source of Truth for Token Rules

This module provides centralized access to token metadata from token_meta_cache.json.
All modules should use this helper instead of directly reading the cache file.

Usage:
    from app.utils.token_metadata import token_metadata
    
    # Get size decimals
    decimals = token_metadata.get_sz_decimals("BTC")
    
    # Round size for order
    rounded_size = token_metadata.round_size("DOGE", 531.72634)  # Returns 532
    
    # Format size for display
    formatted = token_metadata.format_size("BTC", 0.123456)  # Returns "0.12346"
"""

import json
import os
from typing import Dict, Optional

class TokenMetadata:
    """
    Centralized access to token metadata from token_meta_cache.json
    
    Provides:
    - Size decimals (szDecimals)
    - Max leverage (maxLeverage)
    - Isolation mode (onlyIsolated)
    - Formatting and rounding utilities
    """
    
    def __init__(self, cache_path: str = "token_meta_cache.json"):
        """
        Initialize token metadata helper
        
        Args:
            cache_path: Path to token_meta_cache.json file
        """
        self.cache_path = cache_path
        self.cache: Dict = {}
        self._load_cache()
    
    def _load_cache(self) -> None:
        """Load token metadata from cache file"""
        if not os.path.exists(self.cache_path):
            print(f"⚠️ Token metadata cache not found: {self.cache_path}")
            self.cache = {}
            return
        
        try:
            with open(self.cache_path, 'r') as f:
                self.cache = json.load(f)
            print(f"✅ Loaded metadata for {len(self.cache)} tokens from {self.cache_path}")
        except Exception as e:
            print(f"❌ Error loading token metadata cache: {e}")
            self.cache = {}
    
    def reload_cache(self) -> None:
        """Reload cache from file (useful if cache is updated)"""
        self._load_cache()
    
    def get_sz_decimals(self, symbol: str) -> int:
        """
        Get size decimals for a token
        
        Args:
            symbol: Token symbol (e.g., "BTC", "DOGE")
            
        Returns:
            Number of decimals allowed for position size
            
        Examples:
            >>> get_sz_decimals("BTC")
            5
            >>> get_sz_decimals("DOGE")
            0
        """
        if symbol in self.cache:
            return self.cache[symbol].get("szDecimals", 6)
        
        # Fallback: conservative default
        print(f"⚠️ {symbol} not in cache, using default szDecimals=6")
        return 6
    
    def get_max_leverage(self, symbol: str) -> int:
        """
        Get maximum leverage for a token
        
        Args:
            symbol: Token symbol
            
        Returns:
            Maximum leverage allowed
            
        Examples:
            >>> get_max_leverage("BTC")
            40
            >>> get_max_leverage("DOGE")
            20
        """
        if symbol in self.cache:
            return self.cache[symbol].get("maxLeverage", 5)
        
        # Fallback: conservative default
        print(f"⚠️ {symbol} not in cache, using default maxLeverage=5")
        return 5
    
    def get_only_isolated(self, symbol: str) -> bool:
        """
        Check if token requires isolated margin mode
        
        Args:
            symbol: Token symbol
            
        Returns:
            True if token requires isolated margin
        """
        if symbol in self.cache:
            return self.cache[symbol].get("onlyIsolated", False)
        
        # Fallback: assume not isolated
        return False
    
    def round_size(self, symbol: str, size: float) -> float:
        """
        Round size to valid precision for orders
        
        This is critical for order execution. Hyperliquid will reject
        orders with incorrect precision.
        
        Args:
            symbol: Token symbol
            size: Calculated position size
            
        Returns:
            Rounded size according to token's szDecimals
            
        Examples:
            >>> round_size("DOGE", 531.72634)
            532
            >>> round_size("BTC", 0.123456789)
            0.12346
        """
        sz_decimals = self.get_sz_decimals(symbol)
        
        if sz_decimals == 0:
            # Integer rounding for tokens like DOGE
            return round(size)
        else:
            # Decimal rounding
            return round(size, sz_decimals)
    
    def format_size(self, symbol: str, size: float) -> str:
        """
        Format size for display with correct decimals
        
        Use this for logs, Discord notifications, and UI display
        to ensure consistent formatting.
        
        Args:
            symbol: Token symbol
            size: Position size
            
        Returns:
            Formatted string with correct decimal places
            
        Examples:
            >>> format_size("DOGE", 532)
            "532"
            >>> format_size("BTC", 0.12346)
            "0.12346"
        """
        sz_decimals = self.get_sz_decimals(symbol)
        
        if sz_decimals == 0:
            # No decimals for integer tokens
            return f"{int(size)}"
        else:
            # Format with correct decimals
            return f"{size:.{sz_decimals}f}"
    
    def validate_leverage(self, symbol: str, requested_leverage: int) -> int:
        """
        Validate and clamp leverage to token's maximum
        
        Args:
            symbol: Token symbol
            requested_leverage: Desired leverage
            
        Returns:
            Clamped leverage (min of requested and max allowed)
            
        Examples:
            >>> validate_leverage("BTC", 50)  # BTC max is 40
            40
            >>> validate_leverage("DOGE", 10)  # DOGE max is 20
            10
        """
        max_lev = self.get_max_leverage(symbol)
        
        if requested_leverage > max_lev:
            print(f"⚠️ Leverage {requested_leverage} > Max {max_lev} for {symbol}. Clamping to {max_lev}.")
            return max_lev
        
        return requested_leverage
    
    def get_token_info(self, symbol: str) -> Dict:
        """
        Get all metadata for a token
        
        Args:
            symbol: Token symbol
            
        Returns:
            Dictionary with all token metadata
        """
        if symbol in self.cache:
            return self.cache[symbol]
        
        # Return defaults if not found
        return {
            "szDecimals": 6,
            "maxLeverage": 5,
            "onlyIsolated": False
        }
    
    def is_token_cached(self, symbol: str) -> bool:
        """Check if token exists in cache"""
        return symbol in self.cache
    
    def get_all_symbols(self) -> list:
        """Get list of all cached token symbols"""
        return list(self.cache.keys())


# Global singleton instance
token_metadata = TokenMetadata("data/cache/token_meta_cache.json")


# Convenience functions for backward compatibility
def get_sz_decimals(symbol: str) -> int:
    """Get size decimals for a token"""
    return token_metadata.get_sz_decimals(symbol)


def round_size(symbol: str, size: float) -> float:
    """Round size to valid precision"""
    return token_metadata.round_size(symbol, size)


def format_size(symbol: str, size: float) -> str:
    """Format size for display"""
    return token_metadata.format_size(symbol, size)


def validate_leverage(symbol: str, leverage: int) -> int:
    """Validate and clamp leverage"""
    return token_metadata.validate_leverage(symbol, leverage)
