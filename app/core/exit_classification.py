"""Classify exchange-synced closes against the trade's planned SL/TP."""
from __future__ import annotations

from typing import Optional

EXIT_TAKE_PROFIT = "TAKE_PROFIT"
EXIT_STOP_LOSS = "STOP_LOSS"
EXIT_SYNC_UNCLASSIFIED = "External/Sync Close"


def classify_sync_exit_reason(
    side: str,
    exit_price: float,
    *,
    sl: Optional[float] = None,
    tp: Optional[float] = None,
    tol_pct: float = 0.002,
) -> str:
    """
    Infer why an exchange fill closed the position.

    Hyperliquid SL/TP often fill before the bot's local watcher runs, so the
    sync path historically recorded everything as ``External/Sync Close``.
    When planned levels are still on the trade, map the fill to TP or SL
    (with a small relative tolerance for slippage).
    """
    try:
        px = float(exit_price)
    except (TypeError, ValueError):
        return EXIT_SYNC_UNCLASSIFIED
    if px <= 0:
        return EXIT_SYNC_UNCLASSIFIED

    side_u = str(side or "").upper()
    try:
        sl_v = float(sl or 0)
    except (TypeError, ValueError):
        sl_v = 0.0
    try:
        tp_v = float(tp or 0)
    except (TypeError, ValueError):
        tp_v = 0.0

    tol = max(float(tol_pct), 0.0)
    hit_tp = False
    hit_sl = False

    if side_u == "BUY":
        if tp_v > 0 and px >= tp_v * (1.0 - tol):
            hit_tp = True
        if sl_v > 0 and px <= sl_v * (1.0 + tol):
            hit_sl = True
    elif side_u == "SELL":
        if tp_v > 0 and px <= tp_v * (1.0 + tol):
            hit_tp = True
        if sl_v > 0 and px >= sl_v * (1.0 - tol):
            hit_sl = True
    else:
        return EXIT_SYNC_UNCLASSIFIED

    if hit_tp and not hit_sl:
        return EXIT_TAKE_PROFIT
    if hit_sl and not hit_tp:
        return EXIT_STOP_LOSS
    if hit_tp and hit_sl:
        # Degenerate / overlapping levels — pick the closer planned price.
        d_tp = abs(px - tp_v) if tp_v > 0 else float("inf")
        d_sl = abs(px - sl_v) if sl_v > 0 else float("inf")
        return EXIT_TAKE_PROFIT if d_tp <= d_sl else EXIT_STOP_LOSS

    return EXIT_SYNC_UNCLASSIFIED
