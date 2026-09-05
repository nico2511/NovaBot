"""
Helpers to build and persist the market context the AI gate actually sees.

Strategy timeframe is authoritative — never mix in 15m engine snapshots for
1h/5m lanes when validating or auditing a signal.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

# Fields injected into the IA validation prompt (strategy TF context only).
PROMPT_CONTEXT_KEYS = (
    "strategy_timeframe",
    "current_price",
    "regime",
    "market_bias",
    "rsi_val",
    "rsi_slope",
    "rsi_trend",
    "adx_val",
    "adx_slope",
    "volume_ratio",
    "vol_slope",
    "vol_trend",
    "macd_line",
    "macd_signal",
    "macd_hist",
    "bb_upper",
    "bb_middle",
    "bb_lower",
    "bb_position",
    "bb_width",
    "ema_20",
    "ema_50",
    "ema_20_slope",
    "ema_50_slope",
    "ema_50_slope_label",
    "fib_236",
    "fib_382",
    "fib_50",
    "fib_618",
    "fib_786",
    "fib_zone",
    "swing_high",
    "swing_low",
    "price_change_pct",
    "price_trend",
    "open_interest",
    "funding_rate",
    "mtf_sentiment",
)


def _pick(ctx: Dict[str, Any], key: str, fallback_key: Optional[str] = None) -> Any:
    if key in ctx and ctx[key] is not None:
        return ctx[key]
    if fallback_key and fallback_key in ctx:
        return ctx[fallback_key]
    return None


def normalize_strategy_context(raw: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Normalize a full _prepare_ai_context dict to prompt/audit shape.

    - Aliases rsi/adx → rsi_val/adx_val
    - Renames price_change_15m → price_change_pct (TF-agnostic label)
    - Drops keys never shown to the model (recent_closes, atr, etc.)
    """
    src = dict(raw or {})
    out: Dict[str, Any] = {}

    out["strategy_timeframe"] = src.get("strategy_timeframe") or "15m"
    out["current_price"] = src.get("current_price")
    out["regime"] = src.get("regime")
    out["market_bias"] = src.get("market_bias")

    rsi = _pick(src, "rsi_val", "rsi")
    if rsi is not None:
        out["rsi_val"] = round(float(rsi), 1)
    out["rsi_slope"] = src.get("rsi_slope")
    out["rsi_trend"] = src.get("rsi_trend")

    adx = _pick(src, "adx_val", "adx")
    if adx is not None:
        out["adx_val"] = round(float(adx), 2)
    out["adx_slope"] = src.get("adx_slope")

    if src.get("volume_ratio") is not None:
        out["volume_ratio"] = round(float(src["volume_ratio"]), 1)
    out["vol_slope"] = src.get("vol_slope")
    out["vol_trend"] = src.get("vol_trend")

    for k in (
        "macd_line",
        "macd_signal",
        "macd_hist",
        "bb_upper",
        "bb_middle",
        "bb_lower",
        "bb_position",
        "bb_width",
        "ema_20",
        "ema_50",
        "ema_20_slope",
        "ema_50_slope",
        "ema_50_slope_label",
        "fib_236",
        "fib_382",
        "fib_50",
        "fib_618",
        "fib_786",
        "fib_zone",
        "swing_high",
        "swing_low",
        "price_trend",
        "open_interest",
        "funding_rate",
        "mtf_sentiment",
    ):
        if src.get(k) is not None:
            out[k] = src[k]

    pct = src.get("price_change_pct")
    if pct is None:
        pct = src.get("price_change_15m")
    if pct is not None:
        out["price_change_pct"] = pct

    return {k: v for k, v in out.items() if v is not None}


def format_funding_rate_pct(raw_rate: Any) -> str:
    """Hyperliquid funding is a decimal hourly rate — display as %."""
    try:
        rate = float(raw_rate or 0)
    except (TypeError, ValueError):
        return "N/A"
    pct = rate * 100.0
    if pct > 0:
        side = "Longs pay Shorts"
    elif pct < 0:
        side = "Shorts pay Longs"
    else:
        side = "Neutral"
    return f"{pct:.4f}% ({side})"
