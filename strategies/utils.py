"""
Strategy Utility Functions

Contains helper functions for strategy management and risk control.
"""

import pandas as pd


def should_panic_close(strategy_name: str, current_df: pd.DataFrame, regime: str = "RANGE") -> tuple[bool, str]:
    """
    Determine if a position should be panic-closed based on regime change.
    
    This is a KILL SWITCH for strategies that become dangerous when market regime shifts.
    
    Args:
        strategy_name: Name of the strategy that opened the position
        current_df: Current market data DataFrame with indicators
        regime: Current market regime (e.g., "TREND", "RANGE", "TREND_BEAR_STRONG")
        
    Returns:
        (should_close: bool, reason: str)
    """
    
    # KILL SWITCH 1: Bollinger Bounce in Trend
    # ==========================================
    # Bollinger Bounce is a RANGE strategy. If ADX > 30, the range has broken
    # and we're in a trend. Holding a range trade in a trend = disaster.
    # NOTE: bollinger_bounce strategy not implemented - keeping for future reference
    
    # if strategy_name == "bollinger_bounce":
    #     if 'ADX_14' in current_df.columns:
    #         current_adx = current_df['ADX_14'].iloc[-1]
    #         if current_adx > 30:
    #             return (True, f"ADX breakout detected ({current_adx:.1f} > 30): Range strategy in trending market")
    
    # KILL SWITCH 2: Mean Reversion in Strong Trend
    # ==============================================
    # Any mean reversion strategy should exit if ADX spikes above 30 (strong trend forming)
    # NOTE: smart_mean_reversion, rsi_ping_pong not implemented
    
    mean_reversion_strategies = [
        "elastic_reversion",
        "institutional_scalp",
    ]
    
    if strategy_name in mean_reversion_strategies:
        if 'ADX_14' in current_df.columns:
            current_adx = current_df['ADX_14'].iloc[-1]
            
            # EXCEPTION: If we are in "TREND_BEAR_STRONG" (Crash), we might want to panic close BUYS (Reversion)
            # But the strategy itself usually handles that.
            # Here we just check if we are fighting a strong trend.
            
            if current_adx > 35:
                return (
                    True,
                    f"Strong trend detected ({current_adx:.1f} > 35): Mean reversion strategy at risk"
                )
    
    # KILL SWITCH 3: Trend Following in Range Collapse
    # =================================================
    # If a trend strategy is in a position and ADX drops below 20,
    # the trend has died and we should exit before whipsaw.
    # NOTE: smart_trend not implemented
    
    trend_strategies = [
        "scalp_ema_rsi",
    ]
    
    if strategy_name in trend_strategies:
        # If Engine says it's a STRONG BEAR TREND (Waterfall), trust it over lagging ADX
        if regime == "TREND_BEAR_STRONG":
             # NO PANIC CLOSE during waterfall
             return (False, "")

        if 'ADX_14' in current_df.columns:
            current_adx = current_df['ADX_14'].iloc[-1]
            
            if current_adx < 20:
                return (
                    True,
                    f"Trend collapse detected ({current_adx:.1f} < 20): Trend strategy losing momentum"
                )
    
    # No panic close needed
    return (False, "")


def calculate_volume_spike_ratio(df: pd.DataFrame, lookback: int = 20) -> float:
    """
    Calculate the ratio of current volume vs average volume.
    
    Args:
        df: DataFrame with 'volume' column
        lookback: Number of candles to average (default 20)
        
    Returns:
        Ratio (e.g., 1.5 = 50% above average, 0.8 = 20% below average)
        Returns 1.0 if volume data unavailable
    """
    if 'volume' not in df.columns or len(df) < lookback + 1:
        return 1.0
    
    try:
        # Use completed candle for volume (more accurate)
        if len(df) >= lookback + 2:
            current_volume = df['volume'].iloc[-2]  # Last completed candle
            avg_volume = df['volume'].iloc[-(lookback+2):-2].mean()
        else:
            # Fallback for insufficient data
            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].iloc[-(lookback+1):-1].mean()
        
        if avg_volume == 0:
            return 1.0
        
        return current_volume / avg_volume
    except:
        return 1.0
