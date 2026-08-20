"""Unit tests for evaluate_waterfall_thesis."""
from app.core.trade_thesis import THESIS_VALID, THESIS_WEAK, evaluate_waterfall_thesis


def test_waterfall_thesis_valid_while_cascade_active():
    v = evaluate_waterfall_thesis(
        side="SELL",
        entry=10.0,
        current_price=9.2,
        close_15m=9.3,
        ema9=9.8,
        rsi=32,
        prev_open=9.35,
        prev_close=9.28,
        prev_high=9.4,
    )
    assert v.status == THESIS_VALID


def test_waterfall_thesis_holds_inside_entry_rsi_band():
    """RSI 20 is allowed at entry (veto 18) — must not BE-lock mid-band."""
    v = evaluate_waterfall_thesis(
        side="SELL",
        entry=10.0,
        current_price=9.4,
        close_15m=9.5,
        ema9=9.9,
        rsi=20,
        prev_open=9.55,
        prev_close=9.45,
        prev_high=9.6,
    )
    assert v.status == THESIS_VALID


def test_waterfall_thesis_weak_on_exhausted_rsi():
    v = evaluate_waterfall_thesis(
        side="SELL",
        entry=10.0,
        current_price=9.0,
        close_15m=9.1,
        ema9=9.5,
        rsi=15,
        prev_open=9.15,
        prev_close=9.05,
        prev_high=9.2,
    )
    assert v.status == THESIS_WEAK
