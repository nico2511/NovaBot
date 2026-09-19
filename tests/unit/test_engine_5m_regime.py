"""Engine regime gating for fast 5m cascade riders (spark / ember)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.engine import StrategyEngine
from tests.unit.test_ember import _bear_cascade_5m
from tests.unit.test_spark import _bull_cascade_5m


def _range_15m_df(n=100):
    """Flat 15m series — ADX stays low → RANGE regime."""
    idx = pd.date_range("2024-06-01", periods=n, freq="15min")
    close = np.full(n, 100.0)
    open_ = close.copy()
    high = close + 0.001
    low = close - 0.001
    vol = np.full(n, 1000.0)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


def test_spark_inactive_on_5m_cascade_in_range_regime():
    """5m riders must not bypass a 15m RANGE tape."""
    engine = StrategyEngine()
    engine.config = {
        "market_regime": {"adx_threshold": 22},
        "spark": {"enabled": True, "type": "trend", "params": {"allow_longs": True}},
        "rocket": {"enabled": False, "type": "trend"},
    }
    df_15m = _range_15m_df()
    df_5m = _bull_cascade_5m()
    result = engine.analyze(
        df_15m,
        extra_data={"symbol": "ALT", "5m": df_5m, "1m": pd.DataFrame()},
    )
    assert result.get("regime") == "RANGE"
    assert "spark" not in result.get("strategies", [])


def test_ember_inactive_on_5m_cascade_in_range_regime():
    engine = StrategyEngine()
    engine.config = {
        "market_regime": {"adx_threshold": 22},
        "ember": {"enabled": True, "type": "trend", "params": {"allow_shorts": True}},
        "waterfall": {"enabled": False, "type": "trend"},
    }
    df_15m = _range_15m_df()
    df_5m = _bear_cascade_5m()
    result = engine.analyze(
        df_15m,
        extra_data={"symbol": "ALT", "5m": df_5m, "1m": pd.DataFrame()},
    )
    assert result.get("regime") == "RANGE"
    assert "ember" not in result.get("strategies", [])


def test_spark_inactive_without_5m_cascade_in_range():
    engine = StrategyEngine()
    engine.config = {
        "market_regime": {"adx_threshold": 22},
        "spark": {"enabled": True, "type": "trend"},
    }
    df_15m = _range_15m_df()
    flat_5m = df_15m.copy()
    result = engine.analyze(
        df_15m,
        extra_data={"symbol": "ALT", "5m": flat_5m},
    )
    assert result.get("regime") == "RANGE"
    assert "spark" not in result.get("strategies", [])


def test_forming_15m_cascade_does_not_set_bull_strong():
    """Live-bar-only rocket must not rewrite the 15m regime overlay."""
    engine = StrategyEngine()
    engine.config = {
        "market_regime": {"adx_threshold": 22},
        "rocket": {"enabled": True, "type": "trend"},
        "supertrend": {"enabled": False, "type": "trend"},
    }
    df = _range_15m_df()
    # Confirmed bar (-2) is green but previous (-3) is not → no confirmed cascade.
    # Live bar (-1) completes a live cascade (double green + HH).
    df.loc[df.index[-2], ["open", "close", "high", "low"]] = (100.00, 100.25, 100.28, 99.99)
    df.loc[df.index[-1], ["open", "close", "high", "low"]] = (100.25, 100.55, 100.60, 100.24)
    result = engine.analyze(df, extra_data={"symbol": "ALT"})
    assert result.get("regime") == "RANGE"
    assert "rocket" not in result.get("strategies", [])
