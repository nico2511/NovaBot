"""Impulse pullback: persona, veto, arm / fill / invalidate, scan, thesis."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.trade_thesis import ACTION_CLOSE, THESIS_DEAD
from strategies.impulse_pullback import (
    ACTION_ARM,
    ACTION_FILL,
    ACTION_INVALID,
    StrategyImpulsePullback,
    evaluate_impulse_window,
)

ROOT = Path(__file__).resolve().parents[2]


def _flat_1m(n=80, price=100.0, spread=0.40, start="2026-03-02"):
    idx = pd.date_range(start, periods=n, freq="1min", tz="UTC")
    close = np.full(n, price)
    open_ = np.full(n, price - 0.05)
    high = np.full(n, price + spread / 2.0)
    low = np.full(n, price - spread / 2.0)
    vol = np.full(n, 1000.0)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


def _with_break(df: pd.DataFrame, *, close: float, open_: float, high: float, low: float, at: int = -2):
    out = df.copy()
    out.iloc[at, out.columns.get_loc("open")] = open_
    out.iloc[at, out.columns.get_loc("high")] = high
    out.iloc[at, out.columns.get_loc("low")] = low
    out.iloc[at, out.columns.get_loc("close")] = close
    return out


def _strategy(**params) -> StrategyImpulsePullback:
    base = {
        "swing_lookback": 20,
        "pullback_max_bars": 15,
        "min_break_atr": 0.02,
        "max_chase_atr": 0.35,
        "pullback_touch_atr": 0.20,
        "min_rr": 1.5,
        "min_volume_ratio_pct": 50,
        "veto_rsi_long": 78,
        "veto_rsi_short": 22,
    }
    base.update(params)
    return StrategyImpulsePullback({"timeframe": "5m", "params": base})


def _wide_15m(price=100.0, n=20):
    """Range wide enough that `price` is the top quintile for a long."""
    idx = pd.date_range("2026-03-01", periods=n, freq="15min", tz="UTC")
    close = np.linspace(90.0, price, n)
    high = close + 0.2
    low = close - 0.4
    low[0] = 90.0
    high[-1] = price + 0.1
    return pd.DataFrame(
        {
            "open": close - 0.05,
            "high": high,
            "low": low,
            "close": close,
            "volume": np.full(n, 5000.0),
        },
        index=idx,
    )


def test_persona_and_criteria():
    strat = _strategy()
    persona = strat.get_ai_persona().upper()
    criteria = strat.get_ai_validation_criteria() or ""
    assert "IMPULSE PULLBACK" in persona
    assert "BUY" in criteria and "SELL" in criteria
    assert "0.35" in criteria or "0,35" in criteria or "ATR" in criteria


def test_hard_veto_blocks_extreme_rsi_and_thin_volume():
    strat = _strategy()
    assert strat.check_hard_veto("BUY", {"rsi": 90, "volume_ratio": 80}) is not None
    assert strat.check_hard_veto("SELL", {"rsi": 10, "volume_ratio": 80}) is not None
    assert strat.check_hard_veto("BUY", {"rsi": 55, "volume_ratio": 80}) is None
    assert strat.check_hard_veto("SELL", {"rsi": 45, "volume_ratio": 80}) is None
    assert strat.check_hard_veto("BUY", {"rsi": 55, "volume_ratio": 10}) is not None
    assert strat.check_hard_veto("BUY", {"rsi": 55}) is None


def test_generate_signal_rejects_missing_data():
    strat = _strategy()
    assert strat.generate_signal(None) is None
    assert strat.generate_signal(pd.DataFrame()) is None


def test_arm_then_fill_long_pullback():
    strat = _strategy()
    base = _flat_1m()
    armed = _with_break(base, open_=100.10, high=100.32, low=100.05, close=100.30)
    assert strat.generate_signal(armed, extra_data={"1m": armed}) is None
    assert strat.looking_for_entry is True
    assert strat.entry_direction == "LONG"

    filled = armed.copy()
    # Shift the break back one bar and put the pullback on the new closed bar.
    filled.iloc[-3, filled.columns.get_loc("open")] = 100.10
    filled.iloc[-3, filled.columns.get_loc("high")] = 100.32
    filled.iloc[-3, filled.columns.get_loc("low")] = 100.05
    filled.iloc[-3, filled.columns.get_loc("close")] = 100.30
    filled.iloc[-2, filled.columns.get_loc("open")] = 100.28
    filled.iloc[-2, filled.columns.get_loc("high")] = 100.30
    filled.iloc[-2, filled.columns.get_loc("low")] = 100.22
    filled.iloc[-2, filled.columns.get_loc("close")] = 100.26
    sig = strat.generate_signal(filled, extra_data={"1m": filled})
    assert sig is not None, strat.last_rejection_reason
    assert sig["signal"] == "BUY"
    assert sig["sl"] < sig["price"] < sig["tp"]
    assert sig["sl"] < sig["cascade_low"] <= sig["price"]
    assert strat.looking_for_entry is False


def test_arm_then_fill_short_pullback():
    strat = _strategy()
    base = _flat_1m()
    # Flat highs are 100.2 and lows 99.8. A short break must close under 99.8.
    armed = _with_break(base, open_=99.95, high=100.00, low=99.65, close=99.70)
    assert strat.generate_signal(armed, extra_data={"1m": armed}) is None
    assert strat.entry_direction == "SHORT"
    filled = armed.copy()
    filled.iloc[-3, filled.columns.get_loc("open")] = 99.95
    filled.iloc[-3, filled.columns.get_loc("high")] = 100.00
    filled.iloc[-3, filled.columns.get_loc("low")] = 99.65
    filled.iloc[-3, filled.columns.get_loc("close")] = 99.70
    filled.iloc[-2, filled.columns.get_loc("open")] = 99.72
    filled.iloc[-2, filled.columns.get_loc("high")] = 99.78
    filled.iloc[-2, filled.columns.get_loc("low")] = 99.68
    filled.iloc[-2, filled.columns.get_loc("close")] = 99.74
    sig = strat.generate_signal(filled, extra_data={"1m": filled})
    assert sig is not None, strat.last_rejection_reason
    assert sig["signal"] == "SELL"
    assert sig["tp"] < sig["price"] < sig["sl"]
    assert sig["price"] <= sig["cascade_high"] < sig["sl"]


def test_chase_extension_does_not_arm():
    strat = _strategy()
    base = _flat_1m()
    chased = _with_break(base, open_=100.25, high=101.00, low=100.20, close=100.90)
    snap = evaluate_impulse_window(chased, params=strat._params_snapshot())
    assert snap["action"] == ACTION_INVALID
    assert "chase" in str(snap["reason"]).lower()
    assert strat.generate_signal(chased, extra_data={"1m": chased}) is None
    assert strat.looking_for_entry is False


def test_last_quintile_blocks_the_arm():
    strat = _strategy()
    base = _flat_1m()
    armed = _with_break(base, open_=100.10, high=100.32, low=100.05, close=100.30)
    htf = _wide_15m(price=100.4)
    snap = evaluate_impulse_window(
        armed, params=strat._params_snapshot(), df_15m=htf, df_5m=htf
    )
    assert snap["action"] == ACTION_INVALID
    assert strat.generate_signal(armed, extra_data={"1m": armed, "15m": htf, "5m": htf}) is None
    assert strat.looking_for_entry is False


def test_missed_pullback_does_not_fill_later():
    strat = _strategy()
    base = _flat_1m(n=90)
    df = base.copy()
    # Break on iloc[-4], valid pullback on iloc[-3], extension on the closed bar.
    df.iloc[-4, df.columns.get_loc("open")] = 100.10
    df.iloc[-4, df.columns.get_loc("high")] = 100.32
    df.iloc[-4, df.columns.get_loc("low")] = 100.05
    df.iloc[-4, df.columns.get_loc("close")] = 100.30
    df.iloc[-3, df.columns.get_loc("open")] = 100.28
    df.iloc[-3, df.columns.get_loc("high")] = 100.30
    df.iloc[-3, df.columns.get_loc("low")] = 100.22
    df.iloc[-3, df.columns.get_loc("close")] = 100.26
    df.iloc[-2, df.columns.get_loc("open")] = 100.30
    df.iloc[-2, df.columns.get_loc("high")] = 100.40
    df.iloc[-2, df.columns.get_loc("low")] = 100.28
    df.iloc[-2, df.columns.get_loc("close")] = 100.36
    strat.looking_for_entry = True
    strat.entry_direction = "LONG"
    snap = evaluate_impulse_window(df, params=strat._params_snapshot(), armed_side="LONG")
    assert snap["action"] != ACTION_FILL
    assert strat.generate_signal(df, extra_data={"1m": df}) is None


def test_scan_scores_break_and_skips_flat():
    strat = _strategy()
    flat = _flat_1m(n=60)
    flat.index = pd.date_range("2026-03-02", periods=len(flat), freq="5min", tz="UTC")
    assert strat.score_scan_candidate(flat, symbol="BTC") is None

    n = 70
    idx = pd.date_range("2026-03-02", periods=n, freq="5min", tz="UTC")
    t = np.arange(n)
    close = 100 + 0.03 * np.sin(t)
    open_ = 100 + 0.03 * np.sin(t + 1.2)
    high = np.maximum(open_, close) + 0.05
    low = np.minimum(open_, close) - 0.05
    # Older spike sits in the 15m window but outside the 20-bar swing, so the
    # local break is not the last quintile of that wider move.
    high[-23] = 102.0
    low[-23] = 99.5
    broke = pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": np.full(n, 1000.0)},
        index=idx,
    )
    broke.iloc[-2, broke.columns.get_loc("open")] = 100.09
    broke.iloc[-2, broke.columns.get_loc("close")] = 100.103
    broke.iloc[-2, broke.columns.get_loc("high")] = 100.12
    broke.iloc[-2, broke.columns.get_loc("low")] = 100.05
    scored = strat.score_scan_candidate(broke, symbol="BTC", meta={"sticky_armed": True})
    assert scored is not None
    assert scored["bias"] == "LONG"
    assert scored["score"] >= 80
    assert scored["armed"] is True


def test_thesis_dead_when_pullback_low_breaks():
    strat = _strategy()
    idx = pd.date_range("2026-04-01", periods=30, freq="15min", tz="UTC")
    close = np.full(30, 100.0)
    close[-2] = 99.0
    df = pd.DataFrame(
        {
            "open": close,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.full(30, 1000.0),
        },
        index=idx,
    )
    trade = {
        "side": "BUY",
        "entry": 100.2,
        "metadata": {"cascade_low": 99.5},
    }
    verdict = strat.evaluate_trade_thesis(trade, 99.0, df=df)
    assert verdict is not None
    assert verdict.status == THESIS_DEAD
    assert verdict.action == ACTION_CLOSE


def test_registered_off_in_engine_and_both_json_files():
    from strategies.engine import StrategyEngine

    from app.core.strategy_backtest import SPECS

    assert "impulse_pullback" in SPECS
    assert SPECS["impulse_pullback"].step == "1m"
    assert SPECS["impulse_pullback"].regime_gate is False
    engine = StrategyEngine()
    assert "impulse_pullback" in engine.strategies
    strat = engine.strategies["impulse_pullback"]
    assert strat.get_scan_timeframe() == "5m"
    assert strat.supports_trade_thesis() is True
    paths = (
        ROOT / "data" / "config" / "strategies.json",
        ROOT / "app" / "core" / "defaults" / "strategies.default.json",
    )
    for path in paths:
        cfg = json.loads(path.read_text())
        row = cfg["impulse_pullback"]
        assert row["enabled"] is False
        assert row["active"] is False
        assert row["type"] == "always_active"
        assert float(row["params"]["max_chase_atr"]) == 0.35
        assert float(row["params"]["min_rr"]) == 1.5
        assert cfg["rocket"]["enabled"] is True
        assert cfg["waterfall"]["enabled"] is True
        assert "impulse_pullback" in cfg["weekend_pause"]["strategies"]


def test_window_labels_a_clean_arm():
    base = _flat_1m()
    armed = _with_break(base, open_=100.10, high=100.32, low=100.05, close=100.30)
    snap = evaluate_impulse_window(armed, params=_strategy()._params_snapshot())
    assert snap["action"] == ACTION_ARM
    assert snap["side"] == "LONG"
