"""Causal replay harness — no live-bar fill, costs eat edge."""
from __future__ import annotations

from app.core.causal_backtest import net_r, round_trip_cost_frac, walk_closed_bars
from tests.unit.test_rocket import _HAPPY_PARAMS, _bull_1m_confirm, _bull_cascade_15m
from strategies.rocket import StrategyRocket


def test_round_trip_cost_is_two_takers_plus_slip():
    assert round_trip_cost_frac(taker=0.00045, slip=0.0001) == 0.0011


def test_net_r_on_1r_win_with_tight_sl():
    # 0.4% SL: 11 bps RT ≈ 0.275R, so a 1R winner is ~0.725R net.
    out = net_r(1.0, sl_frac=0.004, taker=0.00045, slip=0.0001)
    assert out == 1.0 - (0.0011 / 0.004)
    assert out < 0.8


def test_walk_closed_bars_fill_uses_confirmed_index():
    s = StrategyRocket({"params": dict(_HAPPY_PARAMS)})
    df = _bull_cascade_15m()

    def extra(window, _i):
        tip = float(window["close"].iloc[-2])
        return {"1m": _bull_1m_confirm(anchor=tip)}

    fills = walk_closed_bars(df, s, extra_data_fn=extra, warmup=len(df) - 3)
    assert fills, "synthetic rocket should fill on the last confirmed cascade"
    assert fills[-1].index == df.index[-2]


def test_live_bar_spike_does_not_create_a_new_fill():
    s = StrategyRocket({"params": dict(_HAPPY_PARAMS)})
    df = _bull_cascade_15m()

    def extra(window, _i):
        tip = float(window["close"].iloc[-2])
        return {"1m": _bull_1m_confirm(anchor=tip)}

    baseline = walk_closed_bars(df, s, extra_data_fn=extra, warmup=len(df) - 2)
    spiked = df.copy()
    spiked.loc[spiked.index[-1], ["open", "high", "low", "close"]] = (
        50.0,
        80.0,
        40.0,
        75.0,
    )
    s2 = StrategyRocket({"params": dict(_HAPPY_PARAMS)})
    warped = walk_closed_bars(spiked, s2, extra_data_fn=extra, warmup=len(df) - 2)
    assert [f.price for f in baseline] == [f.price for f in warped]
