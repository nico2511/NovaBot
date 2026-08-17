"""Raw OHLCV (no RSI/ADX columns) must still yield rsi_val/adx_val for the AI prompt."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.utils.data_processing import get_dynamic_context


def _ohlcv(n=80, start=100.0):
    idx = pd.date_range("2024-01-01", periods=n, freq="1h")
    # Oscillating path so RSI/ADX are non-degenerate (pure drift → RSI≈0)
    wave = np.sin(np.linspace(0, 8 * np.pi, n)) * 3.0
    close = start + np.cumsum(np.full(n, 0.05)) + wave
    high = close + 0.8
    low = close - 0.8
    open_ = close - 0.05
    vol = np.linspace(800, 1200, n)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


def test_get_dynamic_context_computes_rsi_adx_on_raw_ohlcv():
    df = _ohlcv()
    assert "RSI_14" not in df.columns
    assert "ADX_14" not in df.columns
    ctx = get_dynamic_context(df)
    assert ctx.get("rsi_val") is not None
    assert ctx.get("adx_val") is not None
    assert isinstance(ctx["rsi_val"], (int, float))
    assert isinstance(ctx["adx_val"], (int, float))
    assert not pd.isna(ctx["rsi_val"])
    assert not pd.isna(ctx["adx_val"])
    assert 0 < ctx["rsi_val"] < 100
    assert ctx["adx_val"] > 0
    assert "rsi_slope" in ctx
    assert "adx_slope" in ctx
