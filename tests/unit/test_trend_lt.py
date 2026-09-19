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
    persona = s.get_ai_persona()
    criteria = s.get_ai_validation_criteria()
    assert "LT" in persona.upper() or "SWING" in persona.upper()
    assert criteria
    assert "1h" in criteria.lower() or "LT" in criteria.upper()
    assert "72" in persona
    assert "150%" not in persona
    assert "150%" not in criteria


def test_trend_lt_rejects_without_1h():
    s = StrategyTrendLT({"params": {}})
    assert s.generate_signal(pd.DataFrame()) is None
    assert s.last_rejection_reason


def test_trend_lt_hard_veto_volume():
    s = StrategyTrendLT({"params": {}})
    ctx = {"current_price": 100.0, "rsi": 50.0, "adx": 25.0, "volume_ratio": 10.0, "macd_hist": 0.01}
    assert s.check_hard_veto("BUY", ctx) is not None


def test_trend_lt_hard_veto_blocks_bearish_macd():
    s = StrategyTrendLT({"params": {}})
    ctx = {"current_price": 100.0, "rsi": 50.0, "adx": 25.0, "volume_ratio": 80.0, "macd_hist": -0.002}
    reason = s.check_hard_veto("BUY", ctx)
    assert reason is not None
    assert "MACD" in reason


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


def test_trend_lt_geometry_rejects_trimmed_rr_below_min():
    s = StrategyTrendLT({"params": {"min_rr": 2.0}})
    n = 40
    close = np.full(n, 100.0)
    high = np.full(n, 101.0)
    high[-2] = 100.8  # nearest swing inside mechanical 2R target
    df = pd.DataFrame(
        {
            "open": close - 0.1,
            "high": high,
            "low": np.full(n, 99.0),
            "close": close,
            "volume": np.full(n, 1000.0),
        }
    )
    reason = s.geometry_reject_reason(
        {"signal": "BUY", "price": 100.0, "sl": 97.0, "tp": 106.0},
        df,
    )
    assert reason is not None
    assert "min_rr" in reason
    assert s._last_signal_bar is None


def test_trend_lt_generate_ignores_15m_engine_regime(monkeypatch):
    captured = {}
    import strategies.trend_lt as mod

    orig = mod.is_strong_trend_from_setup

    def spy(*args, **kwargs):
        captured["regime"] = kwargs.get("regime", "MISSING")
        return orig(*args, **kwargs)

    monkeypatch.setattr(mod, "is_strong_trend_from_setup", spy)
    s = StrategyTrendLT(
        {
            "params": {
                "cooldown_minutes": 0,
                "require_pullback": False,
                "adx_threshold": 1,
                "min_adx_slope": -50,
                "max_rsi_long": 100,
                "min_volume_ratio_pct": 0,
                "max_extension_atr": 99,
            }
        }
    )
    df = _ohlcv(n=250, start=100.0, drift=0.08)
    s.generate_signal(df, extra_data={"1h": df, "regime": "RANGE", "regime_adx": "RANGE"})
    assert "regime" in captured
    assert captured["regime"] is None
