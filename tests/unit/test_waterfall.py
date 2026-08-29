"""Waterfall strategy contract + signal / scan / thesis paths."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.trade_thesis import THESIS_DEAD, evaluate_waterfall_thesis
from strategies.waterfall import StrategyWaterfall, detect_waterfall


def _bear_cascade_15m(n=80, start=10.0):
    """Build declining 15m series ending in a waterfall live bar."""
    idx = pd.date_range("2024-06-01", periods=n, freq="15min")
    close = start - np.linspace(0, 2.5, n)
    close[-3:] = [close[-4], close[-4] - 0.15, close[-4] - 0.35]
    open_ = close + 0.08
    open_[-2:] = close[-2:] + 0.12
    open_[-1] = close[-1] + 0.10
    high = np.maximum(open_, close) + 0.02
    low = np.minimum(open_, close) - 0.02
    low[-1] = close[-1] - 0.03
    low[-2] = close[-2] - 0.02
    vol = np.full(n, 5000.0)
    vol[-1] = 12000.0
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


def _bear_1m_confirm(n=30, anchor=7.5):
    idx = pd.date_range("2024-06-01", periods=n, freq="1min")
    close = np.full(n, anchor)
    close[-2] = anchor - 0.04
    close[-1] = anchor - 0.05
    open_ = close + 0.03
    low = close - 0.01
    low[-2] = close[-2] - 0.02
    low[-3] = close[-3] - 0.01
    high = open_ + 0.01
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": np.full(n, 100.0)},
        index=idx,
    )


def test_waterfall_persona_and_criteria():
    s = StrategyWaterfall({"params": {}})
    assert "WATERFALL" in s.get_ai_persona().upper()
    assert s.get_ai_validation_criteria()
    assert "SELL" in s.get_ai_validation_criteria()


def test_waterfall_hard_veto_blocks_buy():
    s = StrategyWaterfall({"params": {}})
    assert s.check_hard_veto("BUY", {"volume_ratio": 100, "rsi": 40}) is not None


def test_waterfall_hard_veto_blocks_low_volume():
    s = StrategyWaterfall({"params": {}})
    ctx = {"volume_ratio": 20, "rsi": 35, "regime": "TREND_BEAR_STRONG"}
    assert s.check_hard_veto("SELL", ctx) is not None


def test_waterfall_hard_veto_blocks_dying_volume():
    s = StrategyWaterfall({"params": {}})
    ctx = {"volume_ratio": 130, "rsi": 35, "vol_slope": -39.0}
    reason = s.check_hard_veto("SELL", ctx)
    assert reason is not None
    assert "dying" in reason.lower() or "fuel" in reason.lower()


def test_waterfall_rejects_insufficient_data():
    s = StrategyWaterfall({"params": {}})
    assert s.generate_signal(pd.DataFrame()) is None
    assert s.last_rejection_reason


def test_detect_waterfall_on_synthetic():
    df = _bear_cascade_15m()
    s = StrategyWaterfall({"params": {}})
    df = s.add_indicators(df)
    active, snap = detect_waterfall(df, use_live=True)
    assert active is True
    assert snap.get("ema9", 0) > 0


_HAPPY_PARAMS = {
    "cooldown_minutes": 0,
    "veto_rsi_oversold": 0,
    "struct_lookback": 500,
    "veto_vol_slope_min": -100,
}


def test_waterfall_generate_signal_short():
    s = StrategyWaterfall({"params": dict(_HAPPY_PARAMS)})
    df_15m = _bear_cascade_15m()
    df_1m = _bear_1m_confirm()
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is not None
    assert sig["signal"] == "SELL"
    assert sig["sl"] > sig["price"] > sig["tp"]
    assert sig.get("cascade_ema9") is not None


def test_waterfall_rejects_dying_volume_on_signal():
    s = StrategyWaterfall(
        {
            "params": {
                "cooldown_minutes": 0,
                "veto_rsi_oversold": 0,
                "struct_lookback": 500,
                "veto_vol_slope_min": -30,
            }
        }
    )
    df_15m = _bear_cascade_15m()
    df_15m.loc[df_15m.index[-3], "volume"] = 20000.0
    df_15m.loc[df_15m.index[-2], "volume"] = 8000.0
    df_1m = _bear_1m_confirm()
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is None
    assert "dying" in (s.last_rejection_reason or "").lower() or "soft" in (
        s.last_rejection_reason or ""
    ).lower()


def test_waterfall_rejects_prior_support_without_spike():
    """Revisit of an earlier swing low without volume spike (double-bottom fade)."""
    s = StrategyWaterfall(
        {
            "params": {
                "cooldown_minutes": 0,
                "veto_rsi_oversold": 0,
                "veto_vol_slope_min": -100,
                "struct_lookback": 40,
                "struct_exclude_bars": 3,
                "floor_proximity_pct": 0.5,
                "breakdown_clear_pct": 0.15,
                "volume_spike_pct": 120,
            }
        }
    )
    df_15m = _bear_cascade_15m()
    tip = float(df_15m["close"].iloc[-1])
    df_1m = _bear_1m_confirm(anchor=tip)
    entry = float(df_1m["close"].iloc[-2])
    df_15m.loc[df_15m.index[30:40], "low"] = entry
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is None
    low = (s.last_rejection_reason or "").lower()
    assert "support" in low or "spike" in low


def test_waterfall_scan_scores_cascade():
    s = StrategyWaterfall(
        {"params": {"veto_rsi_oversold": 0, "struct_lookback": 500, "veto_vol_slope_min": -100}}
    )
    df = s.add_indicators(_bear_cascade_15m())
    row = s.score_scan_candidate(df, symbol="TEST")
    assert row is not None
    assert row["bias"] == "SHORT"
    assert row["score"] >= 65


def test_waterfall_thesis_dead_on_ema_reclaim():
    verdict = evaluate_waterfall_thesis(
        side="SELL",
        entry=10.0,
        current_price=9.5,
        close_15m=10.2,
        ema9=10.0,
        rsi=45,
        prev_open=9.8,
        prev_close=9.9,
        prev_high=10.0,
    )
    assert verdict.status == THESIS_DEAD


def test_waterfall_supports_trade_thesis():
    s = StrategyWaterfall({"params": {}})
    assert s.supports_trade_thesis() is True
    assert s.get_thesis_timeframe() == "15m"
