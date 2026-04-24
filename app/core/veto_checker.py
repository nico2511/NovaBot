"""
Hard-Veto Checker.

Pure, stateless technical guardrails evaluated just before a trade would be
submitted. If any rule triggers, entry is blocked regardless of what the AI
or strategy proposed — the goal is to prevent objectively bad setups
(extreme RSI, parabolic ADX, dead volume, …).

Returning `None` means "no veto"; returning a string returns the reason to
surface in logs / history. Keep this module free of side-effects and of any
reference to BotContext — it is designed to be unit-testable in isolation.
"""
from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Thresholds tuned for 15m timeframe on perp markets. Bump them here, not
# in the caller, so the behaviour stays centralized and test-covered.
RSI_OVERBOUGHT = 80.0
RSI_OVERSOLD = 30.0
ADX_RUNAWAY = 55.0
LOW_VOLUME_RATIO_PCT = 20.0


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
        current_vol = market_context.get("current_volume")
        avg_vol = market_context.get("avg_volume")
        if current_vol and avg_vol and avg_vol > 0:
            vol_ratio_pct = (current_vol / avg_vol) * 100
            if vol_ratio_pct < LOW_VOLUME_RATIO_PCT:
                return f"HARD VETO: Low Volume ({vol_ratio_pct:.1f}% avg) @ {price:.2f}"

        return None
    except Exception as e:  # pragma: no cover — defensive only
        logger.warning("Veto check error: %s", e)
        return None
