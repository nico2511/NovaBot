"""Rocket strategy contract + signal / scan / thesis paths."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.core.trade_thesis import THESIS_DEAD, evaluate_rocket_thesis
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


def test_rocket_rejects_insufficient_data():
    s = StrategyRocket({"params": {}})
    assert s.generate_signal(pd.DataFrame()) is None
    assert s.last_rejection_reason


def test_detect_rocket_on_synthetic():
    df = _bull_cascade_15m()
    s = StrategyRocket({"params": {}})
    df = s.add_indicators(df)
    active, snap = detect_rocket(df, use_live=True)
    assert active is True
    assert snap.get("ema9", 0) > 0


def test_rocket_generate_signal_long():
    s = StrategyRocket({"params": {"cooldown_minutes": 0, "veto_rsi_overbought": 100}})
    df_15m = _bull_cascade_15m()
    df_1m = _bull_1m_confirm()
    sig = s.generate_signal(df_15m, extra_data={"1m": df_1m})
    assert sig is not None
    assert sig["signal"] == "BUY"
    assert sig["sl"] < sig["price"] < sig["tp"]
    assert sig.get("cascade_ema9") is not None


def test_rocket_scan_scores_cascade():
    s = StrategyRocket({"params": {"veto_rsi_overbought": 100}})
    df = s.add_indicators(_bull_cascade_15m())
    row = s.score_scan_candidate(df, symbol="TEST")
    assert row is not None
    assert row["bias"] == "LONG"
    assert row["score"] >= 65


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


def test_rocket_supports_trade_thesis():
    s = StrategyRocket({"params": {}})
    assert s.supports_trade_thesis() is True
    assert s.get_thesis_timeframe() == "15m"
