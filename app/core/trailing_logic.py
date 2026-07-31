"""
Trailing-Stop Decision Logic.

Pure function that, given a trade dict and the current price, decides whether
the stop-loss should be moved up (BUY) or down (SELL) and returns the new
value plus a short reason label. The caller — typically BotContext — is
responsible for applying the decision (persisting state, notifying Discord,
updating the exchange…). Keeping this module pure makes the stop-management
rules testable and explicit.

Rules (identical to the legacy BotContext._update_trailing_stops):
  - Smart Break-Even  at 60% progress (or >1.2% PnL on LONG) → lock 0.2% profit
  - Trailing Profit   at 65% progress → secure 20% of gains
  - Aggressive Lock   at 75% progress → secure 40% of gains
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class TrailingDecision:
    """Outcome of a trailing evaluation."""
    new_sl: float
    reason: str          # short human-readable label (e.g. "Smart BE", "Trailing 65%")
    progress_pct: float
    pnl_pct: float


def compute_trailing_decision(trade: dict, current_price: float) -> Optional[TrailingDecision]:
    """Return the best trailing-stop upgrade, or None if nothing should change.

    "Best" here means the tightest SL that is still an improvement over the
    current one — the Aggressive Lock wins over the Trailing Profit if both
    apply, because we evaluate in order and keep the last/highest value.
    """
    entry_price = trade.get("entry")
    tp_price = trade.get("tp")
    sl_price = trade.get("sl")
    side = trade.get("side")

    if not (entry_price and tp_price and sl_price) or side not in ("BUY", "SELL"):
        return None

    # Stale/missing quotes must never drive trailing (price=0 on a SHORT
    # looks like 100%+ progress toward TP and falsely tightens SL).
    try:
        if float(current_price) <= 0:
            return None
    except (TypeError, ValueError):
        return None

    entry_price = float(entry_price)
    tp_price = float(tp_price)
    sl_price = float(sl_price)

    # Guard against degenerate configurations (entry == tp) that would divide by zero.
    if side == "BUY":
        total_dist = tp_price - entry_price
        current_dist = current_price - entry_price
    else:
        total_dist = entry_price - tp_price
        current_dist = entry_price - current_price

    if total_dist <= 0:
        return None

    progress_pct = (current_dist / total_dist) * 100
    pnl_pct = (
        ((current_price - entry_price) / entry_price) * 100
        if side == "BUY"
        else ((entry_price - current_price) / entry_price) * 100
    )

    new_sl: Optional[float] = None
    reason = ""

    if side == "BUY":
        # 1. Smart BE
        if progress_pct > 60 or pnl_pct > 1.2:
            be_price = entry_price * 1.002
            if sl_price < be_price and current_price > (be_price * 1.003):
                new_sl = be_price
                reason = "Smart BE"

        # 2. Trailing 20%
        if progress_pct > 65:
            secure_price = entry_price + (total_dist * 0.20)
            if sl_price < secure_price and (new_sl is None or secure_price > new_sl):
                new_sl = secure_price
                reason = "Trailing 65%"

        # 3. Aggressive Lock 40%
        if progress_pct > 75:
            lock_price = entry_price + (total_dist * 0.40)
            if sl_price < lock_price and (new_sl is None or lock_price > new_sl):
                new_sl = lock_price
                reason = "Aggressive Lock 75%"

    else:  # SELL — mirror logic
        # 1. Smart BE
        if progress_pct > 60:
            be_price = entry_price * 0.998
            if sl_price > be_price and current_price < (be_price * 0.997):
                new_sl = be_price
                reason = "Smart BE"

        # 2. Trailing 20%
        if progress_pct > 65:
            secure_price = entry_price - (total_dist * 0.20)
            if sl_price > secure_price and (new_sl is None or secure_price < new_sl):
                new_sl = secure_price
                reason = "Trailing 65%"

        # 3. Aggressive Lock 40%
        if progress_pct > 75:
            lock_price = entry_price - (total_dist * 0.40)
            if sl_price > lock_price and (new_sl is None or lock_price < new_sl):
                new_sl = lock_price
                reason = "Aggressive Lock 75%"

    if new_sl is None:
        return None

    return TrailingDecision(
        new_sl=float(new_sl),
        reason=reason,
        progress_pct=float(progress_pct),
        pnl_pct=float(pnl_pct),
    )
