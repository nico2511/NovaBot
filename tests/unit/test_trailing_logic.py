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
    """Progress below 60% AND PnL below 1.2% → nothing to do."""
    # entry=100, sl=95, tp=110 → progress at price=101 is 10%, pnl is 1.0%
    assert compute_trailing_decision(_long_trade(), 101.0) is None


# ----------------------------------------------------------------------
# Smart Break-Even
# ----------------------------------------------------------------------

def test_smart_be_triggers_on_long_at_60_pct_progress():
    # entry=100, tp=110 → total_dist=10. Price=107 → progress 70%
    trade = _long_trade()
    decision = compute_trailing_decision(trade, 107.0)
    assert decision is not None
    # At 70% progress we ALSO hit the 65% trailing rule, so the final
    # decision is Trailing 65% (higher SL than BE). Smart BE alone is
    # tested below with a PnL-only trigger.
    assert decision.reason in ("Smart BE", "Trailing 65%", "Aggressive Lock 75%")
    assert decision.new_sl > trade["sl"]


def test_smart_be_triggers_on_long_via_pnl_shortcut():
    """Even with low progress, a >1.2% unrealized PnL activates Smart BE."""
    # Far TP so progress stays low, but large entry move triggers PnL branch.
    trade = _long_trade(entry=100.0, sl=95.0, tp=200.0)
    # Price 101.5 → pnl 1.5%, progress only 1.5%
    decision = compute_trailing_decision(trade, 101.5)
    assert decision is not None
    assert decision.reason == "Smart BE"
    # BE = entry * 1.002 = 100.2
    assert decision.new_sl == pytest.approx(100.2)


def test_smart_be_triggers_on_short():
    trade = _short_trade(entry=100.0, sl=105.0, tp=90.0)
    # Price=93 → current_dist=7, total_dist=10, progress=70%
    decision = compute_trailing_decision(trade, 93.0)
    assert decision is not None
    assert decision.new_sl < trade["sl"]


# ----------------------------------------------------------------------
# Trailing 65% and Aggressive Lock 75%
# ----------------------------------------------------------------------

def test_trailing_65_on_long():
    trade = _long_trade(entry=100.0, sl=95.0, tp=110.0)
    # Price=107 → 70% progress. Expect secure_price = 100 + 10*0.20 = 102
    decision = compute_trailing_decision(trade, 107.0)
    assert decision is not None
    assert decision.new_sl == pytest.approx(102.0)
    assert decision.reason == "Trailing 65%"


def test_aggressive_lock_75_overrides_on_long():
    trade = _long_trade(entry=100.0, sl=95.0, tp=110.0)
    # Price=108 → 80% progress. Lock = 100 + 10*0.40 = 104
    decision = compute_trailing_decision(trade, 108.0)
    assert decision is not None
    assert decision.new_sl == pytest.approx(104.0)
    assert decision.reason == "Aggressive Lock 75%"


def test_aggressive_lock_75_on_short():
    trade = _short_trade(entry=100.0, sl=105.0, tp=90.0)
    # Price=92 → current_dist=8, progress=80%. Lock = 100 - 10*0.40 = 96
    decision = compute_trailing_decision(trade, 92.0)
    assert decision is not None
    assert decision.new_sl == pytest.approx(96.0)


def test_no_upgrade_when_sl_already_tighter_than_computed():
    """If SL is already past the would-be new level, keep it."""
    # Price at 108 (80% progress) would propose 104; but SL is already 105.
    trade = _long_trade(entry=100.0, sl=105.0, tp=110.0)
    decision = compute_trailing_decision(trade, 108.0)
    assert decision is None


def test_progress_and_pnl_are_reported():
    trade = _long_trade(entry=100.0, sl=95.0, tp=110.0)
    decision = compute_trailing_decision(trade, 107.0)
    assert decision is not None
    assert decision.progress_pct == pytest.approx(70.0)
    assert decision.pnl_pct == pytest.approx(7.0)
