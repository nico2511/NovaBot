"""Pure live-trading guards: liquidation distance, entry slippage, fill abort.

Kept free of I/O so unit tests can lock the money rules without Hyperliquid.
"""
from __future__ import annotations

from typing import Optional, Tuple

LIQ_BUFFER_FRAC = 0.15
MAJOR_ENTRY_SLIPPAGE = 0.008  # 0.8% IOC cap for BTC/ETH/SOL
ALT_ENTRY_SLIPPAGE = 0.015  # 1.5% IOC cap for thinner perps
MAJOR_SYMBOLS = frozenset({"BTC", "ETH", "SOL"})
# Abort/close if realized fill exceeds max(2× configured slip, this floor).
MIN_FILL_ABORT_SLIPPAGE = 0.015


def entry_slippage_for_symbol(symbol: str) -> float:
    """IOC limit offset used to simulate a market entry."""
    coin = str(symbol or "").upper().replace("-USD", "").replace("-USDC", "").strip()
    if coin.startswith("K") and len(coin) > 2 and coin[1:].isalpha():
        coin = coin[1:]
    if coin in MAJOR_SYMBOLS:
        return MAJOR_ENTRY_SLIPPAGE
    return ALT_ENTRY_SLIPPAGE


def fill_slippage_breached(
    signal_px: Optional[float],
    avg_px: Optional[float],
    configured_slip: float,
) -> Tuple[bool, float]:
    """Return (should_abort, realized_slip_frac). Missing prices → no abort."""
    try:
        signal = float(signal_px or 0)
        avg = float(avg_px or 0)
    except (TypeError, ValueError):
        return False, 0.0
    if signal <= 0 or avg <= 0:
        return False, 0.0
    slip = abs(avg - signal) / signal
    limit = max(float(configured_slip or 0) * 2.0, MIN_FILL_ABORT_SLIPPAGE)
    return slip > limit, slip


def theoretical_isolated_liq(entry: float, side: str, leverage: int) -> float:
    """Conservative Isolated liq (ignore maintenance): long ≈ entry*(1-1/lev)."""
    entry = float(entry)
    lev = max(1, int(leverage or 1))
    side_u = str(side or "BUY").upper()
    if side_u in ("BUY", "LONG"):
        return entry * (1.0 - 1.0 / lev)
    return entry * (1.0 + 1.0 / lev)


def clamp_sl_inside_liquidation(
    *,
    side: str,
    entry: float,
    sl: Optional[float],
    leverage: int = 1,
    liquidation_price: Optional[float] = None,
    buffer_frac: float = LIQ_BUFFER_FRAC,
) -> Tuple[Optional[float], Optional[str]]:
    """Pull SL inside the liquidation band.

    Returns (sl, warning). ``sl is None`` means the stop is unusable — do not enter.
    """
    try:
        entry_px = float(entry)
        sl_px = float(sl or 0)
    except (TypeError, ValueError):
        return None, "invalid entry/SL"
    if entry_px <= 0:
        return None, "invalid entry"
    if sl_px <= 0:
        return None, "missing SL — live entry requires an exchange stop"

    side_u = str(side or "").upper()
    is_buy = side_u in ("BUY", "LONG")
    if not is_buy and side_u not in ("SELL", "SHORT"):
        return None, f"unknown side {side}"

    if is_buy and sl_px >= entry_px:
        return None, "SL is on the wrong side of entry for a long"
    if not is_buy and sl_px <= entry_px:
        return None, "SL is on the wrong side of entry for a short"

    liq = None
    try:
        if liquidation_price is not None and float(liquidation_price) > 0:
            liq = float(liquidation_price)
    except (TypeError, ValueError):
        liq = None
    if liq is None:
        liq = theoretical_isolated_liq(entry_px, side_u, leverage)

    gap = abs(entry_px - liq)
    buffer = gap * float(buffer_frac)

    if is_buy:
        min_sl = liq + buffer
        if sl_px < min_sl:
            return min_sl, (
                f"SL {sl_px:.6g} past Isolated liq ~{liq:.6g}; "
                f"clamped to {min_sl:.6g} (buffer {buffer_frac:.0%})"
            )
        return sl_px, None

    max_sl = liq - buffer
    if sl_px > max_sl:
        return max_sl, (
            f"SL {sl_px:.6g} past Isolated liq ~{liq:.6g}; "
            f"clamped to {max_sl:.6g} (buffer {buffer_frac:.0%})"
        )
    return sl_px, None
