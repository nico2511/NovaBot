"""Compute TA on confirmed bars so a forming candle cannot repaint ST/ADX/ATR."""
from __future__ import annotations

from typing import Callable

import pandas as pd

_OHLCV = frozenset({"open", "high", "low", "close", "volume"})


def closed_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Drop the forming bar when present; otherwise return ``df``."""
    if df is None or getattr(df, "empty", True) or len(df) < 2:
        return df
    return df.iloc[:-1]


def overlay_closed_indicators(
    df: pd.DataFrame,
    builder: Callable[[pd.DataFrame], pd.DataFrame],
) -> pd.DataFrame:
    """
    Run ``builder`` on confirmed bars and ffill indicator columns onto the live bar.

    ``builder`` receives a copy of ``df.iloc[:-1]`` (or ``df`` if too short) and
    must return a frame that includes the indicator columns to overlay.
    OHLCV columns on the original frame are left untouched.
    """
    work = df.copy()
    if work is None or getattr(work, "empty", True):
        return work
    src = work.iloc[:-1].copy() if len(work) >= 2 else work.copy()
    built = builder(src)
    if built is None or getattr(built, "empty", True):
        return work
    for col in built.columns:
        if col in _OHLCV:
            continue
        work[col] = built[col].reindex(work.index, method="ffill")
    return work
