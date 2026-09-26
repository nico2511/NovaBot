"""Rocket strategy contract + signal / scan / thesis paths."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.trade_thesis import ACTION_CLOSE, THESIS_DEAD, evaluate_rocket_thesis
from strategies.rocket import StrategyRocket, detect_rocket


def _bull_cascade_15m(n=80, start=10.0):
    idx = pd.date_range("2024-06-01", periods=n, freq="15min")
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
    vol[-2] = 12000.0
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


def test_rocket_persona_and_criteria():
    s = StrategyRocket({"params": {}})
    assert "ROCKET" in s.get_ai_persona().upper()
    assert s.get_ai_validation_criteria()
    assert "BUY" in s.get_ai_validation_criteria()


def test_rocket_hard_veto_blocks_sell():
    s = StrategyRocket({"params": {}})
    assert s.check_hard_veto("SELL", {"volume_ratio": 100, "rsi": 60}) is not None


def test_rocket_hard_veto_blocks_low_volume():
    s = StrategyRocket({"params": {}})
    ctx = {"volume_ratio": 20, "rsi": 60, "regime": "TREND_BULL_STRONG"}
    assert s.check_hard_veto("BUY", ctx) is not None


def test_rocket_hard_veto_allows_missing_volume_ratio():
    s = StrategyRocket({"params": {}})
    ctx = {"rsi": 60, "macd_hist": 0.01, "vol_slope": -10.0}
    assert s.check_hard_veto("BUY", ctx) is None


def test_rocket_hard_veto_blocks_dying_volume():
    s = StrategyRocket({"params": {}})
    ctx = {"volume_ratio": 130, "rsi": 66, "vol_slope": -39.0}
    reason = s.check_hard_veto("BUY", ctx)
    assert reason is not None
    assert "dying" in reason.lower() or "fuel" in reason.lower()


def test_rocket_hard_veto_allows_stable_volume():
    s = StrategyRocket({"params": {}})
    ctx = {"volume_ratio": 130, "rsi": 66, "vol_slope": -10.0, "macd_hist": 0.01}
    assert s.check_hard_veto("BUY", ctx) is None


def test_rocket_hard_veto_blocks_bearish_macd():
    s = StrategyRocket({"params": {}})
    ctx = {"volume_ratio": 180, "rsi": 62, "vol_slope": 25.0, "macd_hist": -0.0042}
    reason = s.check_hard_veto("BUY", ctx)
    assert reason is not None
    assert "MACD" in reason


def test_rocket_rejects_insufficient_data():
    s = StrategyRocket({"params": {}})
    assert s.generate_signal(pd.DataFrame()) is None
    assert s.last_rejection_reason


def test_detect_rocket_on_synthetic():
    df = _bull_cascade_15m()
    s = StrategyRocket({"params": {}})
    df = s.add_indicators(df)
    live_active, live_snap = detect_rocket(df, use_live=True)
    confirmed_active, confirmed_snap = detect_rocket(df, use_live=False)
    assert live_active is True
    assert confirmed_active is True
    assert confirmed_snap.get("ema9", 0) > 0


_HAPPY_PARAMS = {
    "cooldown_minutes": 0,
    "veto_rsi_overbought": 100,
    # Rising synthetic series sits on its own highs — disable structure gate for happy path
    "struct_lookback": 500,
    "veto_vol_slope_min": -100,
    "max_extension_atr": 10,
}


def test_rocket_generate_signal_long():
    s = StrategyRocket({"params": dict(_HAPPY_PARAMS)})
    df_15m = _bull_cascade_15m()
    df_1m = _bull_1m_confirm()
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is not None
    assert sig["signal"] == "BUY"
    assert sig["sl"] < sig["price"] < sig["tp"]
    assert sig.get("cascade_ema9") is not None


def test_rocket_rejects_prior_resistance_without_spike():
    """Revisit of an earlier swing high without volume spike (double-top)."""
    s = StrategyRocket(
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
    df_15m = _bull_cascade_15m()
    # Confirmed close, not the forming bar — 1m must stay inside the chase cap.
    tip = float(df_15m["close"].iloc[-2])
    df_1m = _bull_1m_confirm(anchor=tip)
    entry = float(df_1m["close"].iloc[-2])
    # Prior swing high exactly at the 1m entry — classic double-top
    df_15m.loc[df_15m.index[30:40], "high"] = entry
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is None
    assert s.last_rejection_reason
    low = s.last_rejection_reason.lower()
    assert "resistance" in low
    assert "breakout" in low or "absorption" in low


def test_rocket_at_prior_ceiling_helper():
    s = StrategyRocket({"params": {}})
    p = s._params_snapshot()
    assert s._at_prior_ceiling(12.0, 12.0, p) is True
    assert s._at_prior_ceiling(11.0, 12.0, p) is False
    # Clear breakout above prior high (15m close, not wick)
    clear_p = {**p, "breakout_clear_pct": 0.20}
    assert s._at_prior_ceiling(12.05, 12.0, clear_p) is False
    assert s._at_prior_ceiling(12.01, 12.0, clear_p) is True


def test_rocket_rejects_dying_volume_on_signal():
    s = StrategyRocket(
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
    df_15m = _bull_cascade_15m()
    df_15m.loc[df_15m.index[-3], "volume"] = 20000.0
    df_15m.loc[df_15m.index[-2], "volume"] = 8000.0  # −60% slope
    df_1m = _bull_1m_confirm()
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is None
    assert "dying" in (s.last_rejection_reason or "").lower() or "soft" in (
        s.last_rejection_reason or ""
    ).lower()


def test_rocket_scan_scores_cascade():
    s = StrategyRocket({"params": {"veto_rsi_overbought": 100, "struct_lookback": 500, "veto_vol_slope_min": -100, "max_extension_atr": 10}})
    df = s.add_indicators(_bull_cascade_15m())
    row = s.score_scan_candidate(df, symbol="TEST")
    assert row is not None
    assert row["bias"] == "LONG"
    assert row["score"] >= 65
    assert row["armed"] is False


def test_rocket_scan_armed_when_sticky():
    s = StrategyRocket({"params": {"veto_rsi_overbought": 100, "struct_lookback": 500, "veto_vol_slope_min": -100, "max_extension_atr": 10}})
    df = s.add_indicators(_bull_cascade_15m())
    row = s.score_scan_candidate(df, symbol="TEST", meta={"sticky_armed": True})
    assert row is not None
    assert row["armed"] is True


def test_rocket_arms_on_missing_1m_confirm():
    s = StrategyRocket({"params": dict(_HAPPY_PARAMS)})
    df_15m = _bull_cascade_15m()
    bad_1m = _bull_1m_confirm()
    bad_1m.loc[bad_1m.index[-2], "close"] = bad_1m["open"].iloc[-2] - 0.01
    sig = s.generate_signal(df_15m, extra_data={"1m": bad_1m})
    assert sig is None
    assert s.looking_for_entry is True
    assert s.entry_direction == "LONG"


def test_rocket_does_not_arm_on_dead_volume():
    s = StrategyRocket({"params": dict(_HAPPY_PARAMS)})
    df_15m = _bull_cascade_15m()
    df_15m["volume"] = 100.0
    df_1m = _bull_1m_confirm()
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is None
    assert s.looking_for_entry is False
    assert "Volume" in (s.last_rejection_reason or "")


def test_rocket_rejects_extended_cascade():
    s = StrategyRocket({"params": {**_HAPPY_PARAMS, "max_extension_atr": 0.5}})
    df_15m = _bull_cascade_15m()
    df_15m = s.add_indicators(df_15m)
    atr = float(df_15m["ATR_14"].iloc[-2])
    ema9 = float(df_15m["EMA_9"].iloc[-2])
    prev_high = float(df_15m["high"].iloc[-3])
    stretched = max(prev_high + 0.05, ema9 + 2.0 * atr)
    df_15m.loc[df_15m.index[-2], "close"] = stretched
    df_15m.loc[df_15m.index[-2], "open"] = ema9 + 1.5 * atr
    df_15m.loc[df_15m.index[-2], "high"] = stretched + 0.01
    df_1m = _bull_1m_confirm()
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is None
    assert s.looking_for_entry is False
    assert "extended" in (s.last_rejection_reason or "").lower()


def test_rocket_enters_without_1m_higher_high():
    """With-trend 1m is enough. Waiting for a new high was the late fill."""
    s = StrategyRocket({"params": dict(_HAPPY_PARAMS)})
    df_15m = _bull_cascade_15m()
    df_1m = _bull_1m_confirm()
    prev_high = float(df_1m["high"].iloc[-3])
    df_1m.loc[df_1m.index[-2], "high"] = prev_high - 0.01
    df_1m.loc[df_1m.index[-2], "close"] = prev_high - 0.02
    df_1m.loc[df_1m.index[-2], "open"] = prev_high - 0.06
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is not None, s.last_rejection_reason
    assert sig["signal"] == "BUY"


def test_rocket_rejects_1m_chase_past_confirmed_close():
    s = StrategyRocket({"params": {**_HAPPY_PARAMS, "max_1m_chase_atr": 0.35}})
    df_15m = _bull_cascade_15m()
    work = s.add_indicators(df_15m)
    confirmed = float(df_15m["close"].iloc[-2])
    atr = float(work["ATR_14"].iloc[-2])
    df_1m = _bull_1m_confirm()
    chased = confirmed + 2.0 * atr
    df_1m.loc[df_1m.index[-2], "open"] = chased - 0.05
    df_1m.loc[df_1m.index[-2], "close"] = chased
    df_1m.loc[df_1m.index[-2], "high"] = chased + 0.02
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is None
    assert s.looking_for_entry is False
    assert "late" in (s.last_rejection_reason or "").lower()


def test_rocket_accelerated_scan_interval_when_armed():
    s = StrategyRocket({"params": {}})
    assert s.get_scan_interval_minutes(scan_context={"sticky_armed": True}) == 1.0
    assert s.get_scan_interval_minutes(scan_context={"sticky_armed": False}) == 2.0


def test_rocket_thesis_dead_on_ema_loss():
    verdict = evaluate_rocket_thesis(
        side="BUY",
        entry=10.0,
        current_price=10.5,
        close_15m=9.8,
        ema9=10.0,
        rsi=55,
        prev_open=10.1,
        prev_close=10.0,
        prev_low=9.9,
    )
    assert verdict.status == THESIS_DEAD
    assert verdict.action == ACTION_CLOSE


def test_rocket_supports_trade_thesis():
    s = StrategyRocket({"params": {}})
    assert s.supports_trade_thesis() is True
    assert s.get_thesis_timeframe() == "15m"
