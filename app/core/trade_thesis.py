"""
In-trade thesis evaluation — pure helpers, no I/O.

Each strategy implements evaluate_trade_thesis() on BaseStrategy; helpers
here encode plan-specific rules (SuperTrend 15m structure, Range LT box, …).

Verdict actions:
  VALID  → leave trailing/BE alone
  WEAK   → thesis softening; tighten SL toward break-even if green
  DEAD   → structure broken; close only if unrealized PnL covers fees, else leave SL
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional


THESIS_VALID = "VALID"
THESIS_WEAK = "WEAK"
THESIS_DEAD = "DEAD"

ACTION_HOLD = "HOLD"
ACTION_TIGHTEN_SL = "TIGHTEN_SL"
ACTION_CLOSE_IF_PROFIT = "CLOSE_IF_PROFIT"

# Soft-close only when green enough to survive round-trip fees (~HL taker).
MIN_SOFT_CLOSE_PNL_PCT = 0.25


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


def _pnl_pct(side: str, entry: float, price: float) -> float:
    if entry <= 0 or price <= 0:
        return 0.0
    raw = (price - entry) / entry * 100.0
    return raw if side == "BUY" else -raw


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
