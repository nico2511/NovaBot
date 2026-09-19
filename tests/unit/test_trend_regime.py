"""Strong-trend relax helpers and strategy wiring."""
from __future__ import annotations

from strategies.rocket import StrategyRocket
from strategies.supertrend import StrategySupertrend
from strategies.trend_lt import StrategyTrendLT
from strategies.trend_regime import (
    effective_min_adx_slope,
    effective_veto_volume_pct,
    is_strong_trend_from_context,
    is_strong_trend_from_setup,
)


def _get_param_factory(overrides=None):
    data = {
        "strong_trend_relax_enabled": True,
        "strong_trend_adx_min": 35,
        "strong_trend_max_rsi_long": 70,
        "strong_trend_min_adx_slope": -1.2,
        "strong_trend_veto_volume_pct": 55,
        "strong_trend_veto_macd_momentum": False,
        "adx_threshold": 22,
    }
    if overrides:
        data.update(overrides)

    def get_param(key, default=None):
        return data.get(key, default)

    return get_param


def test_strong_trend_setup_long():
    gp = _get_param_factory()
    assert is_strong_trend_from_setup(
        "LONG",
        adx=40,
        adx_threshold=22,
        close=110,
        ema=100,
        st_dir=1,
        get_param=gp,
    )
    assert not is_strong_trend_from_setup(
        "LONG",
        adx=30,
        adx_threshold=22,
        close=110,
        ema=100,
        st_dir=1,
        get_param=gp,
    )


def test_effective_min_adx_slope_relax():
    gp = _get_param_factory()
    assert effective_min_adx_slope(-0.55, True, gp) == -1.2
    assert effective_min_adx_slope(-0.55, False, gp) == -0.55


def test_supertrend_hard_veto_allows_volume_in_strong_trend():
    s = StrategySupertrend(
        {
            "params": {
                "min_volume_ratio_pct": 80,
                "strong_trend_veto_volume_pct": 55,
                "strong_trend_adx_min": 35,
                "adx_threshold": 22,
            }
        }
    )
    ctx = {
        "current_price": 100.0,
        "rsi": 55.0,
        "adx": 40.0,
        "volume_ratio": 62.0,
        "macd_hist": -1.0,
        "regime": "TREND",
        "market_bias": "BULLISH",
        "strong_trend": True,
    }
    assert s.check_hard_veto("BUY", ctx) is None


def test_supertrend_hard_veto_still_blocks_weak_volume_outside_strong():
    s = StrategySupertrend({"params": {"min_volume_ratio_pct": 80, "adx_threshold": 22}})
    ctx = {
        "current_price": 100.0,
        "rsi": 55.0,
        "adx": 25.0,
        "volume_ratio": 62.0,
        "macd_hist": 0.5,
        "regime": "TREND",
        "market_bias": "BULLISH",
    }
    reason = s.check_hard_veto("BUY", ctx)
    assert reason is not None
    assert "Low Volume" in reason


def test_trend_lt_context_strong_trend():
    gp = _get_param_factory({"strong_trend_adx_min": 32, "adx_threshold": 18})
    assert is_strong_trend_from_context(
        "BUY",
        {"adx_val": 45, "regime": "TREND", "market_bias": "BULLISH"},
        gp,
        adx_threshold=18,
    )


def test_rocket_relaxed_rsi_in_strong_trend():
    s = StrategyRocket(
        {
            "params": {
                "veto_rsi_overbought": 72,
                "min_volume_ratio_pct": 120,
                "volume_spike_pct": 120,
                "strong_trend_rsi_overbought": 78,
                "strong_trend_adx_min": 28,
            }
        }
    )
    ctx = {
        "regime": "TREND",
        "adx_val": 35,
        "rsi_val": 75,
        "volume_ratio": 200,
        "vol_slope": 50,
        "macd_hist": 0.01,
        "market_bias": "BULLISH",
    }
    assert s.check_hard_veto("BUY", ctx) is None
