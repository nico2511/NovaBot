"""Unit tests for SuperTrend SL construction / quality helpers."""
from strategies.supertrend import StrategySupertrend


def test_build_sl_tp_long_respects_min_sl_pct():
    strat = StrategySupertrend({"params": {}})
    p = strat._params_snapshot()
    p["min_sl_pct"] = 0.8
    p["sl_atr_mult"] = 1.0
    p["rr_ratio"] = 2.0
    # Tight ST just below entry + tiny ATR would previously create ~0.2% SL
    sl, tp = strat._build_sl_tp("LONG", entry=100.0, st_15m=99.8, atr_val=0.2, p=p)
    assert sl is not None and tp is not None
    assert (100.0 - sl) / 100.0 >= 0.0079  # ~0.8%
    assert tp > 100.0
    assert abs((tp - 100.0) / (100.0 - sl) - 2.0) < 0.05


def test_build_sl_tp_short_widens_with_atr():
    strat = StrategySupertrend({"params": {}})
    p = strat._params_snapshot()
    p["min_sl_pct"] = 0.5
    p["sl_atr_mult"] = 2.0
    p["rr_ratio"] = 2.0
    sl, tp = strat._build_sl_tp("SHORT", entry=100.0, st_15m=100.2, atr_val=1.0, p=p)
    assert sl is not None
    assert sl >= 102.0  # at least 2x ATR above entry
    assert tp < 100.0


def test_pullback_to_st_detects_tag():
    import pandas as pd
    import numpy as np

    strat = StrategySupertrend({"params": {}})
    n = 40
    idx = pd.date_range("2026-01-01", periods=n, freq="1min", tz="UTC")
    # Price dips to ST=100 then recovers; last bar is live (ignored)
    close = np.full(n, 103.0)
    low = np.full(n, 102.5)
    high = np.full(n, 103.5)
    low[20] = 100.2  # tag ST band
    close[20] = 100.5
    df = pd.DataFrame({"open": close, "high": high, "low": low, "close": close}, index=idx)
    assert strat._pullback_to_st_ok(df, "LONG", st_15m=100.0, atr_15m=1.0, lookback=30, touch_atr=1.0) is True
    # No tag if lows stay far above ST
    low[:] = 104.0
    df2 = pd.DataFrame({"open": close, "high": high, "low": low, "close": close}, index=idx)
    assert strat._pullback_to_st_ok(df2, "LONG", st_15m=100.0, atr_15m=1.0, lookback=30, touch_atr=1.0) is False
