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
