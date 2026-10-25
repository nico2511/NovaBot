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


def test_a3_same_bar_blocks_repeat_signal_per_symbol_after_fill():
    s = StrategyA3EmaTrend4h({"params": {}})
    ts = pd.Timestamp("2024-06-01T12:00:00+00:00")
    s._mark_signal_bar(ts, "BTC")
    assert s._same_bar_already_signaled(ts, "BTC") is False
    s.mark_entry_fill(symbol="BTC")
    assert s._same_bar_already_signaled(ts, "BTC") is True
    assert s._same_bar_already_signaled(ts, "ETH") is False
    assert s._same_bar_already_signaled(pd.Timestamp("2024-06-01T16:00:00+00:00"), "BTC") is False


def test_a3_signal_has_no_exchange_tp():
    from unittest.mock import patch

    s = StrategyA3EmaTrend4h({"params": {"min_warmup_bars": 10, "atr_period": 3}})
    forming = pd.Timestamp.now(tz="UTC").floor("4h")
    n = 15
    idx = pd.DatetimeIndex(
        [forming - pd.Timedelta(hours=4 * (n - 1 - i)) for i in range(n)],
        tz="UTC",
    )
    close = np.linspace(100.0, 110.0, n)
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 1.0,
            "low": close - 1.0,
            "close": close,
            "volume": np.full(n, 1000.0),
        },
        index=idx,
    )
    with patch("strategies.a3_ema_trend_4h.detect_crossover_on_closed_bar", return_value="BUY"):
        sig = s.generate_signal(df, extra_data={"4h": df, "symbol": "BTC"})
    assert sig is not None
    assert sig.get("tp") is None
    assert sig.get("no_exchange_tp") is True


def test_a3_thesis_candle_limit_derived_from_warmup():
    s = StrategyA3EmaTrend4h({"params": {"min_warmup_bars": 300}})
    assert s.get_thesis_candle_limit() == 400


def test_a3_suppress_reentry_is_per_symbol():
    s = StrategyA3EmaTrend4h({"params": {}})
    s._suppress_reentry_after_exit["BTC"] = True
    assert s._suppress_reentry_after_exit.get("ETH") is not True


def test_a3_scan_opportunity_includes_timeframe():
    s = StrategyA3EmaTrend4h({"params": {}, "timeframe": "4h"})
    n = 130
    forming = pd.Timestamp.now(tz="UTC").floor("4h")
    idx = pd.DatetimeIndex(
        [forming - pd.Timedelta(hours=4 * (n - 1 - i)) for i in range(n)],
        tz="UTC",
    )
    df = pd.DataFrame(
        {
            "open": np.linspace(100, 110, n),
            "high": np.linspace(101, 111, n),
            "low": np.linspace(99, 109, n),
            "close": np.linspace(100, 110, n),
            "volume": np.full(n, 1000.0),
        },
        index=idx,
    )
    row = s.score_scan_candidate(df, symbol="BTC")
    assert row is not None
    assert row.get("timeframe") == "4h"
