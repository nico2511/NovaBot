"""
Shared market arithmetic — one definition of confirmed volume and swings.

Scan, generate_signal, engine snapshot, AI context, and hard veto must all
use these helpers so a log line and a reject reason describe the same bar.
"""
from __future__ import annotations

from typing import Any, Optional, Tuple

_LIVE_INCOMPLETE_VOL_PCT = 0.5


def confirmed_volume_series(df: Any):
    """Volume of closed candles only (drop the forming bar)."""
    if df is None or getattr(df, "empty", True) or "volume" not in getattr(df, "columns", []):
        return None
    if len(df) < 2:
        return df["volume"]
    return df["volume"].iloc[:-1]


def confirmed_volume_ratio_pct(df: Any, *, lookback: int = 50) -> Optional[float]:
    """
    Last closed bar volume vs MA of closed bars ending on that bar (%).

    Live bar is excluded from both numerator and MA so a fresh candle at ~0
    volume cannot false-veto. MA includes the confirmed bar (same as the
    engine snapshot / hard-veto overlay).
    """
    confirmed = confirmed_volume_series(df)
    if confirmed is None or len(confirmed) < 1:
        return None
    try:
        current = float(confirmed.iloc[-1])
        window = int(lookback) if lookback else 50
        ma = float(confirmed.rolling(window).mean().iloc[-1])
    except (TypeError, ValueError, IndexError):
        return None
    if ma != ma or ma <= 0:  # NaN or zero
        return None
    return (current / ma) * 100.0


def live_volume_ratio_pct(df: Any, *, lookback: int = 50) -> Optional[float]:
    """Forming-bar volume vs the confirmed MA50 (cascade fuel on the live candle)."""
    if df is None or getattr(df, "empty", True) or "volume" not in getattr(df, "columns", []):
        return None
    if len(df) < 2:
        return None
    confirmed = confirmed_volume_series(df)
    if confirmed is None or len(confirmed) < 1:
        return None
    try:
        live = float(df["volume"].iloc[-1])
        window = int(lookback) if lookback else 50
        ma = float(confirmed.rolling(window).mean().iloc[-1])
    except (TypeError, ValueError, IndexError):
        return None
    if ma != ma or ma <= 0:
        return None
    return (live / ma) * 100.0


def volume_ratio_for_gate(
    df: Any,
    *,
    live_cascade: bool = False,
    lookback: int = 50,
) -> Optional[float]:
    """
    Volume used by entry/scan gates.

    Trend/range plans: confirmed bar only.
    Cascade plans: max(confirmed, live) so a forming spike can still qualify
    while a dead confirmed tape (e.g. 25% of MA) cannot arm.
    """
    confirmed = confirmed_volume_ratio_pct(df, lookback=lookback)
    if not live_cascade:
        return confirmed
    live = live_volume_ratio_pct(df, lookback=lookback)
    values = [v for v in (confirmed, live) if v is not None]
    return max(values) if values else None


def is_missing_volume_ratio(vol_ratio_pct: Optional[float]) -> bool:
    """Treat near-zero ratio as incomplete data, not a dead market."""
    if vol_ratio_pct is None:
        return True
    try:
        return float(vol_ratio_pct) <= _LIVE_INCOMPLETE_VOL_PCT
    except (TypeError, ValueError):
        return True


def structural_swings(
    df: Any, *, lookback: int = 20
) -> Tuple[Optional[float], Optional[float]]:
    """
    Confirmed-bar swing high/low (rolling max/min, live bar excluded).

    Same window as ``BotContext._prepare_ai_context`` so pre-AI geometry
    and generate_signal trim the TP to the same structure.
    """
    if df is None or getattr(df, "empty", True) or len(df) < 2:
        return None, None
    if "high" not in df.columns or "low" not in df.columns:
        return None, None
    try:
        hi_idx = -2
        highs = df["high"].iloc[: hi_idx + 1]
        lows = df["low"].iloc[: hi_idx + 1]
        window = int(lookback) if lookback else 20
        swing_high = float(highs.rolling(window).max().iloc[-1])
        swing_low = float(lows.rolling(window).min().iloc[-1])
    except (TypeError, ValueError, IndexError):
        return None, None
    if swing_high != swing_high or swing_low != swing_low:
        return None, None
    return swing_high, swing_low
