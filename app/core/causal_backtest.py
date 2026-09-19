"""
Causal replay helpers — confirmed bars only, with Hyperliquid-like costs.

This is a harness, not a walk-forward study. Callers must pass OHLCV frames
that already exclude look-ahead (signal at bar i uses df.iloc[: i + 1] with
the last row treated as forming).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

import pandas as pd

# HL taker ~0.045% per side.
TAKER_FEE = 0.00045
DEFAULT_SLIP_FRAC = 0.0001  # 1 bp per fill


@dataclass(frozen=True)
class ReplayFill:
    index: Any
    side: str
    price: float
    sl: float
    tp: float
    strategy: str


def round_trip_cost_frac(*, taker: float = TAKER_FEE, slip: float = DEFAULT_SLIP_FRAC) -> float:
    """Round-trip cost as a fraction of price (entry + exit, fees + slip)."""
    return (2.0 * float(taker)) + (2.0 * float(slip))


def net_r(
    gross_r: float,
    *,
    sl_frac: float,
    taker: float = TAKER_FEE,
    slip: float = DEFAULT_SLIP_FRAC,
) -> float:
    """Convert a gross R result into net R after round-trip costs."""
    if sl_frac <= 0:
        return float(gross_r)
    cost_r = round_trip_cost_frac(taker=taker, slip=slip) / float(sl_frac)
    return float(gross_r) - cost_r


def walk_closed_bars(
    df: pd.DataFrame,
    strategy,
    *,
    extra_data_fn: Optional[Callable[[pd.DataFrame, int], Dict[str, Any]]] = None,
    warmup: int = 80,
) -> List[ReplayFill]:
    """
    Replay ``generate_signal`` causally.

    At index ``i`` the strategy sees ``df.iloc[: i + 1]`` (last row = forming bar)
    and any extra frames from ``extra_data_fn``. A fill, if any, is tagged on the
    confirmed bar ``iloc[-2]``.
    """
    fills: List[ReplayFill] = []
    if df is None or getattr(df, "empty", True) or len(df) < warmup + 2:
        return fills
    name = getattr(strategy, "name", strategy.__class__.__name__)
    for i in range(warmup, len(df)):
        window = df.iloc[: i + 1]
        extra = extra_data_fn(window, i) if extra_data_fn else None
        sig = strategy.generate_signal(window, extra_data=extra)
        if not isinstance(sig, dict):
            continue
        side = str(sig.get("signal") or "")
        if side not in ("BUY", "SELL"):
            continue
        try:
            price = float(sig["price"])
            sl = float(sig["sl"])
            tp = float(sig["tp"])
        except (KeyError, TypeError, ValueError):
            continue
        fills.append(
            ReplayFill(
                index=window.index[-2],
                side=side,
                price=price,
                sl=sl,
                tp=tp,
                strategy=str(sig.get("strategy") or name),
            )
        )
    return fills
