"""TF-coherent overlays: no 15m cascade leak into AI/hard-veto context."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.bot import BotContext
from app.utils.market_metrics import volume_ratio_for_gate


def _vol_df(confirmed_vol: float, live_vol: float, hist: float = 1000.0, n: int = 60):
    vol = np.full(n, hist)
    vol[-2] = confirmed_vol
    vol[-1] = live_vol
    close = np.linspace(10.0, 12.0, n)
    return pd.DataFrame(
        {
            "open": close - 0.01,
            "high": close + 0.02,
            "low": close - 0.02,
            "close": close,
            "volume": vol,
        }
    )


def test_overlay_cascade_keeps_ai_range_regime():
    ctx = {"regime": "RANGE", "volume_ratio": 40.0, "adx_val": 18.0}
    tech = {
        "regime": "TREND_BULL_STRONG",
        "regime_adx": "RANGE",
        "volume_ratio": 40.0,
    }
    out = BotContext._apply_strategy_tape_overlay(
        ctx,
        sig_tf="15m",
        technical_context=tech,
        ai_df=_vol_df(400.0, 400.0),
        strat_name="rocket",
    )
    assert out["regime"] == "RANGE"


def test_overlay_cascade_uses_live_volume_spike():
    df = _vol_df(confirmed_vol=500.0, live_vol=3000.0)
    ctx = {"regime": "RANGE", "volume_ratio": 50.0}
    out = BotContext._apply_strategy_tape_overlay(
        ctx,
        sig_tf="15m",
        technical_context={"regime": "TREND_BULL_STRONG", "volume_ratio": 50.0},
        ai_df=df,
        strat_name="rocket",
    )
    expected = round(float(volume_ratio_for_gate(df, live_cascade=True)), 1)
    assert out["volume_ratio"] == expected
    assert out["volume_ratio"] > 100.0
    assert out["regime"] == "RANGE"


def test_overlay_spark_uses_5m_live_volume():
    df = _vol_df(confirmed_vol=400.0, live_vol=2500.0)
    ctx = {"regime": "TREND", "volume_ratio": 40.0}
    out = BotContext._apply_strategy_tape_overlay(
        ctx,
        sig_tf="5m",
        technical_context={"regime": "RANGE", "volume_ratio": 20.0},
        ai_df=df,
        strat_name="spark",
    )
    expected = round(float(volume_ratio_for_gate(df, live_cascade=True)), 1)
    assert out["volume_ratio"] == expected
    assert out["regime"] == "TREND"


def test_overlay_supertrend_uses_adx_regime_not_cascade_label():
    ctx = {"regime": "TREND"}
    tech = {
        "regime": "TREND_BULL_STRONG",
        "regime_adx": "RANGE",
        "volume_ratio": 90.0,
    }
    out = BotContext._apply_strategy_tape_overlay(
        ctx,
        sig_tf="15m",
        technical_context=tech,
        ai_df=None,
        strat_name="supertrend",
    )
    assert out["regime"] == "RANGE"
    assert out["volume_ratio"] == 90.0


def test_overlay_trend_lt_ignores_15m_snapshot():
    ctx = {"regime": "TREND", "volume_ratio": 80.0}
    tech = {"regime": "RANGE", "regime_adx": "RANGE", "volume_ratio": 20.0}
    out = BotContext._apply_strategy_tape_overlay(
        ctx,
        sig_tf="1h",
        technical_context=tech,
        ai_df=None,
        strat_name="trend_lt",
    )
    assert out["regime"] == "TREND"
    assert out["volume_ratio"] == 80.0
