"""A3 strategy contract tests."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.a3_ema_trend_4h import StrategyA3EmaTrend4h


def test_a3_persona_and_skip_geometry():
    s = StrategyA3EmaTrend4h({"params": {"min_rr": 0, "skip_ai_validation": True}})
    assert s.get_ai_persona()
    sig, reason = s.pre_ai_geometry_veto({"signal": "BUY", "price": 100, "sl": 90, "tp": 50})
    assert reason is None
    assert sig["price"] == 100


def test_a3_same_bar_blocks_repeat_signal():
    s = StrategyA3EmaTrend4h({"params": {}})
    ts = pd.Timestamp("2024-06-01T12:00:00+00:00")
    s._mark_signal_bar(ts)
    assert s._same_bar_already_signaled(ts) is True
    assert s._same_bar_already_signaled(pd.Timestamp("2024-06-01T16:00:00+00:00")) is False
