"""
Reusable hard-veto helpers for strategy plans.

These are pure functions strategies may call from ``check_hard_veto``.
They are NOT a global bot law — the bot delegates veto ownership to the
active strategy. SuperTrend reuses the defaults below; a future strategy
can use different thresholds or skip these helpers entirely.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Default thresholds (SuperTrend reference). Override inside a strategy if needed.
RSI_OVERBOUGHT = 80.0
RSI_OVERSOLD = 30.0
# Strong trends often sit 50–70 ADX on 15m perps; only veto true parabolic blow-offs.
ADX_RUNAWAY = 75.0
LOW_VOLUME_RATIO_PCT = 50.0


def check_macd_momentum_veto(signal: str, market_context: dict) -> Optional[str]:
    """
    Block momentum entries when MACD histogram disagrees with direction.

    - BUY/LONG: require macd_hist > 0
    - SELL/SHORT: require macd_hist < 0

    Missing or unparsable macd_hist → no veto (same as other optional context).
    """
    ctx = market_context or {}
    side = str(signal or "").upper()
    raw = ctx.get("macd_hist")
    if raw is None:
        return None
    try:
        hist = float(raw)
    except (TypeError, ValueError):
        return None

    if side in ("BUY", "LONG") and hist <= 0:
        return (
            f"MACD histogram {hist:.4f} <= 0 — no bullish momentum on strategy TF"
        )
    if side in ("SELL", "SHORT") and hist >= 0:
        return (
            f"MACD histogram {hist:.4f} >= 0 — no bearish momentum on strategy TF"
        )
    return None


def check_hard_veto(signal: str, market_context: dict) -> Optional[str]:
    """Return a veto reason string, or None if the trade can proceed.

    Args:
        signal:           "BUY" or "SELL".
        market_context:   dict produced by the trading loop; expected keys
                          are ``current_price``, ``rsi``, ``adx``,
                          ``current_volume`` and ``avg_volume``. Any key may
                          be missing — the checker stays conservative.
    """
    try:
        price = market_context.get("current_price", 0) or 0

        # 1. RSI Veto (relaxed: blocks only extreme readings)
        rsi = market_context.get("rsi")
        if rsi is not None:
            if signal == "BUY" and rsi > RSI_OVERBOUGHT:
                return f"HARD VETO: RSI Overbought ({rsi:.1f} > {RSI_OVERBOUGHT:.0f}) @ {price:.2f}"
            if signal == "SELL" and rsi < RSI_OVERSOLD:
                return f"HARD VETO: RSI Oversold ({rsi:.1f} < {RSI_OVERSOLD:.0f}) @ {price:.2f}"

        # 2. ADX runaway (trend already parabolic — reversal risk high)
        adx = market_context.get("adx")
        if adx is not None and adx > ADX_RUNAWAY:
            return f"HARD VETO: ADX Extreme ({adx:.1f} > {ADX_RUNAWAY:.0f}) - Trend runaway @ {price:.2f}"

        # 3. Dead-volume veto (no liquidity → slippage / fake signal risk)
        # Prefer precomputed confirmed-candle ratio. Skip if volume looks incomplete
        # (live bar often reports ~0 at open — that is missing data, not dead market).
        vol_ratio_pct = market_context.get("volume_ratio")
        if vol_ratio_pct is None:
            current_vol = market_context.get("current_volume")
            avg_vol = market_context.get("avg_volume")
            if current_vol and avg_vol and avg_vol > 0:
                vol_ratio_pct = (current_vol / avg_vol) * 100
        try:
            vol_ratio_pct = float(vol_ratio_pct) if vol_ratio_pct is not None else None
        except (TypeError, ValueError):
            vol_ratio_pct = None
        if vol_ratio_pct is not None and vol_ratio_pct > 0.5 and vol_ratio_pct < LOW_VOLUME_RATIO_PCT:
            return f"HARD VETO: Low Volume ({vol_ratio_pct:.1f}% avg) @ {price:.2f}"

        macd_reason = check_macd_momentum_veto(signal, market_context)
        if macd_reason:
            return f"HARD VETO: {macd_reason} @ {price:.2f}"

        return None
    except Exception as e:  # pragma: no cover — defensive only
        logger.warning("Veto check error: %s", e)
        return None
