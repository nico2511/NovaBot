"""
Trailing-Stop Decision Logic.

R-multiple ladder (strategy-agnostic). Initial risk is |entry − initial_sl|
(falls back to current SL). Progress toward TP is no longer the trigger.

  - 1.0R  → break-even (lock a hair of profit)
  - 1.5R  → lock 0.5R
  - 2.0R  → lock 1.0R

Per-trade overrides: ``trail_be_at_r``, ``trail_lock_at_r``, ``trail_lock_r``,
``trail_lock2_at_r``, ``trail_lock2_r``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

BE_AT_R = 1.0
LOCK_AT_R = 1.5
LOCK_R = 0.5
LOCK2_AT_R = 2.0
LOCK2_R = 1.0
BE_LOCK_FRAC = 0.002  # 0.2% beyond entry so fees don't flip a BE stop red


@dataclass(frozen=True)
class TrailingDecision:
    """Outcome of a trailing evaluation."""
    new_sl: float
    reason: str
    progress_pct: float
    pnl_pct: float
    r_multiple: float = 0.0


def _initial_risk(trade: dict, entry: float, side: str) -> Optional[float]:
    raw = trade.get("initial_sl", trade.get("sl"))
    try:
        sl0 = float(raw)
    except (TypeError, ValueError):
        return None
    if sl0 <= 0:
        return None
    if side == "BUY":
        risk = entry - sl0
    else:
        risk = sl0 - entry
    if risk <= 0:
        return None
    return risk


def _float_param(trade: dict, key: str, default: float) -> float:
    try:
        raw = trade.get(key)
        if raw is None:
            return default
        return float(raw)
    except (TypeError, ValueError):
        return default


def compute_trailing_decision(trade: dict, current_price: float) -> Optional[TrailingDecision]:
    """Return the tightest R-ladder SL upgrade, or None if nothing should change."""
    entry_price = trade.get("entry")
    tp_price = trade.get("tp")
    sl_price = trade.get("sl")
    side = trade.get("side")

    if not (entry_price and sl_price) or side not in ("BUY", "SELL"):
        return None

    try:
        if float(current_price) <= 0:
            return None
    except (TypeError, ValueError):
        return None

    entry_price = float(entry_price)
    sl_price = float(sl_price)
    try:
        tp_price = float(tp_price) if tp_price else 0.0
    except (TypeError, ValueError):
        tp_price = 0.0

    risk = _initial_risk(trade, entry_price, side)
    if risk is None:
        return None

    if side == "BUY":
        r_mult = (current_price - entry_price) / risk
        current_dist = current_price - entry_price
        total_dist = (tp_price - entry_price) if tp_price > entry_price else risk
    else:
        r_mult = (entry_price - current_price) / risk
        current_dist = entry_price - current_price
        total_dist = (entry_price - tp_price) if 0 < tp_price < entry_price else risk

    progress_pct = (current_dist / total_dist) * 100 if total_dist > 0 else 0.0
    pnl_pct = (
        ((current_price - entry_price) / entry_price) * 100
        if side == "BUY"
        else ((entry_price - current_price) / entry_price) * 100
    )

    be_at = _float_param(trade, "trail_be_at_r", BE_AT_R)
    lock_at = _float_param(trade, "trail_lock_at_r", LOCK_AT_R)
    lock_r = _float_param(trade, "trail_lock_r", LOCK_R)
    lock2_at = _float_param(trade, "trail_lock2_at_r", LOCK2_AT_R)
    lock2_r = _float_param(trade, "trail_lock2_r", LOCK2_R)

    new_sl: Optional[float] = None
    reason = ""

    if side == "BUY":
        if r_mult >= be_at:
            be_price = entry_price * (1.0 + BE_LOCK_FRAC)
            if sl_price < be_price and current_price > (be_price * 1.003):
                new_sl = be_price
                reason = "BE 1R"
        if r_mult >= lock_at:
            lock_price = entry_price + lock_r * risk
            if sl_price < lock_price and (new_sl is None or lock_price > new_sl):
                new_sl = lock_price
                reason = f"Lock {lock_r:g}R @ {lock_at:g}R"
        if r_mult >= lock2_at:
            lock_price = entry_price + lock2_r * risk
            if sl_price < lock_price and (new_sl is None or lock_price > new_sl):
                new_sl = lock_price
                reason = f"Lock {lock2_r:g}R @ {lock2_at:g}R"
    else:
        if r_mult >= be_at:
            be_price = entry_price * (1.0 - BE_LOCK_FRAC)
            if sl_price > be_price and current_price < (be_price * 0.997):
                new_sl = be_price
                reason = "BE 1R"
        if r_mult >= lock_at:
            lock_price = entry_price - lock_r * risk
            if sl_price > lock_price and (new_sl is None or lock_price < new_sl):
                new_sl = lock_price
                reason = f"Lock {lock_r:g}R @ {lock_at:g}R"
        if r_mult >= lock2_at:
            lock_price = entry_price - lock2_r * risk
            if sl_price > lock_price and (new_sl is None or lock_price < new_sl):
                new_sl = lock_price
                reason = f"Lock {lock2_r:g}R @ {lock2_at:g}R"

    if new_sl is None:
        return None

    return TrailingDecision(
        new_sl=float(new_sl),
        reason=reason,
        progress_pct=float(progress_pct),
        pnl_pct=float(pnl_pct),
        r_multiple=float(r_mult),
    )
