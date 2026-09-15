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


def check_mtf_sentiment_veto(
    signal: str,
    mtf_text: str,
    *,
    block_1h_bias_conflict: bool = True,
    block_1h_mixed: bool = True,
    block_4h_bias_conflict: bool = True,
) -> Optional[str]:
    """
    Block entries when parsed 1h/4h MTF summary fights the trade direction.

    Expects text like:
    ``1h: bias=BEARISH ST=BULLISH (MIXED) ADX=24.9 ... | 4h: bias=BULLISH ...``
    """
    text = str(mtf_text or "").strip()
    if not text or "unavailable" in text.lower():
        return None

    side = str(signal or "").upper()
    want_long = side in ("BUY", "LONG")
    want_short = side in ("SELL", "SHORT")
    if not want_long and not want_short:
        return None

    for segment in text.split("|"):
        seg = segment.strip()
        if not seg.startswith(("1h:", "4h:")):
            continue
        tf = seg.split(":", 1)[0].strip().lower()
        if tf not in ("1h", "4h"):
            continue
        if block_1h_mixed and tf == "1h" and "(MIXED)" in seg.upper():
            return (
                f"1h MTF MIXED (EMA bias vs SuperTrend conflict) — no clean {side} confluence"
            )
        if "bias=BEARISH" in seg and want_long:
            if tf == "1h" and block_1h_bias_conflict:
                return f"1h MTF bias BEARISH conflicts with {side}"
            if tf == "4h" and block_4h_bias_conflict:
                return f"4h MTF bias BEARISH conflicts with {side}"
        if "bias=BULLISH" in seg and want_short:
            if tf == "1h" and block_1h_bias_conflict:
                return f"1h MTF bias BULLISH conflicts with {side}"
            if tf == "4h" and block_4h_bias_conflict:
                return f"4h MTF bias BULLISH conflicts with {side}"
    return None


def check_rsi_slope_veto(
    signal: str,
    market_context: dict,
    *,
    min_slope_long: float = -4.0,
    max_slope_short: float = 4.0,
) -> Optional[str]:
    """Block when RSI slope on the strategy TF disagrees with momentum for the side."""
    ctx = market_context or {}
    raw = ctx.get("rsi_slope")
    if raw is None:
        return None
    try:
        slope = float(raw)
    except (TypeError, ValueError):
        return None
    side = str(signal or "").upper()
    if side in ("BUY", "LONG") and slope < min_slope_long:
        return (
            f"RSI slope {slope:+.1f} < {min_slope_long:+.1f} — momentum fading on LONG"
        )
    if side in ("SELL", "SHORT") and slope > max_slope_short:
        return (
            f"RSI slope {slope:+.1f} > {max_slope_short:+.1f} — momentum fading on SHORT"
        )
    return None


def check_hard_veto(
    signal: str,
    market_context: dict,
    *,
    rsi_overbought: float = RSI_OVERBOUGHT,
    rsi_oversold: float = RSI_OVERSOLD,
    adx_runaway: float = ADX_RUNAWAY,
    low_volume_ratio_pct: float = LOW_VOLUME_RATIO_PCT,
    veto_macd_momentum: bool = True,
) -> Optional[str]:
    """Return a veto reason string, or None if the trade can proceed.

    Args:
        signal:           "BUY" or "SELL".
        market_context:   dict produced by the trading loop; expected keys
                          are ``current_price``, ``rsi``, ``adx``,
                          ``current_volume`` and ``avg_volume``. Any key may
                          be missing — the checker stays conservative.
        rsi_overbought:   Block BUY above this RSI (strategy-owned override).
        rsi_oversold:     Block SELL below this RSI.
        adx_runaway:      Block both sides when ADX exceeds this level.
        low_volume_ratio_pct: Minimum confirmed volume vs MA50 (%).
        veto_macd_momentum: When True, block when MACD histogram disagrees.
    """
    try:
        price = market_context.get("current_price", 0) or 0

        # 1. RSI Veto (relaxed: blocks only extreme readings)
        rsi = market_context.get("rsi")
        if rsi is not None:
            if signal == "BUY" and rsi > rsi_overbought:
                return (
                    f"HARD VETO: RSI Overbought ({rsi:.1f} > {rsi_overbought:.0f}) @ {price:.2f}"
                )
            if signal == "SELL" and rsi < rsi_oversold:
                return (
                    f"HARD VETO: RSI Oversold ({rsi:.1f} < {rsi_oversold:.0f}) @ {price:.2f}"
                )

        # 2. ADX runaway (trend already parabolic — reversal risk high)
        adx = market_context.get("adx")
        if adx is not None and adx > adx_runaway:
            return (
                f"HARD VETO: ADX Extreme ({adx:.1f} > {adx_runaway:.0f}) "
                f"- Trend runaway @ {price:.2f}"
            )

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
        if (
            vol_ratio_pct is not None
            and vol_ratio_pct > 0.5
            and vol_ratio_pct < low_volume_ratio_pct
        ):
            return f"HARD VETO: Low Volume ({vol_ratio_pct:.1f}% avg) @ {price:.2f}"

        if veto_macd_momentum:
            macd_reason = check_macd_momentum_veto(signal, market_context)
            if macd_reason:
                return f"HARD VETO: {macd_reason} @ {price:.2f}"

        return None
    except Exception as e:  # pragma: no cover — defensive only
        logger.warning("Veto check error: %s", e)
        return None
