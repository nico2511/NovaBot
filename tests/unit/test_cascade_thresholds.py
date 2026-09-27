"""Chase cap, with-trend 1m, and early-break lane for rocket and waterfall.

Live defaults keep the cap off and the early-break lane off. These tests pin
the new knobs without changing the baseline happy path.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from strategies.cascade_rider import chase_atr_past_close, confirm_1m_trigger
from strategies.rocket import StrategyRocket
from strategies.waterfall import StrategyWaterfall
from tests.unit.test_rocket import _HAPPY_PARAMS as ROCKET_HAPPY
from tests.unit.test_rocket import _bull_1m_confirm, _bull_cascade_15m
from tests.unit.test_waterfall import _HAPPY_PARAMS as WATERFALL_HAPPY
from tests.unit.test_waterfall import _bear_1m_confirm, _bear_cascade_15m


def test_chase_atr_is_signed_in_the_trade_direction():
    assert chase_atr_past_close("BUY", 101.0, 100.0, 2.0) == 0.5
    assert chase_atr_past_close("LONG", 99.0, 100.0, 2.0) == -0.5
    assert chase_atr_past_close("SELL", 99.0, 100.0, 2.0) == 0.5
    assert chase_atr_past_close("SHORT", 101.0, 100.0, 2.0) == -0.5


def test_confirm_1m_with_trend_does_not_require_a_new_extreme():
    df = _bull_1m_confirm()
    df.loc[df.index[-3], "high"] = float(df["close"].iloc[-2]) + 1.0
    ok_hh, _ = confirm_1m_trigger(df, "LONG", require_new_extreme=True)
    ok_trend, price = confirm_1m_trigger(df, "LONG", require_new_extreme=False)
    assert ok_hh is False
    assert ok_trend is True
    assert price == float(df["close"].iloc[-2])

    bear = _bear_1m_confirm()
    bear.loc[bear.index[-3], "low"] = float(bear["close"].iloc[-2]) - 1.0
    ok_ll, _ = confirm_1m_trigger(bear, "SHORT", require_new_extreme=True)
    ok_red, price_s = confirm_1m_trigger(bear, "SHORT", require_new_extreme=False)
    assert ok_ll is False
    assert ok_red is True
    assert price_s == float(bear["close"].iloc[-2])


def _confirmed_ref(strategy, df_15m):
    work = strategy.add_indicators(df_15m)
    return (
        work,
        float(work["close"].iloc[-2]),
        float(work["ATR_14"].iloc[-2]),
        float(work["EMA_9"].iloc[-2]),
    )


def _long_fill(ref: float, atr: float, *, chase_atr: float) -> pd.DataFrame:
    df = _bull_1m_confirm(anchor=ref)
    entry = ref + chase_atr * atr
    df.loc[df.index[-3], "high"] = min(ref, entry) - abs(atr) * 0.05
    df.loc[df.index[-2], "open"] = entry - abs(atr) * 0.1
    df.loc[df.index[-2], "close"] = entry
    df.loc[df.index[-2], "high"] = entry + abs(atr) * 0.01
    df.loc[df.index[-2], "low"] = entry - abs(atr) * 0.12
    return df


def _short_fill(ref: float, atr: float, *, chase_atr: float) -> pd.DataFrame:
    df = _bear_1m_confirm(anchor=ref)
    entry = ref - chase_atr * atr
    df.loc[df.index[-3], "low"] = max(ref, entry) + abs(atr) * 0.05
    df.loc[df.index[-2], "open"] = entry + abs(atr) * 0.1
    df.loc[df.index[-2], "close"] = entry
    df.loc[df.index[-2], "low"] = entry - abs(atr) * 0.01
    df.loc[df.index[-2], "high"] = entry + abs(atr) * 0.12
    return df


def test_rocket_baseline_allows_a_chased_fill():
    s = StrategyRocket({"params": dict(ROCKET_HAPPY)})
    df = _bull_cascade_15m()
    _, ref, atr, _ = _confirmed_ref(s, df)
    sig = s.generate_signal(df, extra_data={"1m": _long_fill(ref, atr, chase_atr=1.2)})
    assert sig is not None
    assert sig["signal"] == "BUY"
    assert sig["entry_lane"] == "cascade"


def test_rocket_rejects_chase_above_035_and_stays_armed():
    s = StrategyRocket({"params": {**ROCKET_HAPPY, "max_1m_chase_atr": 0.35}})
    df = _bull_cascade_15m()
    _, ref, atr, _ = _confirmed_ref(s, df)
    sig = s.generate_signal(df, extra_data={"1m": _long_fill(ref, atr, chase_atr=1.0)})
    assert sig is None
    assert "chase" in (s.last_rejection_reason or "").lower()
    assert s.looking_for_entry is True


def test_rocket_accepts_fill_inside_chase_cap():
    s = StrategyRocket({"params": {**ROCKET_HAPPY, "max_1m_chase_atr": 0.35}})
    df = _bull_cascade_15m()
    _, ref, atr, _ = _confirmed_ref(s, df)
    sig = s.generate_signal(df, extra_data={"1m": _long_fill(ref, atr, chase_atr=0.10)})
    assert sig is not None
    assert sig["price"] > ref


def test_rocket_pullback_is_not_a_chase_reject():
    s = StrategyRocket({"params": {**ROCKET_HAPPY, "max_1m_chase_atr": 0.35}})
    df = _bull_cascade_15m()
    _, ref, atr, _ = _confirmed_ref(s, df)
    sig = s.generate_signal(df, extra_data={"1m": _long_fill(ref, atr, chase_atr=-0.15)})
    assert sig is not None
    assert sig["price"] < ref


def test_rocket_rejects_upper_bb_extreme_at_fill():
    s = StrategyRocket(
        {
            "params": {
                **ROCKET_HAPPY,
                "reject_bb_extreme_at_fill": True,
                "max_1m_chase_atr": 0,
            }
        }
    )
    df = _bull_cascade_15m()
    _, ref, atr, _ = _confirmed_ref(s, df)
    sig = s.generate_signal(df, extra_data={"1m": _long_fill(ref, atr, chase_atr=8.0)})
    assert sig is None
    assert "upper bb" in (s.last_rejection_reason or "").lower()


def test_rocket_rejects_fill_extension_when_enabled():
    s_probe = StrategyRocket({"params": dict(ROCKET_HAPPY)})
    df = _bull_cascade_15m()
    _, ref, atr, ema = _confirmed_ref(s_probe, df)
    ext_15 = (ref - ema) / atr
    cap = ext_15 + 0.4
    s = StrategyRocket(
        {
            "params": {
                **ROCKET_HAPPY,
                "max_extension_atr": cap,
                "reject_fill_extension": True,
                "max_1m_chase_atr": 0,
            }
        }
    )
    sig = s.generate_signal(df, extra_data={"1m": _long_fill(ref, atr, chase_atr=1.0)})
    assert sig is None
    assert "extended" in (s.last_rejection_reason or "").lower()


def test_rocket_with_trend_1m_fills_without_higher_high():
    df = _bull_cascade_15m()
    probe = StrategyRocket({"params": dict(ROCKET_HAPPY)})
    _, ref, atr, _ = _confirmed_ref(probe, df)
    one = _long_fill(ref, atr, chase_atr=0.05)
    one.loc[one.index[-3], "high"] = float(one["close"].iloc[-2]) + atr

    blocked = StrategyRocket({"params": dict(ROCKET_HAPPY)})
    assert blocked.generate_signal(df, extra_data={"1m": one}) is None
    assert "higher high" in (blocked.last_rejection_reason or "").lower()

    opened = StrategyRocket({"params": {**ROCKET_HAPPY, "require_1m_new_extreme": False}})
    sig = opened.generate_signal(df, extra_data={"1m": one})
    assert sig is not None
    assert sig["signal"] == "BUY"


def test_waterfall_rejects_chase_and_lower_bb_and_accepts_pullback():
    df = _bear_cascade_15m()
    probe = StrategyWaterfall({"params": dict(WATERFALL_HAPPY)})
    _, ref, atr, _ = _confirmed_ref(probe, df)

    chased = StrategyWaterfall({"params": {**WATERFALL_HAPPY, "max_1m_chase_atr": 0.35}})
    assert chased.generate_signal(df, extra_data={"1m": _short_fill(ref, atr, chase_atr=1.0)}) is None
    assert "chase" in (chased.last_rejection_reason or "").lower()
    assert chased.looking_for_entry is True

    inside = StrategyWaterfall({"params": {**WATERFALL_HAPPY, "max_1m_chase_atr": 0.35}})
    sig = inside.generate_signal(df, extra_data={"1m": _short_fill(ref, atr, chase_atr=0.1)})
    assert sig is not None
    assert sig["signal"] == "SELL"
    assert sig["entry_lane"] == "cascade"

    pullback = StrategyWaterfall({"params": {**WATERFALL_HAPPY, "max_1m_chase_atr": 0.35}})
    sig_pb = pullback.generate_signal(df, extra_data={"1m": _short_fill(ref, atr, chase_atr=-0.1)})
    assert sig_pb is not None
    assert sig_pb["price"] > ref

    extreme = StrategyWaterfall(
        {
            "params": {
                **WATERFALL_HAPPY,
                "reject_bb_extreme_at_fill": True,
                "max_1m_chase_atr": 0,
            }
        }
    )
    assert extreme.generate_signal(df, extra_data={"1m": _short_fill(ref, atr, chase_atr=8.0)}) is None
    assert "lower bb" in (extreme.last_rejection_reason or "").lower()


def test_waterfall_with_trend_1m_fills_without_lower_low():
    df = _bear_cascade_15m()
    probe = StrategyWaterfall({"params": dict(WATERFALL_HAPPY)})
    _, ref, atr, _ = _confirmed_ref(probe, df)
    one = _short_fill(ref, atr, chase_atr=0.05)
    one.loc[one.index[-3], "low"] = float(one["close"].iloc[-2]) - atr

    blocked = StrategyWaterfall({"params": dict(WATERFALL_HAPPY)})
    assert blocked.generate_signal(df, extra_data={"1m": one}) is None
    assert "lower low" in (blocked.last_rejection_reason or "").lower()

    opened = StrategyWaterfall({"params": {**WATERFALL_HAPPY, "require_1m_new_extreme": False}})
    sig = opened.generate_signal(df, extra_data={"1m": one})
    assert sig is not None
    assert sig["signal"] == "SELL"


def _early_long_frame(n=80) -> pd.DataFrame:
    idx = pd.date_range("2024-06-01", periods=n, freq="15min")
    close = np.full(n, 10.0)
    open_ = close - 0.01
    high = np.full(n, 10.04)
    low = np.full(n, 9.98)
    # Previous bar is red, so the cascade (double green + HH) stays off.
    open_[-3] = 10.03
    close[-3] = 10.00
    high[-3] = 10.04
    low[-3] = 9.99
    open_[-2] = 10.08
    close[-2] = 10.40
    high[-2] = 10.42
    low[-2] = 10.06
    open_[-1] = 10.38
    close[-1] = 10.39
    high[-1] = 10.41
    low[-1] = 10.36
    vol = np.full(n, 5000.0)
    vol[-2] = 16000.0
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


def _early_short_frame(n=80) -> pd.DataFrame:
    idx = pd.date_range("2024-06-01", periods=n, freq="15min")
    close = np.full(n, 10.0)
    open_ = close + 0.01
    high = np.full(n, 10.02)
    low = np.full(n, 9.96)
    # Previous bar is green, so the cascade (double red + LL) stays off.
    open_[-3] = 9.98
    close[-3] = 10.01
    high[-3] = 10.02
    low[-3] = 9.97
    open_[-2] = 9.92
    close[-2] = 9.60
    high[-2] = 9.94
    low[-2] = 9.58
    open_[-1] = 9.62
    close[-1] = 9.61
    high[-1] = 9.64
    low[-1] = 9.59
    vol = np.full(n, 5000.0)
    vol[-2] = 16000.0
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": vol},
        index=idx,
    )


def _green_1m(price: float) -> pd.DataFrame:
    idx = pd.date_range("2024-06-02", periods=30, freq="1min")
    close = np.full(30, price)
    open_ = close - 0.02
    high = close + 0.01
    low = open_ - 0.01
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": np.full(30, 100.0)},
        index=idx,
    )


def _red_1m(price: float) -> pd.DataFrame:
    idx = pd.date_range("2024-06-02", periods=30, freq="1min")
    close = np.full(30, price)
    open_ = close + 0.02
    high = open_ + 0.01
    low = close - 0.01
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": np.full(30, 100.0)},
        index=idx,
    )


_EARLY_PARAMS = {
    "cooldown_minutes": 0,
    "veto_rsi_overbought": 100,
    "veto_rsi_oversold": 0,
    "struct_lookback": 500,
    "veto_vol_slope_min": -100,
    "max_extension_atr": 30,
    "early_break_enabled": True,
    "early_break_lookback": 16,
}


def test_rocket_early_break_lane_fires_only_when_enabled():
    df = _early_long_frame()
    off = StrategyRocket({"params": {**_EARLY_PARAMS, "early_break_enabled": False}})
    assert off.generate_signal(df, extra_data={"1m": _green_1m(10.40)}) is None
    assert "cascade" in (off.last_rejection_reason or "").lower()

    on = StrategyRocket({"params": dict(_EARLY_PARAMS)})
    sig = on.generate_signal(df, extra_data={"1m": _green_1m(10.40)})
    assert sig is not None
    assert sig["signal"] == "BUY"
    assert sig["entry_lane"] == "early_break"
    assert "early-break" in sig["comment"]


def test_rocket_early_break_still_rejects_extension():
    df = _early_long_frame()
    s = StrategyRocket({"params": {**_EARLY_PARAMS, "max_extension_atr": 0.5}})
    sig = s.generate_signal(df, extra_data={"1m": _green_1m(10.40)})
    assert sig is None
    assert "extended" in (s.last_rejection_reason or "").lower()
    assert s.looking_for_entry is False


def test_waterfall_early_break_lane_mirrors_rocket():
    df = _early_short_frame()
    off = StrategyWaterfall({"params": {**_EARLY_PARAMS, "early_break_enabled": False}})
    assert off.generate_signal(df, extra_data={"1m": _red_1m(9.60)}) is None

    on = StrategyWaterfall({"params": dict(_EARLY_PARAMS)})
    sig = on.generate_signal(df, extra_data={"1m": _red_1m(9.60)})
    assert sig is not None
    assert sig["signal"] == "SELL"
    assert sig["entry_lane"] == "early_break"
    assert "early-break" in sig["comment"]

    tight = StrategyWaterfall({"params": {**_EARLY_PARAMS, "max_extension_atr": 0.5}})
    assert tight.generate_signal(df, extra_data={"1m": _red_1m(9.60)}) is None
    assert "extended" in (tight.last_rejection_reason or "").lower()
