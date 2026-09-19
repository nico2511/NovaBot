"""Unit tests for evaluate_rocket_thesis."""
from app.core.trade_thesis import (
    ACTION_HOLD,
    ACTION_TIGHTEN_SL,
    THESIS_VALID,
    THESIS_WEAK,
    evaluate_rocket_thesis,
)


def test_rocket_thesis_valid_while_cascade_active():
    v = evaluate_rocket_thesis(
        side="BUY",
        entry=10.0,
        current_price=10.8,
        close_15m=10.7,
        ema9=10.2,
        rsi=68,
        prev_open=10.65,
        prev_close=10.72,
        prev_low=10.6,
    )
    assert v.status == THESIS_VALID


def test_rocket_thesis_holds_inside_entry_rsi_band():
    """RSI 79 is allowed at entry (veto 82) — must not BE-lock mid-band."""
    v = evaluate_rocket_thesis(
        side="BUY",
        entry=10.0,
        current_price=10.5,
        close_15m=10.4,
        ema9=10.1,
        rsi=79,
        prev_open=10.2,
        prev_close=10.35,
        prev_low=10.15,
    )
    assert v.status == THESIS_VALID


def test_rocket_thesis_weak_on_exhausted_rsi():
    v = evaluate_rocket_thesis(
        side="BUY",
        entry=10.0,
        current_price=11.0,
        close_15m=10.9,
        ema9=10.3,
        rsi=85,
        prev_open=10.85,
        prev_close=10.95,
        prev_low=10.8,
        rsi_exhaustion=80.0,
    )
    assert v.status == THESIS_WEAK
    assert v.action == ACTION_TIGHTEN_SL


def test_rocket_thesis_avax_like_no_instant_be_lock():
    """RSI 72 right after entry (+0.02%) must not TIGHTEN_SL (AVAX 2026-09-19)."""
    v = evaluate_rocket_thesis(
        side="BUY",
        entry=8.8537,
        current_price=8.8555,
        close_15m=8.855,
        ema9=8.84,
        rsi=72.1,
        prev_open=8.84,
        prev_close=8.85,
        prev_low=8.82,
        rsi_exhaustion=80.0,
        weak_tighten_min_pnl_pct=0.35,
    )
    assert v.status == THESIS_VALID
    assert v.action == ACTION_HOLD


def test_rocket_rsi_weak_holds_sl_until_min_pnl():
    v = evaluate_rocket_thesis(
        side="BUY",
        entry=10.0,
        current_price=10.02,
        close_15m=10.01,
        ema9=9.95,
        rsi=82.5,
        prev_open=10.0,
        prev_close=10.01,
        prev_low=9.98,
        rsi_exhaustion=80.0,
        weak_tighten_min_pnl_pct=0.35,
    )
    assert v.status == THESIS_WEAK
    assert v.action == ACTION_HOLD
