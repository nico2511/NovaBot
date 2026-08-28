"""Unit tests for in-trade SuperTrend thesis evaluation."""
from __future__ import annotations

import pandas as pd
import pytest

from app.core.trade_thesis import (
    ACTION_CLOSE_IF_PROFIT,
    ACTION_HOLD,
    ACTION_TIGHTEN_SL,
    MIN_SOFT_CLOSE_PNL_PCT,
    NEAR_TP_LOCK_FRACTION,
    THESIS_DEAD,
    THESIS_VALID,
    THESIS_WEAK,
    ThesisVerdict,
    apply_near_tp_exhaustion,
    apply_dead_drift,
    break_even_sl,
    compute_thesis_dead_streak,
    count_stall_bars,
    dead_drift_sl,
    detect_near_tp_exhaustion,
    evaluate_range_lt_thesis,
    evaluate_supertrend_thesis,
    near_tp_exhaustion_sl,
    should_apply_be_tighten,
    thesis_indicators_ready,
    tp_progress_pct,
    volume_ratio_pct,
)


def test_long_valid_when_aligned():
    v = evaluate_supertrend_thesis(
        side="BUY",
        entry=100.0,
        current_price=101.0,
        close_15m=101.0,
        ema_filter=99.0,
        st_direction=1,
        supertrend=100.0,
        adx=30.0,
        adx_slope=0.2,
    )
    assert v.status == THESIS_VALID
    assert v.action == ACTION_HOLD
    assert v.pnl_pct > 0


def test_long_dead_on_st_flip_closes_if_green():
    v = evaluate_supertrend_thesis(
        side="BUY",
        entry=100.0,
        current_price=100.5,
        close_15m=99.0,
        ema_filter=98.0,
        st_direction=-1,
        supertrend=100.2,
        adx=28.0,
        adx_slope=0.0,
    )
    assert v.status == THESIS_DEAD
    assert v.action == ACTION_CLOSE_IF_PROFIT
    assert v.pnl_pct > 0


def test_long_dead_but_red_holds_for_sl():
    v = evaluate_supertrend_thesis(
        side="BUY",
        entry=100.0,
        current_price=99.0,
        close_15m=98.5,
        ema_filter=99.5,
        st_direction=-1,
        supertrend=99.0,
        adx=20.0,
        adx_slope=-1.5,
    )
    assert v.status == THESIS_DEAD
    # action is CLOSE_IF_PROFIT but caller must gate on pnl<=0
    assert v.action == ACTION_CLOSE_IF_PROFIT
    assert v.pnl_pct < 0


def test_long_weak_green_tightens():
    v = evaluate_supertrend_thesis(
        side="BUY",
        entry=100.0,
        current_price=101.2,
        close_15m=100.5,
        ema_filter=100.8,  # lost EMA but still above ST
        st_direction=1,
        supertrend=99.5,
        adx=25.0,
        adx_slope=-0.5,  # softening but above min_adx_slope=-1
    )
    assert v.status == THESIS_WEAK
    assert v.action == ACTION_TIGHTEN_SL


def test_entry_min_adx_slope_maps_to_weak_not_dead():
    """Strategy entry filter (-0.35) must be WEAK band, not DEAD floor."""
    v = evaluate_supertrend_thesis(
        side="BUY",
        entry=100.0,
        current_price=101.0,
        close_15m=101.0,
        ema_filter=99.0,
        st_direction=1,
        supertrend=100.0,
        adx=30.0,
        adx_slope=-0.5,
        min_adx_slope=-1.0,
        weak_adx_slope=-0.35,
    )
    assert v.status == THESIS_WEAK
    # Mis-wiring entry min_adx_slope=-0.35 as DEAD floor would wrongly kill this.
    v_miswired = evaluate_supertrend_thesis(
        side="BUY",
        entry=100.0,
        current_price=101.0,
        close_15m=101.0,
        ema_filter=99.0,
        st_direction=1,
        supertrend=100.0,
        adx=30.0,
        adx_slope=-0.5,
        min_adx_slope=-0.35,
        weak_adx_slope=-0.35,
    )
    assert v_miswired.status == THESIS_DEAD


def test_be_tighten_helpers():
    be = break_even_sl("BUY", 100.0)
    assert be == 100.2
    assert should_apply_be_tighten("BUY", 100.0, current_sl=99.0, be_sl=be) is True
    assert should_apply_be_tighten("BUY", 100.0, current_sl=100.3, be_sl=be) is False


def test_indicators_ready_rejects_nan():
    assert (
        thesis_indicators_ready(
            close_15m=100.0,
            ema_filter=99.0,
            st_direction=1,
            supertrend=98.0,
            adx=25.0,
        )
        is True
    )
    assert (
        thesis_indicators_ready(
            close_15m=float("nan"),
            ema_filter=99.0,
            st_direction=1,
            supertrend=98.0,
            adx=25.0,
        )
        is False
    )


def test_soft_close_min_pnl_constant():
    # Gate used by bot soft-close path — keep fee buffer explicit
    assert MIN_SOFT_CLOSE_PNL_PCT >= 0.2


def test_range_lt_short_dead_on_breakout_above_box():
    v = evaluate_range_lt_thesis(
        side="SELL",
        entry=3.31,
        current_price=3.30,
        close_1h=3.335,
        range_high=3.33,
        range_low=3.18,
        adx=14.0,
        adx_slope=0.1,
    )
    assert v.status == THESIS_DEAD
    assert v.action == ACTION_CLOSE_IF_PROFIT


def test_range_lt_short_valid_inside_box():
    v = evaluate_range_lt_thesis(
        side="SELL",
        entry=3.31,
        current_price=3.305,
        close_1h=3.29,
        range_high=3.33,
        range_low=3.18,
        adx=14.0,
        adx_slope=0.1,
    )
    assert v.status == THESIS_VALID
    assert v.action == ACTION_HOLD


def test_range_lt_long_dead_on_breakout_below_box():
    v = evaluate_range_lt_thesis(
        side="BUY",
        entry=3.19,
        current_price=3.18,
        close_1h=3.17,
        range_high=3.33,
        range_low=3.18,
        adx=12.0,
        adx_slope=-0.1,
    )
    assert v.status == THESIS_DEAD


def _stall_df(*, vol: float = 10.0, tight: bool = True) -> pd.DataFrame:
    """Synthetic OHLCV: last 3 closed bars tight-range + low volume vs history."""
    rows = []
    base_vol = 200.0
    for i in range(60):
        close = 100.0 + i * 0.01
        if tight and i >= 56:
            high, low = close + 0.0002, close - 0.0002
            v = vol
        else:
            high, low = close + 0.5, close - 0.5
            v = base_vol
        rows.append(
            {
                "open": close - 0.01,
                "high": high,
                "low": low,
                "close": close,
                "volume": v,
            }
        )
    return pd.DataFrame(rows)


def _valid_verdict(**kwargs) -> ThesisVerdict:
    defaults = dict(
        status=THESIS_VALID,
        action=ACTION_HOLD,
        reasons=("aligned",),
        adx=25.0,
        adx_slope=0.1,
        st_direction=1,
        close=107.5,
        supertrend=100.0,
        pnl_pct=7.5,
    )
    defaults.update(kwargs)
    return ThesisVerdict(**defaults)


def test_tp_progress_pct_long():
    assert tp_progress_pct("BUY", 100.0, 110.0, 107.0) == 70.0
    assert tp_progress_pct("BUY", 100.0, 110.0, 115.0) == 150.0


def test_volume_ratio_pct_low_on_stall_df():
    df = _stall_df(vol=10.0)
    ratio = volume_ratio_pct(df)
    assert ratio is not None
    assert ratio < 50.0


def test_count_stall_bars_on_tight_candles():
    df = _stall_df(tight=True)
    assert count_stall_bars(df, n=3) == 3


def test_near_tp_exhaustion_sl_locks_partial_move():
    sl = near_tp_exhaustion_sl("BUY", 100.0, 110.0, lock_fraction=NEAR_TP_LOCK_FRACTION)
    assert sl == 105.5


def test_detect_near_tp_exhaustion_triggers():
    df = _stall_df()
    ok, reasons = detect_near_tp_exhaustion(
        side="BUY",
        entry=100.0,
        tp=110.0,
        current_price=107.5,
        df=df,
        min_progress_pct=70.0,
        max_volume_ratio_pct=50.0,
    )
    assert ok is True
    assert reasons and "NEAR_TP_EXHAUSTION" in reasons[0]


def test_detect_near_tp_exhaustion_skips_far_from_tp():
    df = _stall_df()
    ok, _ = detect_near_tp_exhaustion(
        side="BUY",
        entry=100.0,
        tp=110.0,
        current_price=103.0,
        df=df,
    )
    assert ok is False


def test_apply_near_tp_exhaustion_upgrades_valid_to_weak():
    df = _stall_df()
    base = _valid_verdict()
    trade = {"side": "BUY", "entry": 100.0, "tp": 110.0}
    out = apply_near_tp_exhaustion(
        base,
        trade=trade,
        current_price=107.5,
        df=df,
    )
    assert out.status == THESIS_WEAK
    assert out.action == ACTION_TIGHTEN_SL
    assert out.tighten_sl == 105.5
    assert any("NEAR_TP_EXHAUSTION" in r for r in out.reasons)


def test_apply_near_tp_exhaustion_skips_dead():
    df = _stall_df()
    dead = _valid_verdict(status=THESIS_DEAD, action=ACTION_CLOSE_IF_PROFIT)
    trade = {"side": "BUY", "entry": 100.0, "tp": 110.0}
    out = apply_near_tp_exhaustion(
        dead,
        trade=trade,
        current_price=107.5,
        df=df,
    )
    assert out.status == THESIS_DEAD
    assert out.tighten_sl is None


def test_apply_near_tp_exhaustion_skips_red():
    df = _stall_df()
    base = _valid_verdict(pnl_pct=-0.5)
    trade = {"side": "BUY", "entry": 100.0, "tp": 110.0}
    out = apply_near_tp_exhaustion(
        base,
        trade=trade,
        current_price=99.5,
        df=df,
    )
    assert out.status == THESIS_VALID
    assert out.tighten_sl is None


def test_compute_thesis_dead_streak():
    assert compute_thesis_dead_streak(THESIS_VALID, THESIS_DEAD, 0) == 1
    assert compute_thesis_dead_streak(THESIS_DEAD, THESIS_DEAD, 1) == 2
    assert compute_thesis_dead_streak(THESIS_DEAD, THESIS_VALID, 3) == 0


def test_dead_drift_sl_moves_buy_sl_toward_entry():
    sl = dead_drift_sl(
        "BUY", 100.0, 98.0, drift_fraction=0.35, cap_loss_pct=2.0
    )
    assert sl == pytest.approx(98.7)


def test_dead_drift_sl_caps_max_loss():
    # Drift alone would land at 98.7; cap floor at -1.2% bumps SL to 98.8.
    sl = dead_drift_sl("BUY", 100.0, 98.0, drift_fraction=0.35, cap_loss_pct=1.2)
    assert sl == pytest.approx(98.8)


def test_apply_dead_drift_on_confirmed_dead_red():
    dead = _valid_verdict(
        status=THESIS_DEAD,
        action=ACTION_CLOSE_IF_PROFIT,
        pnl_pct=-0.8,
        reasons=("SuperTrend flipped",),
    )
    trade = {
        "side": "BUY",
        "entry": 100.0,
        "sl": 98.0,
        "thesis_status": THESIS_DEAD,
        "thesis_dead_streak": 1,
    }
    out = apply_dead_drift(dead, trade=trade, current_sl=98.0)
    assert out.action == ACTION_TIGHTEN_SL
    assert out.tighten_sl == pytest.approx(98.8)
    assert any("DEAD_DRIFT" in r for r in out.reasons)


def test_apply_dead_drift_waits_for_second_dead_check():
    dead = _valid_verdict(
        status=THESIS_DEAD,
        action=ACTION_CLOSE_IF_PROFIT,
        pnl_pct=-0.8,
        reasons=("SuperTrend flipped",),
    )
    trade = {
        "side": "BUY",
        "entry": 100.0,
        "sl": 98.0,
        "thesis_status": THESIS_VALID,
        "thesis_dead_streak": 0,
    }
    out = apply_dead_drift(dead, trade=trade, current_sl=98.0)
    assert out.action == ACTION_CLOSE_IF_PROFIT
    assert out.tighten_sl is None


def test_apply_dead_drift_skips_green_dead():
    dead = _valid_verdict(
        status=THESIS_DEAD,
        action=ACTION_CLOSE_IF_PROFIT,
        pnl_pct=0.5,
    )
    trade = {
        "side": "BUY",
        "entry": 100.0,
        "sl": 98.0,
        "thesis_status": THESIS_DEAD,
        "thesis_dead_streak": 3,
    }
    out = apply_dead_drift(dead, trade=trade, current_sl=98.0)
    assert out.action == ACTION_CLOSE_IF_PROFIT
    assert out.tighten_sl is None


def test_apply_dead_drift_skips_deep_loss():
    dead = _valid_verdict(
        status=THESIS_DEAD,
        action=ACTION_CLOSE_IF_PROFIT,
        pnl_pct=-3.0,
    )
    trade = {
        "side": "BUY",
        "entry": 100.0,
        "sl": 97.0,
        "thesis_status": THESIS_DEAD,
        "thesis_dead_streak": 3,
    }
    out = apply_dead_drift(dead, trade=trade, current_sl=97.0)
    assert out.tighten_sl is None
