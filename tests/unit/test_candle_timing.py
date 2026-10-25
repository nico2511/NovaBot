"""Tests for OHLCV forming-bar alignment."""
from __future__ import annotations

import pandas as pd

from app.core.candle_timing import current_bar_open, last_candle_is_forming


def _frame_with_last_open(open_ts: pd.Timestamp) -> pd.DataFrame:
    idx = pd.DatetimeIndex([open_ts - pd.Timedelta(hours=4), open_ts], tz="UTC")
    return pd.DataFrame(
        {
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.0, 2.0],
            "volume": [100.0, 100.0],
        },
        index=idx,
    )


def test_last_candle_is_forming_accepts_aligned_tail():
    now = pd.Timestamp("2026-01-15T14:30:00Z")
    forming = current_bar_open("4h", now=now)
    df = _frame_with_last_open(forming)
    ok, reason = last_candle_is_forming(df, "4h", now=now)
    assert ok is True
    assert reason == ""


def test_last_candle_is_forming_rejects_stale_tail():
    now = pd.Timestamp("2026-01-15T14:30:00Z")
    forming = current_bar_open("4h", now=now)
    stale = forming - pd.Timedelta(hours=4)
    df = _frame_with_last_open(stale)
    ok, reason = last_candle_is_forming(df, "4h", now=now)
    assert ok is False
    assert "forming open" in reason
