"""
Strong-trend relax helpers — strategy-owned beta-day tuning.

Used by SuperTrend, Trend LT, and cascade riders to loosen chase / ADX-slope /
volume hard-veto gates when trend quality is high (risk-on days), without
 abandoning pullback+reclaim entry geometry.
"""
from __future__ import annotations

from typing import Any, Callable, Optional, Union

GetParam = Callable[[str, Any], Any]


def _float_ctx(ctx: dict, *keys: str) -> Optional[float]:
    for key in keys:
        raw = (ctx or {}).get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def strong_trend_relax_enabled(get_param: GetParam) -> bool:
    return bool(get_param("strong_trend_relax_enabled", True))


def adx_regime_hint(payload: Optional[dict]) -> Optional[str]:
    """
    ADX RANGE/TREND only.

    Engine cascade labels (TREND_BULL_STRONG / TREND_BEAR_STRONG) are a 15m
    overlay for strategy *selection*, not a 1h/scan quality hint. Feeding them
    into strong-trend relax would either hide a real RANGE or leak 15m into LT.
    """
    if not isinstance(payload, dict):
        return None
    for key in ("regime_adx", "regime"):
        raw = payload.get(key)
        if not isinstance(raw, str):
            continue
        label = raw.strip().upper()
        if label in ("RANGE", "TREND"):
            return label
    return None


def is_strong_trend_from_setup(
    direction: str,
    *,
    adx: float,
    adx_threshold: float,
    close: float,
    ema: float,
    st_dir: int,
    get_param: GetParam,
    regime: Optional[str] = None,
) -> bool:
    """True when confirmed trend structure is strong enough to relax anti-chase gates."""
    if not strong_trend_relax_enabled(get_param):
        return False
    try:
        adx_f = float(adx)
        adx_min = float(get_param("strong_trend_adx_min", 35) or 35)
        adx_floor = max(float(adx_threshold), adx_min)
    except (TypeError, ValueError):
        return False
    if adx_f < adx_floor:
        return False
    if regime and str(regime).upper() == "RANGE":
        return False
    side = str(direction or "").upper()
    try:
        close_f = float(close)
        ema_f = float(ema)
        st_i = int(st_dir)
    except (TypeError, ValueError):
        return False
    if side == "LONG":
        return close_f > ema_f and st_i == 1
    if side == "SHORT":
        return close_f < ema_f and st_i == -1
    return False


def is_strong_trend_from_context(
    signal: str,
    ctx: Optional[dict],
    get_param: GetParam,
    *,
    adx_threshold: Optional[float] = None,
) -> bool:
    """Infer strong trend from AI/veto market_context (and optional signal flag)."""
    if not strong_trend_relax_enabled(get_param):
        return False
    market = ctx or {}
    if market.get("strong_trend") is True:
        return True
    side = str(signal or "").upper()
    if side in ("BUY", "LONG"):
        direction = "LONG"
    elif side in ("SELL", "SHORT"):
        direction = "SHORT"
    else:
        return False

    adx = _float_ctx(market, "adx_val", "adx")
    if adx is None:
        return False
    try:
        adx_min = float(get_param("strong_trend_adx_min", 35) or 35)
        floor = float(adx_threshold) if adx_threshold is not None else adx_min
        floor = max(floor, adx_min)
    except (TypeError, ValueError):
        floor = float(get_param("strong_trend_adx_min", 35) or 35)
    if adx < floor:
        return False

    regime = str(market.get("regime") or "").upper()
    if regime == "RANGE":
        return False

    bias = str(market.get("market_bias") or "").upper()
    if direction == "LONG" and bias == "BEARISH":
        return False
    if direction == "SHORT" and bias == "BULLISH":
        return False
    return True


def effective_max_rsi_long(base: float, strong: bool, get_param: GetParam) -> float:
    if not strong:
        return float(base)
    return float(get_param("strong_trend_max_rsi_long", 70) or 70)


def effective_min_rsi_short(base: float, strong: bool, get_param: GetParam) -> float:
    if not strong:
        return float(base)
    return float(get_param("strong_trend_min_rsi_short", 30) or 30)


def effective_min_adx_slope(base: float, strong: bool, get_param: GetParam) -> float:
    if not strong:
        return float(base)
    return float(get_param("strong_trend_min_adx_slope", -1.2) or -1.2)


def effective_min_volume_ratio_pct(
    base: float, strong: bool, get_param: GetParam, *, thin_guard: bool = False
) -> float:
    if not strong:
        return float(base)
    key = "strong_trend_thin_liquidity_pct" if thin_guard else "strong_trend_min_volume_ratio_pct"
    default = 55.0 if thin_guard else float(base)
    return float(get_param(key, default) or default)


def effective_veto_volume_pct(base: float, strong: bool, get_param: GetParam) -> float:
    if not strong:
        return float(base)
    return float(get_param("strong_trend_veto_volume_pct", 55) or 55)


def effective_veto_macd_momentum(default: bool, strong: bool, get_param: GetParam) -> bool:
    if not strong:
        return bool(default)
    return bool(get_param("strong_trend_veto_macd_momentum", False))


def cascade_relaxed_limits(
    signal: str,
    ctx: Optional[dict],
    get_param: GetParam,
    *,
    default_rsi: float,
    default_min_vol: float,
    default_veto_macd: bool,
    rsi_mode: str,
) -> tuple[float, float, bool]:
    """Relaxed RSI / volume / MACD gates for cascade riders in strong trends."""
    adx_floor = float(get_param("strong_trend_adx_min", 28) or 28)
    strong = is_strong_trend_from_context(
        signal, ctx, get_param, adx_threshold=adx_floor
    )
    if not strong:
        return float(default_rsi), float(default_min_vol), bool(default_veto_macd)
    mode = str(rsi_mode or "").lower()
    if mode == "above":
        rsi = float(get_param("strong_trend_rsi_overbought", 78) or 78)
    else:
        rsi = float(get_param("strong_trend_rsi_oversold", 22) or 22)
    vol = float(get_param("strong_trend_min_volume_ratio_pct", 80) or 80)
    macd = effective_veto_macd_momentum(default_veto_macd, True, get_param)
    return rsi, vol, macd
