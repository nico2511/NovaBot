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


DISCORD_EMBED_DESC_LIMIT = 4096


def _fmt_num(value: Any, digits: int = 4) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return str(value)


def _ema_trend_arrow(ema20: Any, ema50: Any) -> str:
    try:
        e20, e50 = float(ema20), float(ema50)
    except (TypeError, ValueError):
        return "→"
    if e20 > e50:
        return "↗"
    if e20 < e50:
        return "↘"
    return "→"


def format_signal_discord_description(
    *,
    symbol: str,
    strategy: str,
    side: str,
    price: float,
    sl: Any,
    tp: Any,
    sig_ts: str,
    market_context: Optional[Dict[str, Any]],
    ai_trace_id: Optional[str] = None,
) -> tuple[str, Optional[str]]:
    """
    Build a readable Discord embed for pre-AI signal notifications.

    Returns (primary, overflow) so callers can send a follow-up when the
    embed would exceed Discord's 4096-character description limit.
    """
    ctx = dict(market_context or {})
    tf = ctx.get("strategy_timeframe") or "15m"
    rsi = _pick(ctx, "rsi_val", "rsi")
    adx = _pick(ctx, "adx_val", "adx")
    ema20 = ctx.get("ema_20")
    ema50 = ctx.get("ema_50")
    ema_trend = _ema_trend_arrow(ema20, ema50)

    sl_txt = _fmt_num(sl, 8) if sl is not None else "N/A"
    tp_txt = _fmt_num(tp, 8) if tp is not None else "N/A"

    lines = [
        f"**Strategy:** {strategy} | **{side}** {symbol}",
        f"**Entry:** {_fmt_num(price, 8)} | **SL/TP:** {sl_txt} / {tp_txt}",
        f"**Signal bar:** {sig_ts}",
    ]
    if ai_trace_id:
        lines.append(f"**Trace:** `{ai_trace_id}`")

    lines.extend(
        [
            "",
            f"**Market ({tf})**",
            (
                f"Price: {_fmt_num(ctx.get('current_price', price))} | "
                f"Regime: {ctx.get('regime', 'UNKNOWN')} | "
                f"Bias: {ctx.get('market_bias', 'N/A')}"
            ),
            (
                f"RSI: {rsi if rsi is not None else 'N/A'}"
                f" [{ctx.get('rsi_trend', '')}]"
                f" (Δ {ctx.get('rsi_slope', 0):+.1f})"
            ),
            f"ADX: {adx if adx is not None else 'N/A'} (slope {ctx.get('adx_slope', 0):+.2f})",
            (
                f"Vol ratio: {ctx.get('volume_ratio', 'N/A')}%"
                f" | Δ {ctx.get('vol_slope', 0):+.1f}%"
                f" [{ctx.get('vol_trend', '')}]"
            ),
            "",
            "**Trend**",
            (
                f"EMA20: {_fmt_num(ema20) if ema20 is not None else 'N/A'}"
                f" | EMA50: {_fmt_num(ema50) if ema50 is not None else 'N/A'}"
                f" ({ema_trend})"
            ),
            (
                f"EMA20 slope: {ctx.get('ema_20_slope', 0):.6f}"
                f" | EMA50 slope: {ctx.get('ema_50_slope', 0):.6f}"
                f" [{ctx.get('ema_50_slope_label', 'N/A')}]"
            ),
            "",
            "**MACD**",
            (
                f"line {_fmt_num(ctx.get('macd_line'))}"
                f" | signal {_fmt_num(ctx.get('macd_signal'))}"
                f" | hist {_fmt_num(ctx.get('macd_hist'))}"
            ),
            "",
            "**Bollinger**",
            (
                f"upper {_fmt_num(ctx.get('bb_upper'))}"
                f" | mid {_fmt_num(ctx.get('bb_middle'))}"
                f" | lower {_fmt_num(ctx.get('bb_lower'))}"
            ),
            (
                f"position: {ctx.get('bb_position', 'N/A')}"
                f" | width {ctx.get('bb_width', 'N/A')}%"
            ),
            "",
            "**Structure**",
            (
                f"Swing H/L: {_fmt_num(ctx.get('swing_high'))}"
                f" / {_fmt_num(ctx.get('swing_low'))}"
            ),
            f"Fib zone: {ctx.get('fib_zone', 'N/A')}",
            (
                f"23.6% {_fmt_num(ctx.get('fib_236'))}"
                f" | 38.2% {_fmt_num(ctx.get('fib_382'))}"
                f" | 50% {_fmt_num(ctx.get('fib_50'))}"
            ),
            (
                f"61.8% {_fmt_num(ctx.get('fib_618'))}"
                f" | 78.6% {_fmt_num(ctx.get('fib_786'))}"
            ),
            (
                f"Price {ctx.get('price_trend', '')}"
                f" ({ctx.get('price_change_pct', 0):+.2f}% on {tf})"
            ),
            "",
            "**Derivatives**",
            f"OI: ${int(float(ctx.get('open_interest') or 0)):,}",
            f"Funding (hourly): {format_funding_rate_pct(ctx.get('funding_rate'))}",
        ]
    )

    mtf = ctx.get("mtf_sentiment")
    if mtf:
        lines.extend(["", "**Higher timeframes**", str(mtf)])

    primary = "\n".join(lines)
    if len(primary) <= DISCORD_EMBED_DESC_LIMIT:
        return primary, None

    compact_end = lines.index("**Structure**")
    compact = lines[:compact_end]
    compact.append("")
    compact.append(
        f"Swing H/L: {_fmt_num(ctx.get('swing_high'))} / {_fmt_num(ctx.get('swing_low'))}"
    )
    compact.append(f"Fib zone: {ctx.get('fib_zone', 'N/A')}")
    compact.append(f"Price Δ: {ctx.get('price_change_pct', 0):+.2f}% on {tf}")
    compact.extend(["", "**Derivatives**"])
    compact.append(f"OI: ${int(float(ctx.get('open_interest') or 0)):,}")
    compact.append(f"Funding: {format_funding_rate_pct(ctx.get('funding_rate'))}")
    compact.append("")
    compact.append("_(suite dans le message log suivant)_")

    overflow_lines = [
        f"**Signal context (suite)** `{ai_trace_id or 'n/a'}` {symbol} {strategy}",
        "",
        "**Structure (detail)**",
        (
            f"23.6% {_fmt_num(ctx.get('fib_236'))}"
            f" | 38.2% {_fmt_num(ctx.get('fib_382'))}"
            f" | 50% {_fmt_num(ctx.get('fib_50'))}"
        ),
        (
            f"61.8% {_fmt_num(ctx.get('fib_618'))}"
            f" | 78.6% {_fmt_num(ctx.get('fib_786'))}"
        ),
    ]
    if mtf:
        overflow_lines.extend(["", "**Higher timeframes**", str(mtf)])

    return "\n".join(compact), "\n".join(overflow_lines)[:DISCORD_EMBED_DESC_LIMIT]
