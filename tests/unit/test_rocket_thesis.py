"""Unit tests for evaluate_rocket_thesis."""
from app.core.trade_thesis import THESIS_VALID, THESIS_WEAK, evaluate_rocket_thesis


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
    )
    assert v.status == THESIS_WEAK
