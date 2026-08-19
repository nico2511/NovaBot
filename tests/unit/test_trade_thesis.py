"""Unit tests for in-trade SuperTrend thesis evaluation."""
from __future__ import annotations

from app.core.trade_thesis import (
    ACTION_CLOSE_IF_PROFIT,
    ACTION_HOLD,
    ACTION_TIGHTEN_SL,
    MIN_SOFT_CLOSE_PNL_PCT,
    THESIS_DEAD,
    THESIS_VALID,
    THESIS_WEAK,
    break_even_sl,
    evaluate_range_lt_thesis,
    evaluate_supertrend_thesis,
    should_apply_be_tighten,
    thesis_indicators_ready,
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
