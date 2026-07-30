"""
Strategy Utility Functions

Contains helper functions for strategy management and risk control.
"""

import pandas as pd


def should_panic_close(strategy_name: str, current_df: pd.DataFrame, regime: str = "RANGE") -> tuple[bool, str]:
    """
    Kill-switch for SuperTrend when the trend collapses into a dead range.

    Returns:
        (should_block_new_signal: bool, reason: str)

    Note: engine uses this to skip *new* signals, not to force-close positions.
    """
    if strategy_name != "supertrend":
        return (False, "")

    # During waterfall, keep allowing SuperTrend shorts / trend logic
    if regime == "TREND_BEAR_STRONG":
        return (False, "")

    if "ADX_14" in current_df.columns:
        current_adx = current_df["ADX_14"].iloc[-1]
        if current_adx < 20:
            return (
                True,
                f"Trend collapse detected ({current_adx:.1f} < 20): SuperTrend losing momentum",
            )

    return (False, "")


def calculate_volume_spike_ratio(df: pd.DataFrame, lookback: int = 20) -> float:
    """
    Calculate the ratio of current volume vs average volume.

    Returns 1.0 if volume data unavailable.
    """
    if "volume" not in df.columns or len(df) < lookback + 1:
        return 1.0

    try:
        if len(df) >= lookback + 2:
            current_volume = df["volume"].iloc[-2]
            avg_volume = df["volume"].iloc[-(lookback + 2):-2].mean()
        else:
            current_volume = df["volume"].iloc[-1]
            avg_volume = df["volume"].iloc[-(lookback + 1):-1].mean()

        if avg_volume == 0:
            return 1.0

        return current_volume / avg_volume
    except Exception:
        return 1.0
