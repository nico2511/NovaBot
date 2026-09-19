"""Confirmed-bar ST/ADX overlay: live OHLC must not repaint iloc[-2]."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.supertrend import StrategySupertrend


def _ohlcv(n=250):
    idx = pd.date_range("2024-01-01", periods=n, freq="15min")
    close = 100.0 + np.cumsum(np.linspace(0.01, 0.02, n))
    return pd.DataFrame(
        {
            "open": close - 0.05,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.full(n, 1000.0),
        },
        index=idx,
    )


def test_supertrend_confirmed_adx_ignores_live_bar():
    s = StrategySupertrend({"params": {}})
    df = _ohlcv()
    base = s.add_indicators(df.copy())
    mutated = df.copy()
    mutated.loc[mutated.index[-1], ["open", "high", "low", "close"]] = (
        80.0,
        140.0,
        70.0,
        130.0,
    )
    warped = s.add_indicators(mutated)
    assert float(base["ADX_14"].iloc[-2]) == float(warped["ADX_14"].iloc[-2])
    assert float(base["Supertrend"].iloc[-2]) == float(warped["Supertrend"].iloc[-2])
    assert float(base["ATR_14"].iloc[-2]) == float(warped["ATR_14"].iloc[-2])
