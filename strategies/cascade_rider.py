"""
Shared helpers for rocket / waterfall cascade riders (15m detection + 1m entry).

Centralises extension filters, cascade age, and hybrid scan scoring so both
strategies stay symmetric without duplicating métier logic.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Tuple

import pandas as pd

from app.services.indicators import ta

DEFAULT_MAX_EXTENSION_ATR = 3.5
DEFAULT_SPARK_MAX_EXTENSION_ATR = 2.5
DEFAULT_CASCADE_FRESH_BARS_MAX = 4
DEFAULT_SPARK_CASCADE_FRESH_BARS_MAX = 3
DEFAULT_CASCADE_FRESH_BONUS = 10.0
DEFAULT_SCAN_INTERVAL_ACTIVE_MINUTES = 2.0
DEFAULT_SPARK_SCAN_INTERVAL_ACTIVE_MINUTES = 1.5


def detect_bull_cascade(
    df: pd.DataFrame,
    *,
    use_live: bool = True,
) -> Tuple[bool, Dict[str, float]]:
    """
    Bullish cascade: price > EMA9 > EMA20, double green, higher high.

    Shared by rocket (15m) and spark (5m).
    """
    empty: Dict[str, float] = {}
    if df is None or getattr(df, "empty", True) or len(df) < 3:
        return False, empty

    work = df
    if "EMA_9" not in work.columns or "EMA_20" not in work.columns:
        work = work.copy()
        work["EMA_9"] = ta.ema(work["close"], length=9)
        work["EMA_20"] = ta.ema(work["close"], length=20)

    curr_i = -1 if use_live else -2
    prev_i = -2 if use_live else -3

    try:
        curr_close = float(work["close"].iloc[curr_i])
        curr_open = float(work["open"].iloc[curr_i])
        curr_ema9 = float(work["EMA_9"].iloc[curr_i])
        curr_ema20 = float(work["EMA_20"].iloc[curr_i])
        prev_close = float(work["close"].iloc[prev_i])
        prev_open = float(work["open"].iloc[prev_i])
        prev_high = float(work["high"].iloc[prev_i])
    except (IndexError, TypeError, ValueError):
        return False, empty

    is_curr_green = curr_close > curr_open
    is_prev_green = prev_close > prev_open
    active = (
        curr_close > curr_ema9 > curr_ema20
        and is_curr_green
        and is_prev_green
        and curr_close > prev_high
    )
    if not active:
        return False, empty

    return True, {
        "close": curr_close,
        "ema9": curr_ema9,
        "ema20": curr_ema20,
        "prev_high": prev_high,
    }


def bar_index(*, use_live: bool) -> int:
    return -1 if use_live else -2


def ensure_ema_atr_rsi(work: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with EMA_9/20, ATR_14, RSI_14 when missing."""
    if work is None or getattr(work, "empty", True):
        return work
    out = work
    need_copy = False
    for col, fn in (
        ("EMA_9", lambda w: ta.ema(w["close"], length=9)),
        ("EMA_20", lambda w: ta.ema(w["close"], length=20)),
        ("ATR_14", lambda w: ta.atr(w["high"], w["low"], w["close"], length=14)),
        ("RSI_14", lambda w: ta.rsi(w["close"], length=14)),
    ):
        if col not in out.columns:
            if not need_copy:
                out = work.copy()
                need_copy = True
            out[col] = fn(out)
    return out


def extension_vs_ema_anchor(
    work: pd.DataFrame,
    side: str,
    *,
    ema_period: int = 9,
    use_live: bool = True,
) -> Optional[float]:
    """
    Extension from the cascade anchor EMA in ATR units (default EMA9).

    Rocket: (close - EMA9) / ATR — waterfall: (EMA9 - close) / ATR.
    """
    side_u = str(side or "").upper()
    if work is None or getattr(work, "empty", True):
        return None
    col = "EMA_9" if int(ema_period) == 9 else f"EMA_{int(ema_period)}"
    if col not in work.columns and int(ema_period) == 20 and "EMA_20" in work.columns:
        col = "EMA_20"
    idx = bar_index(use_live=use_live)
    try:
        close = float(work["close"].iloc[idx])
        ema = float(work[col].iloc[idx])
        atr = float(work["ATR_14"].iloc[idx])
    except (IndexError, TypeError, ValueError, KeyError):
        return None
    if atr <= 0:
        return None
    if side_u == "LONG":
        return (close - ema) / atr
    if side_u == "SHORT":
        return (ema - close) / atr
    return None


def extension_vs_ema20(
    work: pd.DataFrame,
    side: str,
    *,
    use_live: bool = True,
) -> Optional[float]:
    """Backward-compatible alias — cascade riders anchor on EMA9."""
    return extension_vs_ema_anchor(work, side, ema_period=9, use_live=use_live)


def extension_within_limit(
    work: pd.DataFrame,
    side: str,
    max_extension_atr: float,
    *,
    ema_period: int = 9,
    use_live: bool = True,
) -> Tuple[bool, Optional[float]]:
    ext = extension_vs_ema_anchor(
        work, side, ema_period=ema_period, use_live=use_live
    )
    if ext is None:
        return True, None
    return ext <= float(max_extension_atr), ext


def cascade_age_bars(
    work: pd.DataFrame,
    side: str,
    *,
    use_live: bool = True,
) -> int:
    """Count consecutive same-color candles ending at the evaluation bar."""
    side_u = str(side or "").upper()
    if work is None or getattr(work, "empty", True) or len(work) < 1:
        return 0
    end = bar_index(use_live=use_live)
    end_abs = len(work) + end if end < 0 else end
    streak = 0
    for i in range(end_abs, -1, -1):
        try:
            close = float(work["close"].iloc[i])
            open_ = float(work["open"].iloc[i])
        except (TypeError, ValueError, IndexError):
            break
        if side_u == "LONG":
            if close > open_:
                streak += 1
            else:
                break
        elif side_u == "SHORT":
            if close < open_:
                streak += 1
            else:
                break
        else:
            break
    return streak


def active_scan_interval_minutes(
    base_interval: float,
    *,
    sticky_armed: bool,
    scan_interval_active_minutes: float,
) -> float:
    """Accelerate lane refresh when a symbol is sticky-armed for 1m entry."""
    if sticky_armed:
        return max(1.0, min(float(base_interval), float(scan_interval_active_minutes)))
    return float(base_interval)


def compare_detection_timeframes(
    df_15m: pd.DataFrame,
    detect_fn: Callable[..., Tuple[bool, Dict[str, float]]],
    *,
    resample_rule: str = "5min",
) -> Dict[str, Any]:
    """
  Lightweight comparison helper for 15m vs resampled detection TF.

  Returns counts of live-bar detections on 15m and on a resampled series.
  Intended for offline analysis / unit tests — not used in the live bot loop.
    """
    if df_15m is None or getattr(df_15m, "empty", True):
        return {
            "bars_15m": 0,
            "bars_resampled": 0,
            "detections_15m_live": 0,
            "detections_resampled_live": 0,
            "resample_rule": resample_rule,
        }

    work = ensure_ema_atr_rsi(df_15m)
    det_15m = 0
    min_bars = 3
    for i in range(min_bars, len(work) + 1):
        slice_df = work.iloc[:i]
        active, _ = detect_fn(slice_df, use_live=True)
        if active:
            det_15m += 1

    resampled = (
        df_15m.resample(resample_rule)
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
    )
    resampled = ensure_ema_atr_rsi(resampled)
    det_rs = 0
    for i in range(min_bars, len(resampled) + 1):
        slice_df = resampled.iloc[:i]
        active, _ = detect_fn(slice_df, use_live=True)
        if active:
            det_rs += 1

    return {
        "bars_15m": len(work),
        "bars_resampled": len(resampled),
        "detections_15m_live": det_15m,
        "detections_resampled_live": det_rs,
        "resample_rule": resample_rule,
    }


def score_cascade_scan(
    df: pd.DataFrame,
    *,
    side: str,
    symbol: str,
    detect_fn: Callable[..., Tuple[bool, Dict[str, float]]],
    params: Dict[str, Any],
    vol_slope_from_df: Callable[[pd.DataFrame], Optional[float]],
    prior_structure_level: Callable[[pd.DataFrame, Dict[str, Any]], Optional[float]],
    at_prior_level: Callable[[float, float, Dict[str, Any]], bool],
    wick_trap_reason: Callable[..., Optional[str]],
    rsi_veto: Callable[[float, Dict[str, Any]], bool],
    rsi_score_bonus: Callable[[float], float],
    meta: Optional[Dict[str, Any]],
    close_key: str,
    ema_key: str,
) -> Optional[Dict[str, float]]:
    """
    Hybrid scan scorer: live bar arms, confirmed bar gates board score.

    Returns None when the candidate should not appear on the merge board.
    """
    if df is None or getattr(df, "empty", True):
        return None

    sticky_armed = bool(meta and meta.get("sticky_armed"))
    hybrid = bool(params.get("scan_score_use_confirmed_bar", True))

    live_active, live_snap = detect_fn(df, use_live=True)
    confirmed_active, confirmed_snap = (
        detect_fn(df, use_live=False) if hybrid else (live_active, live_snap)
    )

    if not live_active and not sticky_armed:
        return None
    if hybrid and not confirmed_active and not sticky_armed:
        return None

    work = ensure_ema_atr_rsi(df.copy())
    use_confirmed_filters = hybrid and (confirmed_active or sticky_armed)
    filter_live = not use_confirmed_filters

    rsi_idx = bar_index(use_live=filter_live)
    try:
        rsi = float(work["RSI_14"].iloc[rsi_idx])
    except (TypeError, ValueError, IndexError):
        rsi = 50.0
    if rsi_veto(rsi, params):
        return None

    vol_slope = vol_slope_from_df(work)
    if vol_slope is not None and vol_slope < float(params["veto_vol_slope_min"]):
        return None

    vol_ratio_pct = None
    # Volume spike is a live-cascade fuel signal; structure filters use confirmed bar.
    vol_idx = bar_index(use_live=bool(live_active))
    if "volume" in work.columns and len(work) >= 3:
        try:
            vol_now = float(work["volume"].iloc[vol_idx])
            hist_end = -2 if vol_idx == -1 else vol_idx
            vol_ma = float(work["volume"].iloc[:hist_end].rolling(50).mean().iloc[-1])
            if vol_ma > 0:
                vol_ratio_pct = (vol_now / vol_ma) * 100.0
        except Exception:
            vol_ratio_pct = None

    min_vol = float(params["min_volume_ratio_pct"])
    spike = float(params["volume_spike_pct"])
    if vol_ratio_pct is not None and vol_ratio_pct < min_vol and vol_ratio_pct < spike:
        return None

    try:
        px = float(work["close"].iloc[bar_index(use_live=filter_live)])
    except Exception:
        px = 0.0

    prior = prior_structure_level(work, params)
    if (
        prior is not None
        and px > 0
        and at_prior_level(px, prior, params)
        and (vol_ratio_pct is None or vol_ratio_pct < spike)
    ):
        return None

    wick_idx = bar_index(use_live=filter_live)
    wick_reason = wick_trap_reason(
        work,
        bar_index=wick_idx,
        min_wick_ratio=float(params["wick_trap_min_ratio"]),
        close_extreme_pct=float(params["wick_trap_close_extreme_pct"]),
    )
    if wick_reason:
        return None

    ext_ok, ext_atr = extension_within_limit(
        work,
        side,
        float(params.get("max_extension_atr", DEFAULT_MAX_EXTENSION_ATR)),
        ema_period=int(params.get("extension_ema_period", 9) or 9),
        use_live=filter_live,
    )
    if not ext_ok:
        return None

    snap = confirmed_snap if hybrid and confirmed_active else live_snap
    age = cascade_age_bars(work, side, use_live=filter_live)
    fresh_max = int(params.get("cascade_fresh_bars_max", DEFAULT_CASCADE_FRESH_BARS_MAX))

    score = 70.0
    reasons = [f"15m {side.lower()} cascade" + (" confirmed" if hybrid and confirmed_active else " live")]
    if vol_ratio_pct is not None:
        score += min(20.0, max(0.0, (vol_ratio_pct - min_vol) * 0.15))
        reasons.append(f"Vol {vol_ratio_pct:.0f}%")
    score += rsi_score_bonus(rsi)
    reasons.append(f"RSI {rsi:.1f}")
    if ext_atr is not None:
        reasons.append(f"Ext {ext_atr:.2f}x ATR")
    if age > 0 and age <= fresh_max:
        bonus = float(params.get("cascade_fresh_bonus", DEFAULT_CASCADE_FRESH_BONUS))
        score += bonus
        reasons.append(f"Fresh cascade ({age} bars)")

    if sticky_armed:
        score += 15.0
        reasons.append("Sticky armed near-entry")

    armed = sticky_armed or (live_active and not confirmed_active)

    bias = "LONG" if str(side).upper() == "LONG" else "SHORT"
    return {
        "score": min(100.0, score),
        "bias": bias,
        "symbol": symbol,
        "rsi": round(rsi, 1),
        "reasons": reasons,
        "armed": armed,
        "timeframe": "15m",
        close_key: snap.get("close"),
        ema_key: snap.get("ema9"),
        "cascade_age_bars": age,
        "extension_atr": round(ext_atr, 3) if ext_atr is not None else None,
    }
