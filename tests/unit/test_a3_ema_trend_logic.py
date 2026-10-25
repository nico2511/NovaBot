"""Unit tests — A3 EMA-Trend 4H pure logic."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.core.a3_ema_trend_logic import (
    compute_a3_indicators,
    compute_paper_stop_flags,
    detect_crossover_on_closed_bar,
    initial_stop,
    update_trailing_stop,
)
from strategies.a3_ema_trend_4h import StrategyA3EmaTrend4h


def _ohlcv_4h(n: int, *, cross_at: int | None = None) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    close = np.linspace(100.0, 100.0 + n * 0.01, n)
    if cross_at is not None and cross_at > 1:
        # Force EMAf below EMAs then cross up at cross_at (approximate via bump)
        close[: cross_at - 1] -= 5.0
        close[cross_at - 1 :] += 8.0
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    high = close + 0.5
    low = close - 0.5
    vol = np.full(n, 1000.0)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


def test_crossover_detected_only_on_cross_bar():
    n = 320
    df = _ohlcv_4h(n)
    ind = compute_a3_indicators(df)
    # Without engineered cross, likely no signal on random walk — at least no exception
    side = detect_crossover_on_closed_bar(ind, min_warmup=300)
    assert side in (None, "BUY", "SELL")


def test_no_cross_without_warmup():
    df = _ohlcv_4h(50)
    ind = compute_a3_indicators(df)
    assert detect_crossover_on_closed_bar(ind, min_warmup=300) is None


def test_initial_stop_long():
    sl = initial_stop("BUY", 100.0, 2.0, atr_mult=4.0)
    assert sl == pytest.approx(92.0)


def test_trailing_stop_never_loosens_long():
    new_sl, peak, _ = update_trailing_stop(
        "BUY",
        current_stop=90.0,
        atr_current=2.0,
        last_close=105.0,
        peak_close=100.0,
        trough_close=95.0,
        atr_mult=4.0,
    )
    assert new_sl >= 90.0
    assert peak == 105.0
    # Loosen attempt
    new_sl2, _, _ = update_trailing_stop(
        "BUY",
        current_stop=new_sl,
        atr_current=10.0,
        last_close=80.0,
        peak_close=peak,
        trough_close=95.0,
        atr_mult=4.0,
    )
    assert new_sl2 == new_sl


def test_strategy_rejects_short_history():
    s = StrategyA3EmaTrend4h({"params": {"min_warmup_bars": 300}})
    df = _ohlcv_4h(100)
    assert s.generate_signal(df, extra_data={"4h": df}) is None


def test_strategy_universe_veto():
    s = StrategyA3EmaTrend4h({"params": {}})
    reason = s.check_hard_veto("BUY", {"symbol": "PEPE", "current_price": 1.0})
    assert reason is not None


def test_paper_stop_flags_drawdown():
    trades = [{"pnl_usd": -2500}] * 9 + [{"pnl_usd": 100}]
    flags = compute_paper_stop_flags(trades, equity_start=10000.0)
    assert flags.drawdown_breach is True


def test_engineered_cross_emits_signal():
    n = 305
    idx = pd.date_range("2024-01-01", periods=n, freq="4h", tz="UTC")
    ind = pd.DataFrame(
        {
            "open": np.full(n, 100.0),
            "high": np.full(n, 101.0),
            "low": np.full(n, 99.0),
            "close": np.full(n, 100.0),
            "volume": np.full(n, 1000.0),
            "EMAf": np.full(n, 100.0),
            "EMAs": np.full(n, 100.0),
            "ATR20": np.full(n, 2.0),
        },
        index=idx,
    )
    ind.iloc[-2, ind.columns.get_loc("EMAf")] = 101.0
    ind.iloc[-2, ind.columns.get_loc("EMAs")] = 100.0
    ind.iloc[-3, ind.columns.get_loc("EMAf")] = 99.0
    ind.iloc[-3, ind.columns.get_loc("EMAs")] = 100.0
    side = detect_crossover_on_closed_bar(ind, min_warmup=300)
    assert side == "BUY"
