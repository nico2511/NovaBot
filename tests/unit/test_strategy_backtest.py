"""Causal exit simulation and the per-strategy runner. No network."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app.core.causal_backtest import (
    bar_bracket_exit,
    funding_drag_r,
    gross_r,
    net_r,
    summarize_trades,
)
from app.core.hl_ohlcv import candles_to_frame, fetch_candles, slice_asof
from app.core.strategy_backtest import StrategySpec, replay_symbol

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "ohlcv" / "hl_candles.json"


class _Toy:
    """Buys once at the confirmed close. No thesis, no veto."""

    name = "toy"

    def __init__(self):
        self.calls = 0

    def get_param(self, key, default=None):
        return default

    def generate_signal(self, df, extra_data=None):
        self.calls += 1
        if self.calls != 1:
            return None
        if df is None or len(df) < 2:
            return None
        px = float(df["close"].iloc[-2])
        return {"signal": "BUY", "price": px, "sl": px - 1.0, "tp": px + 2.0}

    def supports_trade_thesis(self):
        return False


def _spec() -> StrategySpec:
    return StrategySpec(
        name="toy",
        primary="1h",
        step="1h",
        required=("1h",),
        regime_gate=False,
        bb_filter=False,
        mtf=False,
        thesis_tf="1h",
    )


def _hours(n: int, start: str = "2026-01-05T00:00:00Z") -> pd.DatetimeIndex:
    return pd.date_range(start, periods=n, freq="1h", tz="UTC")


def _flat(n: int, **kwargs) -> pd.DataFrame:
    idx = _hours(n, **kwargs) if "start" in kwargs else _hours(n)
    if "start" in kwargs:
        idx = _hours(n, kwargs["start"])
    df = pd.DataFrame(
        {
            "open": 100.0,
            "high": 100.4,
            "low": 99.6,
            "close": 100.0,
            "volume": 10.0,
        },
        index=idx,
    )
    return df


def test_bar_bracket_stop_wins_when_both_touched():
    price, reason = bar_bracket_exit("BUY", 100, 105, 99, sl=99.5, tp=104)
    assert price == 99.5
    assert reason == "sl_same_bar"


def test_bar_bracket_gap_through_stop_fills_at_open():
    price, reason = bar_bracket_exit("SELL", 110, 111, 108, sl=105, tp=90)
    assert reason == "sl_gap"
    assert price == 110


def test_bar_bracket_target_when_stop_is_safe():
    price, reason = bar_bracket_exit("BUY", 100, 106, 99.8, sl=99, tp=105)
    assert reason == "tp"
    assert price == 105


def test_funding_drag_long_pays_positive_rate():
    idx = pd.date_range("2026-01-01", periods=4, freq="1h", tz="UTC")
    funding = pd.DataFrame({"funding_rate": [0.0001, 0.0001, 0.0001, 0.0001]}, index=idx)
    drag, covered = funding_drag_r(
        "BUY",
        idx[0],
        idx[3],
        sl_frac=0.01,
        funding=funding,
    )
    assert covered
    # settlements strictly after entry and <= exit: three hours
    assert drag == pytest.approx(0.0003 / 0.01)
    short_drag, _ = funding_drag_r("SELL", idx[0], idx[3], 0.01, funding)
    assert short_drag == pytest.approx(-drag)


def test_candles_to_frame_sorts_and_coerces():
    raw = json.loads(FIXTURE.read_text())
    df = candles_to_frame(raw)
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]
    assert df.index.is_monotonic_increasing
    assert str(df.index.tz) == "UTC"
    assert float(df["close"].iloc[0]) == 100.0
    assert len(df) == 3


def test_fetch_candles_stops_when_the_next_page_is_empty():
    step = 60_000
    end = 5000 * step + 10_000
    calls = {"n": 0}

    def transport(payload):
        calls["n"] += 1
        req = payload["req"]
        if calls["n"] == 1:
            return [
                {"t": req["startTime"], "o": "1", "h": "2", "l": "0.5", "c": "1.5", "v": "3"},
                {"t": req["endTime"] - step, "o": "1", "h": "2", "l": "0.5", "c": "1.6", "v": "3"},
            ]
        return []

    df = fetch_candles(
        "BTC",
        "1m",
        start_ms=0,
        end_ms=end,
        page_pause=0,
        transport=transport,
    )
    assert calls["n"] == 2
    assert len(df) == 2
    assert df.index.tz is not None


def test_slice_asof_drops_future_bars():
    df = _flat(6)
    cut = slice_asof(df, df.index[3], n=10)
    assert cut.index[-1] == df.index[3]
    assert df.index[4] not in cut.index


def test_replay_target_ignores_the_signal_bar_wick():
    df = _flat(12)
    # Confirmed bar at the first decision (index 5 → iloc[-2] is index 4)
    # wicks through the future stop. That wick is before the fill.
    df.loc[df.index[4], ["open", "high", "low", "close"]] = (100, 101, 90, 100)
    # Bar that opens at the fill: no stop.
    df.loc[df.index[5], ["open", "high", "low", "close"]] = (100, 100.5, 99.5, 100.2)
    # Next bar runs the target.
    df.loc[df.index[6], ["open", "high", "low", "close"]] = (100.2, 103, 100, 102.5)
    trades, diag, _start, _end = replay_symbol(
        _Toy(),
        _spec(),
        "BTC",
        {"1h": df},
        {},
        warmup=5,
        verbose=False,
    )
    assert diag["signals"] == 1
    assert len(trades) == 1
    trade = trades[0]
    assert trade.exit_reason == "tp"
    assert trade.entry == pytest.approx(100.0)
    assert trade.exit == pytest.approx(102.0)
    assert trade.gross_r == pytest.approx(2.0)
    assert trade.net_r == pytest.approx(net_r(2.0, sl_frac=0.01))
    assert trade.net_r < trade.gross_r
    stats = summarize_trades(trades)
    assert stats.hit_rate == 1.0
    assert stats.n == 1


def test_weekend_pause_skips_entries():
    # Saturday 12:00 UTC is inside the default Sat 06:00 → Mon 06:00 Paris window.
    df = _flat(10, start="2026-01-03T12:00:00Z")
    config = {
        "weekend_pause": {
            "enabled": True,
            "timezone": "Europe/Paris",
            "start_weekday": 5,
            "start_hour": 6,
            "end_weekday": 0,
            "end_hour": 6,
            "strategies": ["toy"],
        }
    }
    trades, diag, _s, _e = replay_symbol(
        _Toy(),
        _spec(),
        "BTC",
        {"1h": df},
        config,
        warmup=3,
    )
    assert trades == []
    assert diag["weekend_skips"] > 0
    assert diag["signals"] == 0


def test_gross_r_short_stop():
    assert gross_r("SELL", 100, 101, 102) == pytest.approx(-0.5)
