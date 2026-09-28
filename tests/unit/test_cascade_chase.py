"""1m chase cap for rocket / waterfall fills past the confirmed 15m close."""
from __future__ import annotations

import pandas as pd

from strategies.cascade_rider import chase_atr_past_close
from strategies.rocket import StrategyRocket
from strategies.waterfall import StrategyWaterfall
from tests.unit.test_rocket import _HAPPY_PARAMS as ROCKET_HAPPY
from tests.unit.test_rocket import _bull_1m_confirm, _bull_cascade_15m
from tests.unit.test_waterfall import _HAPPY_PARAMS as WATERFALL_HAPPY
from tests.unit.test_waterfall import _bear_1m_confirm, _bear_cascade_15m

_CHASE = {"max_1m_chase_atr": 0.35}


def test_chase_atr_is_signed_in_the_trade_direction():
    assert chase_atr_past_close("BUY", 101.0, 100.0, 2.0) == 0.5
    assert chase_atr_past_close("LONG", 99.0, 100.0, 2.0) == -0.5
    assert chase_atr_past_close("SELL", 99.0, 100.0, 2.0) == 0.5
    assert chase_atr_past_close("SHORT", 101.0, 100.0, 2.0) == -0.5


def _confirmed_ref(strategy, df_15m):
    work = strategy.add_indicators(df_15m)
    return (
        work,
        float(work["close"].iloc[-2]),
        float(work["ATR_14"].iloc[-2]),
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


def test_rocket_rejects_chase_above_035_and_stays_armed():
    s = StrategyRocket({"params": {**ROCKET_HAPPY, **_CHASE}})
    df = _bull_cascade_15m()
    _, ref, atr = _confirmed_ref(s, df)
    sig = s.generate_signal(df, extra_data={"1m": _long_fill(ref, atr, chase_atr=1.0)})
    assert sig is None
    assert "chase" in (s.last_rejection_reason or "").lower()
    assert s.looking_for_entry is True


def test_rocket_accepts_fill_inside_chase_cap():
    s = StrategyRocket({"params": {**ROCKET_HAPPY, **_CHASE}})
    df = _bull_cascade_15m()
    _, ref, atr = _confirmed_ref(s, df)
    sig = s.generate_signal(df, extra_data={"1m": _long_fill(ref, atr, chase_atr=0.10)})
    assert sig is not None
    assert sig["price"] > ref


def test_rocket_pullback_is_not_a_chase_reject():
    s = StrategyRocket({"params": {**ROCKET_HAPPY, **_CHASE}})
    df = _bull_cascade_15m()
    _, ref, atr = _confirmed_ref(s, df)
    sig = s.generate_signal(df, extra_data={"1m": _long_fill(ref, atr, chase_atr=-0.15)})
    assert sig is not None
    assert sig["price"] < ref


def test_rocket_zero_cap_allows_chased_fill():
    s = StrategyRocket({"params": {**ROCKET_HAPPY, "max_1m_chase_atr": 0}})
    df = _bull_cascade_15m()
    _, ref, atr = _confirmed_ref(s, df)
    sig = s.generate_signal(df, extra_data={"1m": _long_fill(ref, atr, chase_atr=1.2)})
    assert sig is not None
    assert sig["signal"] == "BUY"


def test_rocket_code_default_is_035_when_param_omitted():
    s = StrategyRocket(
        {"params": {k: v for k, v in ROCKET_HAPPY.items() if k != "max_1m_chase_atr"}}
    )
    assert s._params_snapshot()["max_1m_chase_atr"] == 0.35


def test_waterfall_rejects_chase_and_accepts_inside_and_pullback():
    df = _bear_cascade_15m()
    probe = StrategyWaterfall({"params": {**WATERFALL_HAPPY, **_CHASE}})
    _, ref, atr = _confirmed_ref(probe, df)

    chased = StrategyWaterfall({"params": {**WATERFALL_HAPPY, **_CHASE}})
    assert chased.generate_signal(df, extra_data={"1m": _short_fill(ref, atr, chase_atr=1.0)}) is None
    assert "chase" in (chased.last_rejection_reason or "").lower()
    assert chased.looking_for_entry is True

    inside = StrategyWaterfall({"params": {**WATERFALL_HAPPY, **_CHASE}})
    sig = inside.generate_signal(df, extra_data={"1m": _short_fill(ref, atr, chase_atr=0.1)})
    assert sig is not None
    assert sig["signal"] == "SELL"

    pullback = StrategyWaterfall({"params": {**WATERFALL_HAPPY, **_CHASE}})
    sig_pb = pullback.generate_signal(
        df, extra_data={"1m": _short_fill(ref, atr, chase_atr=-0.1)}
    )
    assert sig_pb is not None
    assert sig_pb["price"] > ref
