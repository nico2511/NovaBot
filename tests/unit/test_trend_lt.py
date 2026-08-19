"""Trend LT strategy contract + basic reject paths."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.trend_lt import StrategyTrendLT


def _ohlcv(n=250, start=100.0, drift=0.05):
    idx = pd.date_range("2024-01-01", periods=n, freq="1h")
    close = start + np.cumsum(np.full(n, drift))
    high = close + 0.5
    low = close - 0.5
    open_ = close - 0.1
    vol = np.full(n, 1000.0)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


def test_trend_lt_persona_and_criteria():
    s = StrategyTrendLT({"params": {}})
    assert "LT" in s.get_ai_persona().upper() or "SWING" in s.get_ai_persona().upper()
    assert s.get_ai_validation_criteria()
    assert "1h" in s.get_ai_validation_criteria().lower() or "LT" in s.get_ai_validation_criteria().upper()


def test_trend_lt_rejects_without_1h():
    s = StrategyTrendLT({"params": {}})
    assert s.generate_signal(pd.DataFrame()) is None
    assert s.last_rejection_reason


def test_trend_lt_hard_veto_volume():
    s = StrategyTrendLT({"params": {}})
    ctx = {"current_price": 100.0, "rsi": 50.0, "adx": 25.0, "volume_ratio": 10.0}
    assert s.check_hard_veto("BUY", ctx) is not None


def test_trend_lt_rejects_short_history():
    s = StrategyTrendLT({"params": {"ema_filter_period": 200}})
    df = _ohlcv(50)
    assert s.generate_signal(df, extra_data={"1h": df}) is None


def test_trend_lt_post_ai_adjust_trims_buy_tp():
    s = StrategyTrendLT({"params": {}})
    signal = {"signal": "BUY", "price": 100.0, "tp": 110.0, "sl": 99.0}
    ai = {"approved": True, "reasoning": "x", "suggested_adjustments": {}}
    out = s.post_ai_adjust(signal, ai, {"swing_high": 105.0, "swing_low": 90.0})
    assert out["suggested_adjustments"]["tp"] < 105.0
    assert out["suggested_adjustments"]["tp"] > 100.0


def test_trend_lt_supports_trade_thesis():
    s = StrategyTrendLT({"params": {}})
    assert s.supports_trade_thesis() is True
    assert s.get_thesis_timeframe() == "1h"
    assert s.evaluate_trade_thesis({}, 100.0, df=None) is None
