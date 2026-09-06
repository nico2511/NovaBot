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
    ctx = {"volume_ratio": 130, "rsi": 35, "vol_slope": -39.0, "macd_hist": -0.01}
    reason = s.check_hard_veto("SELL", ctx)
    assert reason is not None
    assert "dying" in reason.lower() or "fuel" in reason.lower()


def test_waterfall_hard_veto_blocks_bullish_macd():
    s = StrategyWaterfall({"params": {}})
    ctx = {"volume_ratio": 180, "rsi": 38, "vol_slope": 25.0, "macd_hist": 0.0042}
    reason = s.check_hard_veto("SELL", ctx)
    assert reason is not None
    assert "MACD" in reason


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
    "max_extension_atr": 10,
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
                    "veto_vol_slope_min": -30,
                    "struct_lookback": 500,
                    "max_extension_atr": 10,
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
    """Revisit of an earlier swing low without a close-through (double-bottom fade)."""
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
                    "max_extension_atr": 10,
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
    assert "support" in low
    assert "breakdown" in low or "absorption" in low


def test_waterfall_rejects_support_even_with_volume_spike():
    """ADA-like: 1m pierces a prior shelf, 15m still on it, huge volume = absorption."""
    s = StrategyWaterfall(
        {
            "params": {
                **_HAPPY_PARAMS,
                "struct_lookback": 40,
                "struct_exclude_bars": 3,
                "floor_proximity_pct": 0.35,
                "breakdown_clear_pct": 0.60,
                "volume_spike_pct": 120,
            }
        }
    )
    df_15m = _bear_cascade_15m()
    tip = float(df_15m["close"].iloc[-1])
    df_1m = _bear_1m_confirm(anchor=tip)
    entry = float(df_1m["close"].iloc[-2])
    shelf = entry * 1.0031
    df_15m.loc[df_15m.index[30:40], "low"] = shelf
    df_15m.loc[df_15m.index[-2], "volume"] = 50000.0
    df_15m.loc[df_15m.index[-1], "volume"] = 50000.0
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is None
    low = (s.last_rejection_reason or "").lower()
    assert "support" in low
    assert "spike" not in low


def test_waterfall_scan_scores_cascade():
    s = StrategyWaterfall(
        {"params": {"veto_rsi_oversold": 0, "struct_lookback": 500, "veto_vol_slope_min": -100, "max_extension_atr": 10}}
    )
    df = s.add_indicators(_bear_cascade_15m())
    row = s.score_scan_candidate(df, symbol="TEST")
    assert row is not None
    assert row["bias"] == "SHORT"
    assert row["score"] >= 65
    assert row["armed"] is False


def test_waterfall_scan_armed_when_sticky():
    s = StrategyWaterfall(
        {"params": {"veto_rsi_oversold": 0, "struct_lookback": 500, "veto_vol_slope_min": -100, "max_extension_atr": 10}}
    )
    df = s.add_indicators(_bear_cascade_15m())
    row = s.score_scan_candidate(df, symbol="TEST", meta={"sticky_armed": True})
    assert row is not None
    assert row["armed"] is True


def test_waterfall_arms_on_missing_1m_confirm():
    s = StrategyWaterfall({"params": dict(_HAPPY_PARAMS)})
    df_15m = _bear_cascade_15m()
    bad_1m = _bear_1m_confirm()
    bad_1m.loc[bad_1m.index[-2], "close"] = bad_1m["open"].iloc[-2] + 0.01
    sig = s.generate_signal(df_15m, extra_data={"1m": bad_1m})
    assert sig is None
    assert s.looking_for_entry is True
    assert s.entry_direction == "SHORT"


def test_waterfall_rejects_extended_cascade():
    s = StrategyWaterfall({"params": {**_HAPPY_PARAMS, "max_extension_atr": 0.5}})
    df_15m = _bear_cascade_15m()
    df_15m = s.add_indicators(df_15m)
    atr = float(df_15m["ATR_14"].iloc[-1])
    ema9 = float(df_15m["EMA_9"].iloc[-1])
    prev_low = float(df_15m["low"].iloc[-2])
    df_15m.loc[df_15m.index[-1], "close"] = min(prev_low - 0.05, ema9 - 2.0 * atr)
    df_15m.loc[df_15m.index[-1], "open"] = ema9 - 1.5 * atr
    df_15m.loc[df_15m.index[-1], "low"] = float(df_15m["close"].iloc[-1]) - 0.01
    df_1m = _bear_1m_confirm()
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is None
    assert s.looking_for_entry is False
    assert "extended" in (s.last_rejection_reason or "").lower()


def test_waterfall_accelerated_scan_interval_when_armed():
    s = StrategyWaterfall({"params": {}})
    assert s.get_scan_interval_minutes(scan_context={"sticky_armed": True}) == 2.0
    assert s.get_scan_interval_minutes(scan_context={"sticky_armed": False}) == 5.0


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
