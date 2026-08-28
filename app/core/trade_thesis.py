"""
In-trade thesis evaluation — pure helpers, no I/O.

Each strategy implements evaluate_trade_thesis() on BaseStrategy; helpers
here encode plan-specific rules (SuperTrend 15m structure, Range LT box, …).

Verdict actions:
  VALID  → leave trailing/BE alone
  WEAK   → thesis softening; tighten SL toward break-even if green
  DEAD   → structure broken; close only if unrealized PnL covers fees, else leave SL

NEAR_TP_EXHAUSTION overlay (via apply_near_tp_exhaustion / finalize_thesis_verdict):
  High progress toward TP + drying volume + tight-range stall → WEAK + lock partial gains.

DEAD_DRIFT overlay (via apply_dead_drift / finalize_thesis_verdict):
  Confirmed DEAD + small red PnL → progressively tighten SL toward entry (cap max loss).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Any, Dict, Optional, Tuple


THESIS_VALID = "VALID"
THESIS_WEAK = "WEAK"
THESIS_DEAD = "DEAD"

ACTION_HOLD = "HOLD"
ACTION_TIGHTEN_SL = "TIGHTEN_SL"
ACTION_CLOSE_IF_PROFIT = "CLOSE_IF_PROFIT"

# Soft-close only when green enough to survive round-trip fees (~HL taker).
MIN_SOFT_CLOSE_PNL_PCT = 0.25

# Near-TP exhaustion: fill the 70–85% progress gap before default trailing kicks in.
NEAR_TP_MIN_PROGRESS_PCT = 70.0
NEAR_TP_EXHAUSTION_MAX_VOL_RATIO = 50.0
NEAR_TP_STALL_BARS = 3
NEAR_TP_STALL_MAX_RANGE_PCT = 0.40
NEAR_TP_LOCK_FRACTION = 0.55

# DEAD drift: after consecutive DEAD checks on a small loser, ratchet SL toward entry.
DEAD_DRIFT_MIN_STREAK = 2
DEAD_DRIFT_MIN_LOSS_PCT = 0.25
DEAD_DRIFT_MAX_LOSS_PCT = 2.5
DEAD_DRIFT_FRACTION = 0.35
DEAD_DRIFT_CAP_LOSS_PCT = 1.2


def is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def thesis_indicators_ready(
    *,
    close_15m: Any,
    ema_filter: Any,
    st_direction: Any,
    supertrend: Any,
    adx: Any,
) -> bool:
    """True when 15m inputs are usable (no NaN / missing)."""
    if not all(
        is_finite_number(v)
        for v in (close_15m, ema_filter, supertrend, adx, st_direction)
    ):
        return False
    if float(ema_filter) <= 0 or float(supertrend) <= 0 or float(close_15m) <= 0:
        return False
    return True


@dataclass(frozen=True)
class ThesisVerdict:
    status: str
    action: str
    reasons: tuple
    adx: float
    adx_slope: float
    st_direction: int
    close: float
    supertrend: float
    pnl_pct: float
    tighten_sl: Optional[float] = None


def _pnl_pct(side: str, entry: float, price: float) -> float:
    if entry <= 0 or price <= 0:
        return 0.0
    raw = (price - entry) / entry * 100.0
    return raw if side == "BUY" else -raw


def tp_progress_pct(side: str, entry: float, tp: float, price: float) -> Optional[float]:
    """Progress toward TP as % of entry→TP distance (mirrors trailing_logic)."""
    side = (side or "").upper()
    if side not in ("BUY", "SELL") or entry <= 0 or tp <= 0 or price <= 0:
        return None
    if side == "BUY":
        total_dist = tp - entry
        current_dist = price - entry
    else:
        total_dist = entry - tp
        current_dist = entry - price
    if total_dist <= 0:
        return None
    return (current_dist / total_dist) * 100.0


def volume_ratio_pct(df: Any, *, lookback: int = 50) -> Optional[float]:
    """Last closed bar volume vs rolling mean (%), excluding the forming candle."""
    if df is None or getattr(df, "empty", True) or "volume" not in getattr(df, "columns", []):
        return None
    if len(df) < lookback + 2:
        return None
    try:
        vol = float(df["volume"].iloc[-2])
        ma = float(df["volume"].iloc[:-2].tail(lookback).mean())
        if ma <= 0:
            return None
        return vol / ma * 100.0
    except (TypeError, ValueError, IndexError):
        return None


def count_stall_bars(df: Any, *, n: int = 3, max_range_pct: float = 0.40) -> int:
    """Count recent closed bars with tight high-low range (price stalling)."""
    if df is None or getattr(df, "empty", True) or len(df) < n + 2:
        return 0
    stall = 0
    for i in range(-(n + 1), -1):
        try:
            row = df.iloc[i]
            high = float(row["high"])
            low = float(row["low"])
            close = float(row["close"])
        except (TypeError, ValueError, IndexError, KeyError):
            continue
        if close <= 0:
            continue
        if (high - low) / close * 100.0 <= max_range_pct:
            stall += 1
    return stall


def near_tp_exhaustion_sl(
    side: str,
    entry: float,
    tp: float,
    *,
    lock_fraction: float = NEAR_TP_LOCK_FRACTION,
) -> Optional[float]:
    """Lock a fraction of the planned entry→TP move when momentum dries near target."""
    side = (side or "").upper()
    if entry <= 0 or tp <= 0:
        return None
    frac = float(lock_fraction)
    if frac <= 0 or frac >= 1:
        return None
    if side == "BUY":
        total = tp - entry
        if total <= 0:
            return None
        return entry + total * frac
    if side == "SELL":
        total = entry - tp
        if total <= 0:
            return None
        return entry - total * frac
    return None


def detect_near_tp_exhaustion(
    *,
    side: str,
    entry: float,
    tp: float,
    current_price: float,
    df: Any,
    min_progress_pct: float = NEAR_TP_MIN_PROGRESS_PCT,
    max_volume_ratio_pct: float = NEAR_TP_EXHAUSTION_MAX_VOL_RATIO,
    stall_bars: int = NEAR_TP_STALL_BARS,
    stall_max_range_pct: float = NEAR_TP_STALL_MAX_RANGE_PCT,
) -> Tuple[bool, tuple]:
    """True when price is near TP but volume dried up and candles are compressing."""
    progress = tp_progress_pct(side, entry, tp, current_price)
    if progress is None or progress < min_progress_pct:
        return False, ()

    vol_ratio = volume_ratio_pct(df)
    if vol_ratio is None or vol_ratio >= max_volume_ratio_pct:
        return False, ()

    stalls = count_stall_bars(df, n=stall_bars, max_range_pct=stall_max_range_pct)
    if stalls < stall_bars:
        return False, ()

    return True, (
        f"NEAR_TP_EXHAUSTION: {progress:.0f}% to TP, vol {vol_ratio:.0f}% avg, "
        f"{stalls} tight-range bars",
    )


def apply_near_tp_exhaustion(
    verdict: ThesisVerdict,
    *,
    trade: Dict[str, Any],
    current_price: float,
    df: Any,
    min_progress_pct: float = NEAR_TP_MIN_PROGRESS_PCT,
    max_volume_ratio_pct: float = NEAR_TP_EXHAUSTION_MAX_VOL_RATIO,
    stall_bars: int = NEAR_TP_STALL_BARS,
    stall_max_range_pct: float = NEAR_TP_STALL_MAX_RANGE_PCT,
    lock_fraction: float = NEAR_TP_LOCK_FRACTION,
) -> ThesisVerdict:
    """Upgrade VALID→WEAK when near TP with exhaustion; suggest a partial-profit SL lock."""
    if verdict.status == THESIS_DEAD or verdict.pnl_pct <= 0:
        return verdict

    side = str(trade.get("side") or "BUY").upper()
    entry = float(trade.get("entry") or trade.get("entry_price") or 0)
    tp = float(trade.get("tp") or 0)
    if entry <= 0 or tp <= 0:
        return verdict

    triggered, reasons = detect_near_tp_exhaustion(
        side=side,
        entry=entry,
        tp=tp,
        current_price=float(current_price),
        df=df,
        min_progress_pct=min_progress_pct,
        max_volume_ratio_pct=max_volume_ratio_pct,
        stall_bars=stall_bars,
        stall_max_range_pct=stall_max_range_pct,
    )
    if not triggered:
        return verdict

    lock_sl = near_tp_exhaustion_sl(
        side, entry, tp, lock_fraction=lock_fraction
    )
    if lock_sl is None:
        return verdict

    merged_reasons = tuple(verdict.reasons) + reasons
    return replace(
        verdict,
        status=THESIS_WEAK,
        action=ACTION_TIGHTEN_SL,
        reasons=merged_reasons,
        tighten_sl=float(lock_sl),
    )


def compute_thesis_dead_streak(
    prev_status: Optional[str],
    verdict_status: str,
    prev_streak: int = 0,
) -> int:
    """Consecutive DEAD thesis checks (reset on VALID / WEAK)."""
    if verdict_status != THESIS_DEAD:
        return 0
    if prev_status == THESIS_DEAD:
        return max(1, int(prev_streak or 0) + 1)
    return 1


def dead_drift_sl(
    side: str,
    entry: float,
    current_sl: float,
    *,
    drift_fraction: float = DEAD_DRIFT_FRACTION,
    cap_loss_pct: float = DEAD_DRIFT_CAP_LOSS_PCT,
) -> Optional[float]:
    """Move SL partially toward entry; never past entry on a still-losing trade."""
    side = (side or "").upper()
    entry = float(entry)
    current_sl = float(current_sl)
    if entry <= 0 or current_sl <= 0:
        return None
    frac = float(drift_fraction)
    if frac <= 0 or frac >= 1:
        return None
    cap = float(cap_loss_pct)

    if side == "BUY":
        gap = entry - current_sl
        if gap <= 0:
            return None
        tightened = current_sl + gap * frac
        floor = entry * (1.0 - cap / 100.0)
        tightened = max(tightened, floor)
        tightened = min(tightened, entry * 0.999)
        return tightened if tightened > current_sl else None

    if side == "SELL":
        gap = current_sl - entry
        if gap <= 0:
            return None
        tightened = current_sl - gap * frac
        ceiling = entry * (1.0 + cap / 100.0)
        tightened = min(tightened, ceiling)
        tightened = max(tightened, entry * 1.001)
        return tightened if tightened < current_sl else None

    return None


def apply_dead_drift(
    verdict: ThesisVerdict,
    *,
    trade: Dict[str, Any],
    current_sl: float,
    min_streak: int = DEAD_DRIFT_MIN_STREAK,
    min_loss_pct: float = DEAD_DRIFT_MIN_LOSS_PCT,
    max_loss_pct: float = DEAD_DRIFT_MAX_LOSS_PCT,
    drift_fraction: float = DEAD_DRIFT_FRACTION,
    cap_loss_pct: float = DEAD_DRIFT_CAP_LOSS_PCT,
) -> ThesisVerdict:
    """On confirmed DEAD + red, ratchet SL toward entry to cap further loss."""
    if verdict.status != THESIS_DEAD:
        return verdict
    if verdict.pnl_pct >= 0:
        return verdict

    loss = abs(float(verdict.pnl_pct))
    if loss < min_loss_pct or loss > max_loss_pct:
        return verdict

    prev_status = trade.get("thesis_status")
    prev_streak = int(trade.get("thesis_dead_streak") or 0)
    streak = compute_thesis_dead_streak(prev_status, verdict.status, prev_streak)
    if streak < min_streak:
        return verdict

    side = str(trade.get("side") or "BUY").upper()
    entry = float(trade.get("entry") or trade.get("entry_price") or 0)
    if entry <= 0:
        return verdict

    drift_sl = dead_drift_sl(
        side,
        entry,
        float(current_sl),
        drift_fraction=drift_fraction,
        cap_loss_pct=cap_loss_pct,
    )
    if drift_sl is None:
        return verdict

    reason = (
        f"DEAD_DRIFT: streak {streak}, PnL {verdict.pnl_pct:+.2f}% "
        f"→ tighten SL toward entry (cap -{cap_loss_pct:.1f}%)"
    )
    return replace(
        verdict,
        action=ACTION_TIGHTEN_SL,
        reasons=tuple(verdict.reasons) + (reason,),
        tighten_sl=float(drift_sl),
    )


def evaluate_supertrend_thesis(
    *,
    side: str,
    entry: float,
    current_price: float,
    close_15m: float,
    ema_filter: float,
    st_direction: int,
    supertrend: float,
    adx: float,
    adx_slope: float,
    adx_threshold: float = 22.0,
    min_adx_slope: float = -1.0,
    weak_adx_slope: float = -0.35,
) -> ThesisVerdict:
    """Classify whether an open SuperTrend trade thesis still holds."""
    side = (side or "").upper()
    if side not in ("BUY", "SELL"):
        return ThesisVerdict(
            status=THESIS_DEAD,
            action=ACTION_HOLD,
            reasons=("unknown side",),
            adx=float(adx or 0),
            adx_slope=float(adx_slope or 0),
            st_direction=int(st_direction or 0),
            close=float(close_15m or 0),
            supertrend=float(supertrend or 0),
            pnl_pct=_pnl_pct(side, entry, current_price),
        )

    reasons = []
    want_dir = 1 if side == "BUY" else -1
    aligned_st = int(st_direction) == want_dir
    aligned_ema = (
        close_15m > ema_filter if side == "BUY" else close_15m < ema_filter
    )
    # Price still on the correct side of the ST line (hard structure)
    on_st_side = (
        close_15m >= supertrend if side == "BUY" else close_15m <= supertrend
    )

    dead = False
    weak = False

    if not aligned_st or not on_st_side:
        dead = True
        reasons.append("SuperTrend flipped / price through ST")
    if not aligned_ema:
        # EMA loss alone = weak first; combined with ST break = dead already
        if dead:
            reasons.append("price vs EMA filter also broken")
        else:
            weak = True
            reasons.append("price lost EMA filter (soft)")

    if adx < adx_threshold:
        if dead:
            reasons.append(f"ADX low ({adx:.1f})")
        else:
            weak = True
            reasons.append(f"ADX below threshold ({adx:.1f} < {adx_threshold:.0f})")

    if adx_slope < min_adx_slope:
        dead = True
        reasons.append(f"ADX slope dying ({adx_slope:+.2f})")
    elif adx_slope < weak_adx_slope:
        weak = True
        reasons.append(f"ADX slope softening ({adx_slope:+.2f})")

    if dead:
        status = THESIS_DEAD
    elif weak:
        status = THESIS_WEAK
    else:
        status = THESIS_VALID
        reasons = reasons or ("15m ST + EMA + ADX still aligned",)

    pnl = _pnl_pct(side, entry, current_price)
    if status == THESIS_DEAD:
        action = ACTION_CLOSE_IF_PROFIT
    elif status == THESIS_WEAK and pnl > 0:
        action = ACTION_TIGHTEN_SL
    else:
        action = ACTION_HOLD

    return ThesisVerdict(
        status=status,
        action=action,
        reasons=tuple(reasons),
        adx=float(adx),
        adx_slope=float(adx_slope),
        st_direction=int(st_direction),
        close=float(close_15m),
        supertrend=float(supertrend),
        pnl_pct=float(pnl),
    )


def evaluate_waterfall_thesis(
    *,
    side: str,
    entry: float,
    current_price: float,
    close_15m: float,
    ema9: float,
    rsi: float = 50.0,
    prev_open: float = 0.0,
    prev_close: float = 0.0,
    prev_high: float = 0.0,
    cascade_high: Optional[float] = None,
    rsi_exhaustion: float = 18.0,
) -> ThesisVerdict:
    """Classify whether an open waterfall short thesis still holds.

    ``rsi_exhaustion`` mirrors strategy ``veto_rsi_oversold`` so BE-lock does
    not fire inside the RSI band that was valid at entry.
    """
    side = (side or "").upper()
    if side != "SELL":
        return ThesisVerdict(
            status=THESIS_DEAD,
            action=ACTION_HOLD,
            reasons=("waterfall thesis is short-only",),
            adx=0.0,
            adx_slope=0.0,
            st_direction=-1,
            close=float(close_15m or 0),
            supertrend=float(ema9 or 0),
            pnl_pct=_pnl_pct(side, entry, current_price),
        )

    reasons = []
    dead = False
    weak = False
    close_15m = float(close_15m or 0)
    ema9 = float(ema9 or 0)

    # Cascade broken: price reclaimed EMA9
    if ema9 > 0 and close_15m > ema9:
        dead = True
        reasons.append(f"15m close {close_15m:.6g} reclaimed EMA9 {ema9:.6g}")

    # Bullish reversal candle through prior high
    if prev_close > prev_open and prev_high > 0 and close_15m > prev_high:
        if not dead:
            weak = True
            reasons.append("Green candle breaking prior high — cascade stalling")
        else:
            reasons.append("Bullish reversal through prior high")

    # Stop run above entry plan high (structure break against short)
    if cascade_high is not None:
        try:
            ch = float(cascade_high)
            if ch > 0 and close_15m > ch * 1.002:
                dead = True
                reasons.append(f"Price above cascade high {ch:.6g}")
        except (TypeError, ValueError):
            pass

    if not dead and rsi < rsi_exhaustion:
        weak = True
        reasons.append(f"RSI {rsi:.1f} — bounce risk on exhausted cascade")

    if dead:
        status = THESIS_DEAD
    elif weak:
        status = THESIS_WEAK
    else:
        status = THESIS_VALID
        reasons = reasons or ("15m waterfall cascade still active",)

    pnl = _pnl_pct(side, entry, current_price)
    if status == THESIS_DEAD:
        action = ACTION_CLOSE_IF_PROFIT
    elif status == THESIS_WEAK and pnl > 0:
        action = ACTION_TIGHTEN_SL
    else:
        action = ACTION_HOLD

    return ThesisVerdict(
        status=status,
        action=action,
        reasons=tuple(reasons),
        adx=0.0,
        adx_slope=0.0,
        st_direction=-1,
        close=close_15m,
        supertrend=ema9,
        pnl_pct=float(pnl),
    )


def evaluate_rocket_thesis(
    *,
    side: str,
    entry: float,
    current_price: float,
    close_15m: float,
    ema9: float,
    rsi: float = 50.0,
    prev_open: float = 0.0,
    prev_close: float = 0.0,
    prev_low: float = 0.0,
    cascade_low: Optional[float] = None,
    rsi_exhaustion: float = 82.0,
) -> ThesisVerdict:
    """Classify whether an open rocket long thesis still holds.

    ``rsi_exhaustion`` mirrors strategy ``veto_rsi_overbought`` so BE-lock does
    not fire inside the RSI band that was valid at entry.
    """
    side = (side or "").upper()
    if side != "BUY":
        return ThesisVerdict(
            status=THESIS_DEAD,
            action=ACTION_HOLD,
            reasons=("rocket thesis is long-only",),
            adx=0.0,
            adx_slope=0.0,
            st_direction=1,
            close=float(close_15m or 0),
            supertrend=float(ema9 or 0),
            pnl_pct=_pnl_pct(side, entry, current_price),
        )

    reasons = []
    dead = False
    weak = False
    close_15m = float(close_15m or 0)
    ema9 = float(ema9 or 0)

    if ema9 > 0 and close_15m < ema9:
        dead = True
        reasons.append(f"15m close {close_15m:.6g} lost EMA9 {ema9:.6g}")

    if prev_close < prev_open and prev_low > 0 and close_15m < prev_low:
        if not dead:
            weak = True
            reasons.append("Red candle breaking prior low — cascade stalling")
        else:
            reasons.append("Bearish reversal through prior low")

    if cascade_low is not None:
        try:
            cl = float(cascade_low)
            if cl > 0 and close_15m < cl * 0.998:
                dead = True
                reasons.append(f"Price below cascade low {cl:.6g}")
        except (TypeError, ValueError):
            pass

    if not dead and rsi > rsi_exhaustion:
        weak = True
        reasons.append(f"RSI {rsi:.1f} — fade risk on exhausted cascade")

    if dead:
        status = THESIS_DEAD
    elif weak:
        status = THESIS_WEAK
    else:
        status = THESIS_VALID
        reasons = reasons or ("15m rocket cascade still active",)

    pnl = _pnl_pct(side, entry, current_price)
    if status == THESIS_DEAD:
        action = ACTION_CLOSE_IF_PROFIT
    elif status == THESIS_WEAK and pnl > 0:
        action = ACTION_TIGHTEN_SL
    else:
        action = ACTION_HOLD

    return ThesisVerdict(
        status=status,
        action=action,
        reasons=tuple(reasons),
        adx=0.0,
        adx_slope=0.0,
        st_direction=1,
        close=close_15m,
        supertrend=ema9,
        pnl_pct=float(pnl),
    )


def break_even_sl(side: str, entry: float) -> Optional[float]:
    """Slightly profitable BE lock (same idea as Smart BE)."""
    if entry <= 0:
        return None
    if side == "BUY":
        return entry * 1.002
    if side == "SELL":
        return entry * 0.998
    return None


def should_apply_be_tighten(side: str, entry: float, current_sl: float, be_sl: float) -> bool:
    """True if moving SL to BE would actually improve protection."""
    if entry <= 0 or be_sl <= 0:
        return False
    sl = float(current_sl or 0)
    if side == "BUY":
        return sl < be_sl
    if side == "SELL":
        return sl == 0 or sl > be_sl
    return False


def evaluate_range_lt_thesis(
    *,
    side: str,
    entry: float,
    current_price: float,
    close_1h: float,
    range_high: float,
    range_low: float,
    adx: float = 0.0,
    adx_slope: float = 0.0,
    adx_trend_threshold: float = 22.0,
    weak_adx_slope: float = 0.4,
) -> ThesisVerdict:
    """Classify whether an open Range LT box-fade thesis still holds."""
    side = (side or "").upper()
    rh = float(range_high)
    rl = float(range_low)
    close_1h = float(close_1h)
    if side not in ("BUY", "SELL") or rh <= rl or close_1h <= 0:
        return ThesisVerdict(
            status=THESIS_DEAD,
            action=ACTION_HOLD,
            reasons=("invalid range thesis inputs",),
            adx=float(adx or 0),
            adx_slope=float(adx_slope or 0),
            st_direction=0,
            close=close_1h,
            supertrend=rh if side == "SELL" else rl,
            pnl_pct=_pnl_pct(side, entry, current_price),
        )

    reasons = []
    dead = False
    weak = False

    if side == "SELL":
        if close_1h > rh:
            dead = True
            reasons.append(
                f"1h close {close_1h:.6g} above box high {rh:.6g} (breakout up)"
            )
        elif close_1h < rl:
            dead = True
            reasons.append(
                f"1h close {close_1h:.6g} below box low {rl:.6g} (wrong-side drift)"
            )
    else:
        if close_1h < rl:
            dead = True
            reasons.append(
                f"1h close {close_1h:.6g} below box low {rl:.6g} (breakout down)"
            )
        elif close_1h > rh:
            dead = True
            reasons.append(
                f"1h close {close_1h:.6g} above box high {rh:.6g} (wrong-side drift)"
            )

    if not dead:
        if adx >= adx_trend_threshold and adx_slope >= weak_adx_slope:
            weak = True
            reasons.append(
                f"ADX expanding ({adx:.1f}, slope {adx_slope:+.2f}) — range may break"
            )

    if dead:
        status = THESIS_DEAD
    elif weak:
        status = THESIS_WEAK
    else:
        status = THESIS_VALID
        reasons = reasons or (
            f"1h close {close_1h:.6g} inside box [{rl:.6g}-{rh:.6g}]",
        )

    pnl = _pnl_pct(side, entry, current_price)
    if status == THESIS_DEAD:
        action = ACTION_CLOSE_IF_PROFIT
    elif status == THESIS_WEAK and pnl > 0:
        action = ACTION_TIGHTEN_SL
    else:
        action = ACTION_HOLD

    bound = rh if side == "SELL" else rl
    return ThesisVerdict(
        status=status,
        action=action,
        reasons=tuple(reasons),
        adx=float(adx),
        adx_slope=float(adx_slope),
        st_direction=1 if not dead else -1,
        close=close_1h,
        supertrend=bound,
        pnl_pct=float(pnl),
    )


def decision_from_verdict(verdict: ThesisVerdict) -> Dict[str, Any]:
    """Serialize for logs / Discord / trade metadata."""
    return {
        "status": verdict.status,
        "action": verdict.action,
        "reasons": list(verdict.reasons),
        "adx": round(verdict.adx, 2),
        "adx_slope": round(verdict.adx_slope, 2),
        "pnl_pct": round(verdict.pnl_pct, 3),
        "close": verdict.close,
        "supertrend": verdict.supertrend,
    }
