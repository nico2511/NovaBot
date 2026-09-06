"""Spark strategy contract + signal / scan / thesis paths."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.trade_thesis import THESIS_DEAD, evaluate_rocket_thesis
from strategies.spark import StrategySpark, detect_spark


def _bull_cascade_5m(n=80, start=10.0):
    idx = pd.date_range("2024-06-01", periods=n, freq="5min")
    close = start + np.linspace(0, 2.5, n)
    close[-3:] = [close[-4], close[-4] + 0.15, close[-4] + 0.35]
    open_ = close - 0.08
    open_[-2:] = close[-2:] - 0.12
    open_[-1] = close[-1] - 0.10
    high = np.maximum(open_, close) + 0.02
    high[-1] = close[-1] + 0.03
    high[-2] = close[-2] + 0.02
    low = np.minimum(open_, close) - 0.02
    vol = np.full(n, 5000.0)
    vol[-1] = 12000.0
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


def _bull_1m_confirm(n=30, anchor=12.5):
    idx = pd.date_range("2024-06-01", periods=n, freq="1min")
    close = np.full(n, anchor)
    close[-2] = anchor + 0.04
    close[-1] = anchor + 0.05
    open_ = close - 0.03
    high = close + 0.01
    high[-2] = close[-2] + 0.02
    high[-3] = close[-3] + 0.01
    low = open_ - 0.01
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": np.full(n, 100.0)},
        index=idx,
    )


def test_spark_persona_and_criteria():
    s = StrategySpark({"params": {}})
    assert "SPARK" in s.get_ai_persona().upper()
    assert s.get_ai_validation_criteria()
    assert "BUY" in s.get_ai_validation_criteria()


def test_spark_hard_veto_blocks_sell():
    s = StrategySpark({"params": {}})
    assert s.check_hard_veto("SELL", {"volume_ratio": 100, "rsi": 60}) is not None


def test_spark_hard_veto_blocks_low_volume():
    s = StrategySpark({"params": {}})
    ctx = {"volume_ratio": 20, "rsi": 60, "regime": "TREND_BULL_STRONG"}
    assert s.check_hard_veto("BUY", ctx) is not None


def test_spark_hard_veto_blocks_dying_volume():
    s = StrategySpark({"params": {}})
    ctx = {"volume_ratio": 130, "rsi": 66, "vol_slope": -39.0}
    reason = s.check_hard_veto("BUY", ctx)
    assert reason is not None
    assert "dying" in reason.lower() or "fuel" in reason.lower()


def test_spark_hard_veto_allows_stable_volume():
    s = StrategySpark({"params": {}})
    ctx = {"volume_ratio": 130, "rsi": 66, "vol_slope": -10.0, "macd_hist": 0.01}
    assert s.check_hard_veto("BUY", ctx) is None


def test_spark_hard_veto_blocks_bearish_macd():
    s = StrategySpark({"params": {}})
    ctx = {"volume_ratio": 180, "rsi": 62, "vol_slope": 25.0, "macd_hist": -0.0033}
    reason = s.check_hard_veto("BUY", ctx)
    assert reason is not None
    assert "MACD" in reason


def test_spark_rejects_insufficient_data():
    s = StrategySpark({"params": {}})
    assert s.generate_signal(pd.DataFrame()) is None
    assert s.last_rejection_reason


def test_detect_spark_on_synthetic():
    df = _bull_cascade_5m()
    s = StrategySpark({"params": {}})
    df = s.add_indicators(df)
    active, snap = detect_spark(df, use_live=True)
    assert active is True
    assert snap.get("ema9", 0) > 0


_HAPPY_PARAMS = {
    "cooldown_minutes": 0,
    "veto_rsi_overbought": 100,
    "struct_lookback": 500,
    "veto_vol_slope_min": -100,
    "max_extension_atr": 10,
}


def test_spark_generate_signal_long():
    s = StrategySpark({"params": dict(_HAPPY_PARAMS)})
    df_5m = _bull_cascade_5m()
    df_1m = _bull_1m_confirm()
    sig = s.generate_signal(pd.DataFrame(), extra_data={"5m": df_5m, "1m": df_1m})
    assert sig is not None
    assert sig["signal"] == "BUY"
    assert sig["sl"] < sig["price"] < sig["tp"]
    assert sig.get("cascade_ema9") is not None


def test_spark_rejects_prior_resistance_without_spike():
    s = StrategySpark(
        {
            "params": {
                "cooldown_minutes": 0,
                "veto_rsi_overbought": 100,
                "veto_vol_slope_min": -100,
                "struct_lookback": 40,
                "struct_exclude_bars": 3,
                "ceiling_proximity_pct": 0.5,
                "breakout_clear_pct": 0.15,
                "volume_spike_pct": 120,
                "max_extension_atr": 10,
            }
        }
    )
    df_5m = _bull_cascade_5m()
    tip = float(df_5m["close"].iloc[-1])
    df_1m = _bull_1m_confirm(anchor=tip)
    entry = float(df_1m["close"].iloc[-2])
    df_5m.loc[df_5m.index[30:40], "high"] = entry
    sig = s.generate_signal(pd.DataFrame(), extra_data={"5m": df_5m, "1m": df_1m})
    assert sig is None
    assert s.last_rejection_reason
    low = s.last_rejection_reason.lower()
    assert "resistance" in low
    assert "breakout" in low or "absorption" in low


def test_spark_at_prior_ceiling_helper():
    s = StrategySpark({"params": {}})
    p = s._params_snapshot()
    assert s._at_prior_ceiling(12.0, 12.0, p) is True
    assert s._at_prior_ceiling(11.0, 12.0, p) is False
    clear_p = {**p, "breakout_clear_pct": 0.20}
    assert s._at_prior_ceiling(12.05, 12.0, clear_p) is False
    assert s._at_prior_ceiling(12.01, 12.0, clear_p) is True


def test_spark_rejects_dying_volume_on_signal():
    s = StrategySpark(
        {
            "params": {
                "cooldown_minutes": 0,
                "veto_rsi_overbought": 100,
                "struct_lookback": 500,
                "veto_vol_slope_min": -30,
                "max_extension_atr": 10,
            }
        }
    )
    df_5m = _bull_cascade_5m()
    df_5m.loc[df_5m.index[-3], "volume"] = 20000.0
    df_5m.loc[df_5m.index[-2], "volume"] = 8000.0
    df_1m = _bull_1m_confirm()
    sig = s.generate_signal(pd.DataFrame(), extra_data={"5m": df_5m, "1m": df_1m})
    assert sig is None
    assert "dying" in (s.last_rejection_reason or "").lower() or "soft" in (
        s.last_rejection_reason or ""
    ).lower()


def test_spark_scan_scores_cascade():
    s = StrategySpark(
        {
            "params": {
                "veto_rsi_overbought": 100,
                "struct_lookback": 500,
                "veto_vol_slope_min": -100,
                "max_extension_atr": 10,
            }
        }
    )
    df = s.add_indicators(_bull_cascade_5m())
    row = s.score_scan_candidate(df, symbol="TEST")
    assert row is not None
    assert row["bias"] == "LONG"
    assert row["score"] >= 65
    assert row["timeframe"] == "5m"
    assert row["armed"] is False


def test_spark_scan_armed_when_sticky():
    s = StrategySpark(
        {
            "params": {
                "veto_rsi_overbought": 100,
                "struct_lookback": 500,
                "veto_vol_slope_min": -100,
                "max_extension_atr": 10,
            }
        }
    )
    df = s.add_indicators(_bull_cascade_5m())
    row = s.score_scan_candidate(df, symbol="TEST", meta={"sticky_armed": True})
    assert row is not None
    assert row["armed"] is True


def test_spark_arms_on_missing_1m_confirm():
    s = StrategySpark({"params": dict(_HAPPY_PARAMS)})
    df_5m = _bull_cascade_5m()
    sig = s.generate_signal(pd.DataFrame(), extra_data={"5m": df_5m})
    assert sig is None
    assert s.looking_for_entry is True
    assert s.entry_direction == "LONG"


def test_spark_rejects_extended_cascade():
    s = StrategySpark({"params": {"max_extension_atr": 0.1, "cooldown_minutes": 0}})
    df_5m = _bull_cascade_5m()
    df_1m = _bull_1m_confirm()
    sig = s.generate_signal(pd.DataFrame(), extra_data={"5m": df_5m, "1m": df_1m})
    assert sig is None
    assert "extended" in (s.last_rejection_reason or "").lower()


def test_spark_accelerated_scan_interval_when_armed():
    s = StrategySpark({"params": {"scan_interval_minutes": 3, "scan_interval_active_minutes": 1.5}})
    assert s.get_scan_interval_minutes() == 3.0
    assert s.get_scan_interval_minutes(scan_context={"sticky_armed": True}) == 1.5


def test_spark_thesis_dead_on_ema_loss():
    verdict = evaluate_rocket_thesis(
        side="BUY",
        entry=10.0,
        current_price=9.5,
        close_15m=9.4,
        ema9=9.6,
        rsi=55.0,
        prev_open=9.7,
        prev_close=9.5,
        prev_low=9.3,
        cascade_low=9.2,
        rsi_exhaustion=74.0,
    )
    assert verdict.status == THESIS_DEAD


def test_spark_supports_trade_thesis():
    s = StrategySpark({"params": {}})
    assert s.supports_trade_thesis() is True
    assert s.get_scan_timeframe() == "5m"
    assert s.get_thesis_timeframe() == "5m"
