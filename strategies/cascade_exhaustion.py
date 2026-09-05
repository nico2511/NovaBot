"""Range blow-off / climax guards for rocket and waterfall cascades."""
from __future__ import annotations

from typing import Any, Dict, Optional

import pandas as pd

DEFAULT_RANGE_ADX_MAX = 22.0
DEFAULT_RANGE_RSI_LONG_MIN = 72.0
DEFAULT_RANGE_RSI_SHORT_MAX = 28.0
DEFAULT_WICK_TRAP_MIN_RATIO = 0.45
DEFAULT_WICK_TRAP_CLOSE_EXTREME_PCT = 0.75
DEFAULT_STRUCTURE_PROXIMITY_PCT = 0.35
DEFAULT_STRUCTURE_CLEAR_PCT = 0.60


def _ctx_float(ctx: Dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        raw = ctx.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return float(default)


def check_range_exhaustion_veto(
    signal: str,
    market_context: Optional[Dict[str, Any]],
    *,
    adx_max: float = DEFAULT_RANGE_ADX_MAX,
    rsi_long_min: float = DEFAULT_RANGE_RSI_LONG_MIN,
    rsi_short_max: float = DEFAULT_RANGE_RSI_SHORT_MAX,
) -> Optional[str]:
    """
    Hard veto when a cascade fires in a weak range with extension (BB or RSI).

    Requires the full combo — trending rockets/waterfalls stay permissive.
    """
    ctx = market_context or {}
    regime = str(ctx.get("regime") or "").upper()
    if regime != "RANGE":
        return None

    adx = _ctx_float(ctx, "adx_val", "adx")
    if adx >= float(adx_max):
        return None

    rsi = _ctx_float(ctx, "rsi_val", "rsi", default=50.0)
    bb = str(ctx.get("bb_position") or "").upper()
    side = str(signal or "").upper()

    if side == "BUY":
        extended = bb == "ABOVE_UPPER" or rsi > float(rsi_long_min)
        if not extended:
            return None
        parts = [f"RANGE ADX {adx:.1f}<{adx_max:.0f}"]
        if bb == "ABOVE_UPPER":
            parts.append("above upper BB")
        if rsi > float(rsi_long_min):
            parts.append(f"RSI {rsi:.1f}>{rsi_long_min:.0f}")
        return f"Range blow-off long ({', '.join(parts)}) — skip climax chase"

    if side == "SELL":
        extended = bb == "BELOW_LOWER" or rsi < float(rsi_short_max)
        if not extended:
            return None
        parts = [f"RANGE ADX {adx:.1f}<{adx_max:.0f}"]
        if bb == "BELOW_LOWER":
            parts.append("below lower BB")
        if rsi < float(rsi_short_max):
            parts.append(f"RSI {rsi:.1f}<{rsi_short_max:.0f}")
        return f"Range climax short ({', '.join(parts)}) — skip knife catch"

    return None


def _bar_ohlc(df: pd.DataFrame, bar_index: int = -1) -> Optional[tuple[float, float, float, float]]:
    if df is None or getattr(df, "empty", True):
        return None
    try:
        row = df.iloc[bar_index]
        return (
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
        )
    except (IndexError, KeyError, TypeError, ValueError):
        return None


def wick_trap_reason_long(
    df: pd.DataFrame,
    *,
    bar_index: int = -1,
    min_wick_ratio: float = DEFAULT_WICK_TRAP_MIN_RATIO,
    close_extreme_pct: float = DEFAULT_WICK_TRAP_CLOSE_EXTREME_PCT,
) -> Optional[str]:
    """Reject long when live bar is a spike wick without a strong close."""
    ohlc = _bar_ohlc(df, bar_index)
    if ohlc is None:
        return None
    open_, high, low, close = ohlc
    total = high - low
    if total <= 0:
        return None

    body_top = max(open_, close)
    upper_wick = high - body_top
    wick_ratio = upper_wick / total
    close_pos = (close - low) / total

    if wick_ratio >= float(min_wick_ratio) and close_pos < float(close_extreme_pct):
        return (
            f"Wick trap long (upper wick {wick_ratio:.0%} of range, "
            f"close not in top {(1 - close_extreme_pct):.0%})"
        )
    return None


def wick_trap_reason_short(
    df: pd.DataFrame,
    *,
    bar_index: int = -1,
    min_wick_ratio: float = DEFAULT_WICK_TRAP_MIN_RATIO,
    close_extreme_pct: float = DEFAULT_WICK_TRAP_CLOSE_EXTREME_PCT,
) -> Optional[str]:
    """Reject short when live bar is a spike wick down without a strong close."""
    ohlc = _bar_ohlc(df, bar_index)
    if ohlc is None:
        return None
    open_, high, low, close = ohlc
    total = high - low
    if total <= 0:
        return None

    body_bottom = min(open_, close)
    lower_wick = body_bottom - low
    wick_ratio = lower_wick / total
    close_pos = (close - low) / total
    bottom_pct = 1.0 - float(close_extreme_pct)

    if wick_ratio >= float(min_wick_ratio) and close_pos > bottom_pct:
        return (
            f"Wick trap short (lower wick {wick_ratio:.0%} of range, "
            f"close not in bottom {(1 - close_extreme_pct):.0%})"
        )
    return None


def clear_breakout_above(close: float, prior_high: float, clear_pct: float) -> bool:
    if close <= 0 or prior_high <= 0:
        return False
    return close > prior_high * (1.0 + float(clear_pct) / 100.0)


def clear_breakdown_below(close: float, prior_low: float, clear_pct: float) -> bool:
    if close <= 0 or prior_low <= 0:
        return False
    return close < prior_low * (1.0 - float(clear_pct) / 100.0)


def at_prior_floor(
    price: float,
    prior_low: float,
    proximity_pct: float = DEFAULT_STRUCTURE_PROXIMITY_PCT,
    clear_pct: float = DEFAULT_STRUCTURE_CLEAR_PCT,
) -> bool:
    """True when price is still sitting on prior support (including a noise pierce)."""
    if price <= 0 or prior_low <= 0:
        return False
    prox = float(proximity_pct) / 100.0
    clear = float(clear_pct) / 100.0
    if price < prior_low * (1.0 - clear):
        return False
    return price <= prior_low * (1.0 + prox)


def at_prior_ceiling(
    price: float,
    prior_high: float,
    proximity_pct: float = DEFAULT_STRUCTURE_PROXIMITY_PCT,
    clear_pct: float = DEFAULT_STRUCTURE_CLEAR_PCT,
) -> bool:
    """True when price is still sitting on prior resistance (including a noise pierce)."""
    if price <= 0 or prior_high <= 0:
        return False
    prox = float(proximity_pct) / 100.0
    clear = float(clear_pct) / 100.0
    if price > prior_high * (1.0 + clear):
        return False
    return price >= prior_high * (1.0 - prox)


def unbroken_structure_reason(
    side: str,
    *,
    entry: float,
    cascade_close: float,
    prior_level: Optional[float],
    proximity_pct: float,
    clear_pct: float,
    tf_label: str,
) -> Optional[str]:
    """
    Reject cascade entries that press into prior structure without a close-through.

    Volume at the level is ignored — absorption spikes look like cascade fuel.
    A 1m wick/pierce through support is not a break; only cascade_close through
    clear_pct qualifies.
    """
    if prior_level is None:
        return None
    try:
        prior = float(prior_level)
        entry_f = float(entry)
        close_f = float(cascade_close)
    except (TypeError, ValueError):
        return None
    if prior <= 0 or entry_f <= 0 or close_f <= 0:
        return None

    side_u = str(side or "").upper()
    if side_u in ("SHORT", "SELL"):
        if clear_breakdown_below(close_f, prior, clear_pct):
            return None
        if at_prior_floor(entry_f, prior, proximity_pct, clear_pct) or at_prior_floor(
            close_f, prior, proximity_pct, clear_pct
        ):
            return (
                f"Prior swing support {prior:.6g} — need a clear {tf_label} close "
                "breakdown (volume at the floor is absorption, not continuation)"
            )
        return None

    if side_u in ("LONG", "BUY"):
        if clear_breakout_above(close_f, prior, clear_pct):
            return None
        if at_prior_ceiling(entry_f, prior, proximity_pct, clear_pct) or at_prior_ceiling(
            close_f, prior, proximity_pct, clear_pct
        ):
            return (
                f"Prior swing resistance {prior:.6g} — need a clear {tf_label} close "
                "breakout (volume at the ceiling is absorption, not continuation)"
            )
        return None

    return None
