"""Ember strategy contract + signal / scan / thesis paths."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.trade_thesis import THESIS_DEAD, evaluate_waterfall_thesis
from strategies.ember import StrategyEmber, detect_ember


def _bear_cascade_5m(n=80, start=10.0):
    idx = pd.date_range("2024-06-01", periods=n, freq="5min")
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


def test_ember_persona_and_criteria():
    s = StrategyEmber({"params": {}})
    assert "EMBER" in s.get_ai_persona().upper()
    assert s.get_ai_validation_criteria()
    assert "SELL" in s.get_ai_validation_criteria()


def test_ember_hard_veto_blocks_buy():
    s = StrategyEmber({"params": {}})
    assert s.check_hard_veto("BUY", {"volume_ratio": 100, "rsi": 40}) is not None


def test_ember_hard_veto_blocks_low_volume():
    s = StrategyEmber({"params": {}})
    ctx = {"volume_ratio": 20, "rsi": 35, "regime": "TREND_BEAR_STRONG"}
    assert s.check_hard_veto("SELL", ctx) is not None


def test_ember_hard_veto_blocks_dying_volume():
    s = StrategyEmber({"params": {}})
    ctx = {"volume_ratio": 130, "rsi": 35, "vol_slope": -39.0}
    reason = s.check_hard_veto("SELL", ctx)
    assert reason is not None
    assert "dying" in reason.lower() or "fuel" in reason.lower()


def test_ember_hard_veto_allows_stable_volume():
    s = StrategyEmber({"params": {}})
    ctx = {"volume_ratio": 130, "rsi": 35, "vol_slope": -10.0}
    assert s.check_hard_veto("SELL", ctx) is None


def test_ember_rejects_insufficient_data():
    s = StrategyEmber({"params": {}})
    assert s.generate_signal(pd.DataFrame()) is None
    assert s.last_rejection_reason


def test_detect_ember_on_synthetic():
    df = _bear_cascade_5m()
    s = StrategyEmber({"params": {}})
    df = s.add_indicators(df)
    active, snap = detect_ember(df, use_live=True)
    assert active is True
    assert snap.get("ema9", 0) > 0


_HAPPY_PARAMS = {
    "cooldown_minutes": 0,
    "veto_rsi_oversold": 0,
    "struct_lookback": 500,
    "veto_vol_slope_min": -100,
    "max_extension_atr": 10,
}


def test_ember_generate_signal_short():
    s = StrategyEmber({"params": dict(_HAPPY_PARAMS)})
    df_5m = _bear_cascade_5m()
    df_1m = _bear_1m_confirm()
    sig = s.generate_signal(pd.DataFrame(), extra_data={"5m": df_5m, "1m": df_1m})
    assert sig is not None
    assert sig["signal"] == "SELL"
    assert sig["tp"] < sig["price"] < sig["sl"]
    assert sig.get("cascade_ema9") is not None


def test_ember_rejects_prior_support_without_spike():
    s = StrategyEmber(
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
                "max_extension_atr": 10,
            }
        }
    )
    df_5m = _bear_cascade_5m()
    tip = float(df_5m["close"].iloc[-1])
    df_1m = _bear_1m_confirm(anchor=tip)
    entry = float(df_1m["close"].iloc[-2])
    df_5m.loc[df_5m.index[30:40], "low"] = entry
    sig = s.generate_signal(pd.DataFrame(), extra_data={"5m": df_5m, "1m": df_1m})
    assert sig is None
    assert s.last_rejection_reason
    low = s.last_rejection_reason.lower()
    assert "support" in low
    assert "breakdown" in low or "absorption" in low


def test_ember_at_prior_floor_helper():
    s = StrategyEmber({"params": {}})
    p = s._params_snapshot()
    assert s._at_prior_floor(8.0, 8.0, p) is True
    assert s._at_prior_floor(9.0, 8.0, p) is False
    clear_p = {**p, "breakdown_clear_pct": 0.20}
    assert s._at_prior_floor(7.95, 8.0, clear_p) is False
    assert s._at_prior_floor(7.99, 8.0, clear_p) is True


def test_ember_rejects_dying_volume_on_signal():
    s = StrategyEmber(
        {
            "params": {
                "cooldown_minutes": 0,
                "veto_rsi_oversold": 0,
                "struct_lookback": 500,
                "veto_vol_slope_min": -30,
                "max_extension_atr": 10,
            }
        }
    )
    df_5m = _bear_cascade_5m()
    df_5m.loc[df_5m.index[-3], "volume"] = 20000.0
    df_5m.loc[df_5m.index[-2], "volume"] = 8000.0
    df_1m = _bear_1m_confirm()
    sig = s.generate_signal(pd.DataFrame(), extra_data={"5m": df_5m, "1m": df_1m})
    assert sig is None
    assert "dying" in (s.last_rejection_reason or "").lower() or "soft" in (
        s.last_rejection_reason or ""
    ).lower()


def test_ember_scan_scores_cascade():
    s = StrategyEmber(
        {
            "params": {
                "veto_rsi_oversold": 0,
                "struct_lookback": 500,
                "veto_vol_slope_min": -100,
                "max_extension_atr": 10,
            }
        }
    )
    df = s.add_indicators(_bear_cascade_5m())
    row = s.score_scan_candidate(df, symbol="TEST")
    assert row is not None
    assert row["bias"] == "SHORT"
    assert row["score"] >= 65
    assert row["timeframe"] == "5m"
    assert row["armed"] is False


def test_ember_scan_armed_when_sticky():
    s = StrategyEmber(
        {
            "params": {
                "veto_rsi_oversold": 0,
                "struct_lookback": 500,
                "veto_vol_slope_min": -100,
                "max_extension_atr": 10,
            }
        }
    )
    df = s.add_indicators(_bear_cascade_5m())
    row = s.score_scan_candidate(df, symbol="TEST", meta={"sticky_armed": True})
    assert row is not None
    assert row["armed"] is True


def test_ember_arms_on_missing_1m_confirm():
    s = StrategyEmber({"params": dict(_HAPPY_PARAMS)})
    df_5m = _bear_cascade_5m()
    sig = s.generate_signal(pd.DataFrame(), extra_data={"5m": df_5m})
    assert sig is None
    assert s.looking_for_entry is True
    assert s.entry_direction == "SHORT"


def test_ember_rejects_extended_cascade():
    s = StrategyEmber({"params": {"max_extension_atr": 0.1, "cooldown_minutes": 0}})
    df_5m = _bear_cascade_5m()
    df_1m = _bear_1m_confirm()
    sig = s.generate_signal(pd.DataFrame(), extra_data={"5m": df_5m, "1m": df_1m})
    assert sig is None
    assert "extended" in (s.last_rejection_reason or "").lower()


def test_ember_accelerated_scan_interval_when_armed():
    s = StrategyEmber({"params": {"scan_interval_minutes": 3, "scan_interval_active_minutes": 1.5}})
    assert s.get_scan_interval_minutes() == 3.0
    assert s.get_scan_interval_minutes(scan_context={"sticky_armed": True}) == 1.5


def test_ember_thesis_dead_on_ema_reclaim():
    verdict = evaluate_waterfall_thesis(
        side="SELL",
        entry=10.0,
        current_price=10.5,
        close_15m=10.6,
        ema9=10.4,
        rsi=45.0,
        prev_open=10.3,
        prev_close=10.5,
        prev_high=10.7,
        cascade_high=10.8,
        rsi_exhaustion=26.0,
    )
    assert verdict.status == THESIS_DEAD


def test_ember_supports_trade_thesis():
    s = StrategyEmber({"params": {}})
    assert s.supports_trade_thesis() is True
    assert s.get_scan_timeframe() == "5m"
    assert s.get_thesis_timeframe() == "5m"
