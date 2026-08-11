"""
Unit tests for app.core.trailing_logic.compute_trailing_decision.

The trailing-stop ladder (Smart BE → 20% lock → 40% lock) is a
non-trivial, state-dependent rule set; these tests pin every branch.
"""
from __future__ import annotations

import pytest

from app.core.trailing_logic import compute_trailing_decision


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _long_trade(entry=100.0, sl=95.0, tp=110.0):
    return {"symbol": "BTC", "side": "BUY", "entry": entry, "sl": sl, "tp": tp}


def _short_trade(entry=100.0, sl=105.0, tp=90.0):
    return {"symbol": "BTC", "side": "SELL", "entry": entry, "sl": sl, "tp": tp}


# ----------------------------------------------------------------------
# Guards — when the function must return None
# ----------------------------------------------------------------------

def test_returns_none_when_missing_fields():
    assert compute_trailing_decision({}, 100.0) is None
    assert compute_trailing_decision({"side": "BUY", "entry": 100}, 100.0) is None


def test_returns_none_for_unknown_side():
    trade = {"side": "HODL", "entry": 100.0, "sl": 95.0, "tp": 110.0}
    assert compute_trailing_decision(trade, 105.0) is None


def test_returns_none_when_tp_equals_entry():
    """Degenerate case: total distance is zero → no division, no decision."""
    trade = _long_trade(tp=100.0)
    assert compute_trailing_decision(trade, 100.5) is None


def test_returns_none_when_price_missing_or_zero():
    """Stale quote (0) must not look like a huge SHORT win toward TP."""
    assert compute_trailing_decision(_short_trade(), 0.0) is None
    assert compute_trailing_decision(_long_trade(), 0.0) is None
    assert compute_trailing_decision(_short_trade(), -1.0) is None


def test_returns_none_before_be_threshold():
    """Progress below 75% AND PnL below 2.0% → nothing to do."""
    # entry=100, sl=95, tp=110 → progress at price=107 is 70%, pnl is 7%
    # 70% used to trigger BE (old 60%); must stay quiet now until 75%.
    assert compute_trailing_decision(_long_trade(), 107.0) is None
    # Low progress + sub-2% PnL
    assert compute_trailing_decision(_long_trade(tp=200.0), 101.5) is None


def test_link_style_60pct_progress_does_not_arm_be():
    """Regression: LINK was stopped after ~60% progress toward TP."""
    # entry=8.377, risk≈0.64%, R:R2 → tp≈8.484; MFE≈8.442 → ~60% progress, pnl≈0.77%
    trade = {
        "symbol": "LINK",
        "side": "BUY",
        "entry": 8.377,
        "sl": 8.323,
        "tp": 8.4848,
    }
    assert compute_trailing_decision(trade, 8.4417) is None


# ----------------------------------------------------------------------
# Smart Break-Even
# ----------------------------------------------------------------------

def test_smart_be_triggers_on_long_at_75_pct_progress():
    # entry=100, tp=110 → total_dist=10. Price=107.6 → progress 76%
    trade = _long_trade()
    decision = compute_trailing_decision(trade, 107.6)
    assert decision is not None
    assert decision.reason == "Smart BE"
    assert decision.new_sl == pytest.approx(100.2)


def test_smart_be_triggers_on_long_via_pnl_shortcut():
    """Even with low progress, a >2.0% unrealized PnL activates Smart BE."""
    trade = _long_trade(entry=100.0, sl=95.0, tp=200.0)
    # Price 102.1 → pnl 2.1%, progress only ~2.1%
    decision = compute_trailing_decision(trade, 102.1)
    assert decision is not None
    assert decision.reason == "Smart BE"
    assert decision.new_sl == pytest.approx(100.2)


def test_smart_be_triggers_on_short():
    trade = _short_trade(entry=100.0, sl=105.0, tp=90.0)
    # Price=92.4 → current_dist=7.6, total_dist=10, progress=76%
    decision = compute_trailing_decision(trade, 92.4)
    assert decision is not None
    assert decision.reason == "Smart BE"
    assert decision.new_sl == pytest.approx(99.8)


# ----------------------------------------------------------------------
# Trailing 80% and Aggressive Lock 90%
# ----------------------------------------------------------------------

def test_trailing_80_on_long():
    trade = _long_trade(entry=100.0, sl=95.0, tp=110.0)
    # Price=108.5 → 85% progress. Expect secure_price = 100 + 10*0.20 = 102
    decision = compute_trailing_decision(trade, 108.5)
    assert decision is not None
    assert decision.new_sl == pytest.approx(102.0)
    assert decision.reason == "Trailing 80%"


def test_aggressive_lock_90_overrides_on_long():
    trade = _long_trade(entry=100.0, sl=95.0, tp=110.0)
    # Price=109.5 → 95% progress. Lock = 100 + 10*0.40 = 104
    decision = compute_trailing_decision(trade, 109.5)
    assert decision is not None
    assert decision.new_sl == pytest.approx(104.0)
    assert decision.reason == "Aggressive Lock 90%"


def test_aggressive_lock_90_on_short():
    trade = _short_trade(entry=100.0, sl=105.0, tp=90.0)
    # Price=90.5 → current_dist=9.5, progress=95%. Lock = 100 - 10*0.40 = 96
    decision = compute_trailing_decision(trade, 90.5)
    assert decision is not None
    assert decision.new_sl == pytest.approx(96.0)
    assert decision.reason == "Aggressive Lock 90%"


def test_no_upgrade_when_sl_already_tighter_than_computed():
    """If SL is already past the would-be new level, keep it."""
    trade = _long_trade(entry=100.0, sl=105.0, tp=110.0)
    decision = compute_trailing_decision(trade, 109.5)
    assert decision is None


def test_progress_and_pnl_are_reported():
    trade = _long_trade(entry=100.0, sl=95.0, tp=110.0)
    decision = compute_trailing_decision(trade, 108.5)
    assert decision is not None
    assert decision.progress_pct == pytest.approx(85.0)
    assert decision.pnl_pct == pytest.approx(8.5)
