"""Shared volume / swing arithmetic — one formula for scan, entry, veto, logs."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.utils.market_metrics import (
    confirmed_volume_ratio_pct,
    live_volume_ratio_pct,
    structural_swings,
    volume_ratio_for_gate,
)


def _vol_df(confirmed_vol: float, live_vol: float, hist: float = 1000.0, n: int = 60):
    vol = np.full(n, hist)
    vol[-2] = confirmed_vol
    vol[-1] = live_vol
    close = np.linspace(10.0, 12.0, n)
    return pd.DataFrame(
        {
            "open": close - 0.01,
            "high": close + 0.02,
            "low": close - 0.02,
            "close": close,
            "volume": vol,
        }
    )


def test_confirmed_volume_ratio_uses_closed_bar_and_includes_it_in_ma():
    df = _vol_df(confirmed_vol=500.0, live_vol=9.0, hist=1000.0, n=60)
    # MA50 of confirmed series: 49*1000 + 500 = 49500 / 50 = 990
    ratio = confirmed_volume_ratio_pct(df)
    assert ratio is not None
    assert abs(ratio - (500.0 / 990.0) * 100.0) < 0.05
    # Live bar must not enter the ratio
    live = live_volume_ratio_pct(df)
    assert live is not None
    assert live < 2.0


def test_cascade_gate_takes_max_of_confirmed_and_live_spike():
    df = _vol_df(confirmed_vol=500.0, live_vol=3000.0, hist=1000.0, n=60)
    confirmed = confirmed_volume_ratio_pct(df)
    live = live_volume_ratio_pct(df)
    gated = volume_ratio_for_gate(df, live_cascade=True)
    assert gated == max(confirmed, live)
    assert gated > 100.0
    trend_gate = volume_ratio_for_gate(df, live_cascade=False)
    assert trend_gate == confirmed


def test_structural_swings_ignore_live_wick():
    n = 30
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    low = np.full(n, 99.0)
    high[-2] = 105.0  # confirmed swing
    high[-1] = 120.0  # live wick must not count
    low[-2] = 94.0
    low[-1] = 80.0
    df = pd.DataFrame(
        {
            "open": close,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(n, 1.0),
        }
    )
    sh, sl = structural_swings(df, lookback=20)
    assert sh == 105.0
    assert sl == 94.0
