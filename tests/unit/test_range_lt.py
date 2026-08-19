"""Range LT strategy contract + reject / scan paths."""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.range_lt import StrategyRangeLT


def _ohlcv_trend(n=250, start=100.0, drift=0.08):
    idx = pd.date_range("2024-01-01", periods=n, freq="1h")
    close = start + np.cumsum(np.full(n, drift))
    return pd.DataFrame(
        {
            "open": close - 0.1,
            "high": close + 0.5,
            "low": close - 0.5,
            "close": close,
            "volume": np.full(n, 1000.0),
        },
        index=idx,
    )


def _ohlcv_range(n=160, lo=100.0, hi=108.0, period=16):
    idx = pd.date_range("2024-01-01", periods=n, freq="1h")
    half = (hi - lo) / 2.0
    mid = (hi + lo) / 2.0
    phase = np.linspace(0, (n / period) * 2 * np.pi, n)
    close = mid + half * np.sin(phase)
    high = close + 0.25
    low = close - 0.25
    # Extra wicks at cycle extremes so Donchian touches register
    near_hi = close >= (hi - 0.35)
    near_lo = close <= (lo + 0.35)
    high = np.where(near_hi, hi + 0.05, high)
    low = np.where(near_lo, lo - 0.05, low)
    volume = np.full(n, 1200.0)
    return pd.DataFrame(
        {
            "open": close - 0.05,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        },
        index=idx,
    )


def _relaxed_params(**extra):
    p = {
        "lookback": 40,
        "min_touches": 1,
        "adx_max": 50,
        "max_adx_slope": 20,
        "ema_period": 20,
        "ema_slope_flat_max": 0.05,
        "min_range_pct": 1.0,
        "max_range_pct": 20.0,
        "min_volume_ratio_pct": 10,
        "min_rr": 1.2,
        "sl_atr_mult": 0.3,
        "sl_range_frac": 0.08,
        "min_sl_pct": 0.2,
        "htf_slope_max": 0.05,
        "cooldown_minutes": 0,
        "edge_frac": 0.35,
    }
    p.update(extra)
    return p


def test_range_lt_persona_and_criteria():
    s = StrategyRangeLT({"params": {}})
    persona = s.get_ai_persona().upper()
    assert "RANGE" in persona or "BOX" in persona or "FADE" in persona
    criteria = s.get_ai_validation_criteria()
    assert criteria
    assert "1h" in criteria.lower() or "BOX" in criteria.upper()


def test_range_lt_rejects_without_1h():
    s = StrategyRangeLT({"params": {}})
    assert s.generate_signal(pd.DataFrame()) is None
    assert s.last_rejection_reason
    assert "1h" in s.last_rejection_reason.lower()


def test_range_lt_rejects_short_history():
    s = StrategyRangeLT({"params": {"lookback": 48, "ema_period": 50}})
    df = _ohlcv_range(40)
    assert s.generate_signal(df, extra_data={"1h": df}) is None


def test_range_lt_hard_veto_adx_and_wrong_side_rsi():
    s = StrategyRangeLT({"params": {}})
    ctx = {"current_price": 100.0, "rsi": 50.0, "adx": 25.0, "volume_ratio": 80.0}
    assert s.check_hard_veto("BUY", ctx) is None
    assert s.check_hard_veto("BUY", {**ctx, "adx": 40.0}) is not None
    assert s.check_hard_veto("BUY", {**ctx, "rsi": 72.0}) is not None
    # Oversold BUY is the fade — must not copy SuperTrend oversold veto
    assert s.check_hard_veto("BUY", {**ctx, "rsi": 28.0}) is None
    assert s.check_hard_veto("BUY", {**ctx, "volume_ratio": 10.0}) is not None


def test_range_lt_veto_report_shows_pass_and_block():
    s = StrategyRangeLT({"params": {}})
    ctx = {"current_price": 100.0, "rsi": 50.0, "adx": 40.0, "volume_ratio": 80.0}
    reason = s.check_hard_veto("BUY", ctx)
    assert reason is not None
    names = [row["name"] for row in s.last_veto_report]
    assert names == ["ADX", "RSI", "VOL"]
    by_name = {row["name"]: row for row in s.last_veto_report}
    assert by_name["ADX"]["blocked"] is True
    assert by_name["RSI"]["blocked"] is False
    assert by_name["VOL"]["blocked"] is False
    report = s.format_veto_report()
    assert "ADX BLOCK" in report
    assert "RSI PASS" in report
    assert "VOL PASS" in report


def test_range_lt_veto_report_all_pass():
    s = StrategyRangeLT({"params": {}})
    ctx = {"current_price": 100.0, "rsi": 28.0, "adx": 16.0, "volume_ratio": 90.0}
    assert s.check_hard_veto("BUY", ctx) is None
    report = s.format_veto_report()
    assert "ADX PASS" in report
    assert "RSI PASS" in report
    assert "VOL PASS" in report
    assert "BLOCK" not in report


def test_range_lt_veto_report_can_be_silenced():
    s = StrategyRangeLT({"params": {"log_veto_report": False}})
    ctx = {"current_price": 100.0, "rsi": 50.0, "adx": 40.0, "volume_ratio": 80.0}
    assert s.check_hard_veto("BUY", ctx) is not None
    assert s.format_veto_report() is None


def test_bot_logs_range_lt_veto_pass_and_block():
    from app.core.bot import BotContext

    bot = BotContext.__new__(BotContext)
    logs = []
    bot.add_log = lambda msg, metadata=None: logs.append(msg)
    s = StrategyRangeLT({"params": {}})
    ctx = {"current_price": 100.0, "rsi": 28.0, "adx": 16.0, "volume_ratio": 90.0}
    assert s.check_hard_veto("BUY", ctx) is None
    bot._log_hard_veto_outcome("BUY", "ATOM", "range_lt", strategy=s, veto_reason=None)
    assert logs and logs[0].startswith("🛡️ VETO PASS")
    assert "ADX PASS" in logs[0] and "RSI PASS" in logs[0]

    logs.clear()
    reason = s.check_hard_veto("BUY", {**ctx, "adx": 40.0})
    bot._log_hard_veto_outcome("BUY", "ATOM", "range_lt", strategy=s, veto_reason=reason)
    assert logs and logs[0].startswith("⛔ HARD VETO")
    assert "ADX BLOCK" in logs[0] and "RSI PASS" in logs[0]


def test_range_lt_post_ai_adjust_caps_buy_tp_at_box():
    s = StrategyRangeLT({"params": {}})
    signal = {
        "signal": "BUY",
        "price": 100.0,
        "tp": 112.0,
        "sl": 98.0,
        "range_high": 105.0,
        "range_low": 99.0,
    }
    ai = {"approved": True, "reasoning": "x", "suggested_adjustments": {}}
    out = s.post_ai_adjust(signal, ai, {})
    assert out["suggested_adjustments"]["tp"] < 105.0
    assert out["suggested_adjustments"]["tp"] > 100.0


def test_range_lt_scan_hooks_and_score_path():
    s = StrategyRangeLT({"params": _relaxed_params(scan_interval_minutes=60)})
    s.name = "range_lt"
    assert s.get_scan_timeframe() == "1h"
    assert s.get_scan_interval_minutes() == 60.0
    out = s.score_scan_candidate(
        _ohlcv_range(), symbol="ATOM", meta={"volume_24h": 3e6}
    )
    assert out is not None
    assert out["bias"] in ("LONG", "SHORT")
    assert out["timeframe"] == "1h"
    assert out["score"] > 0
    assert out["trend"] == "RANGE"


def test_range_lt_scan_rejects_uptrend():
    s = StrategyRangeLT(
        {"params": _relaxed_params(adx_max=12, ema_slope_flat_max=0.00001, min_touches=2)}
    )
    assert s.score_scan_candidate(_ohlcv_trend(), symbol="TREND") is None


def test_range_lt_rejects_short_on_h1_high_piercing_box_top():
    """Wick above hourly box top with close inside is breakout, not a fade."""
    df = _ohlcv_range(n=140)
    range_low = float(df["low"].iloc[-(72 + 3) : -2].min())
    range_high = float(df["high"].iloc[-(72 + 3) : -2].max())
    last_conf = df.index[-2]
    df.loc[last_conf, "high"] = range_high + 0.15
    df.loc[last_conf, "open"] = range_high - 0.05
    df.loc[last_conf, "close"] = range_high - 0.12
    df.loc[last_conf, "low"] = df.loc[last_conf, "close"] - 0.08
    df.loc[last_conf, "volume"] = 2000.0

    s = StrategyRangeLT({"params": _relaxed_params(lookback=40, structure_lookback=72)})
    sig = s.generate_signal(df, extra_data={"1h": df})
    assert sig is None
    assert s.last_rejection_reason
    reason = s.last_rejection_reason.lower()
    assert "pierced" in reason or "ceiling" in reason or "hourly" in reason


def test_range_lt_can_fade_synthetic_range_low():
    """Craft a ranging series ending with a low-tag + close-back-inside bar."""
    df = _ohlcv_range(n=140)
    # Prior box from the sine; overwrite the last confirmed bar as a rejection
    # at the low and keep a forming bar after it.
    range_low = float(df["low"].iloc[-(48 + 3) : -2].min())
    range_high = float(df["high"].iloc[-(48 + 3) : -2].max())
    mid = (range_low + range_high) / 2.0
    last_conf = df.index[-2]
    df.loc[last_conf, "low"] = range_low + 0.02
    df.loc[last_conf, "open"] = range_low + 0.15
    df.loc[last_conf, "close"] = range_low + max(0.35, (mid - range_low) * 0.2)
    df.loc[last_conf, "high"] = df.loc[last_conf, "close"] + 0.05
    df.loc[last_conf, "volume"] = 2000.0

    s = StrategyRangeLT({"params": _relaxed_params(lookback=40)})
    sig = s.generate_signal(df, extra_data={"1h": df})
    assert sig is not None, s.last_rejection_reason
    assert sig["signal"] == "BUY"
    assert sig["sl"] < sig["price"] < sig["tp"]
    assert sig["range_low"] < sig["price"] < sig["range_high"]


def test_range_lt_registered_always_active_on_engine():
    from strategies.engine import StrategyEngine

    engine = StrategyEngine()
    assert "range_lt" in engine.strategies
    cfg = engine.config.get("range_lt") or {}
    assert cfg.get("timeframe") == "1h"
    assert cfg.get("type") == "always_active"
