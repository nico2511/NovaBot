"""Unit tests for R-multiple trailing (1R BE, 1.5R lock 0.5R, 2R lock 1R)."""
from __future__ import annotations

import pytest

from app.core.trailing_logic import compute_trailing_decision


def _long_trade(entry=100.0, sl=95.0, tp=110.0):
    return {
        "symbol": "BTC",
        "side": "BUY",
        "entry": entry,
        "sl": sl,
        "initial_sl": sl,
        "tp": tp,
    }


def _short_trade(entry=100.0, sl=105.0, tp=90.0):
    return {
        "symbol": "BTC",
        "side": "SELL",
        "entry": entry,
        "sl": sl,
        "initial_sl": sl,
        "tp": tp,
    }


def test_returns_none_when_missing_fields():
    assert compute_trailing_decision({}, 100.0) is None
    assert compute_trailing_decision({"side": "BUY", "entry": 100}, 100.0) is None


def test_returns_none_for_unknown_side():
    trade = {"side": "HODL", "entry": 100.0, "sl": 95.0, "tp": 110.0}
    assert compute_trailing_decision(trade, 105.0) is None


def test_returns_none_when_price_missing_or_zero():
    assert compute_trailing_decision(_short_trade(), 0.0) is None
    assert compute_trailing_decision(_long_trade(), 0.0) is None
    assert compute_trailing_decision(_short_trade(), -1.0) is None


def test_returns_none_before_1r():
    # risk=5, 0.6R → 103. Not yet BE.
    assert compute_trailing_decision(_long_trade(), 103.0) is None


def test_sub_1r_link_style_does_not_arm_be():
    """~0.6R of a 2R SuperTrend target must not BE (old % of TP fired too early)."""
    trade = {
        "symbol": "LINK",
        "side": "BUY",
        "entry": 8.377,
        "sl": 8.323,
        "initial_sl": 8.323,
        "tp": 8.4848,
    }
    # 0.6R = 8.377 + 0.6 * 0.054 = 8.4094
    assert compute_trailing_decision(trade, 8.4094) is None


def test_be_at_1r_long():
    decision = compute_trailing_decision(_long_trade(), 105.1)
    assert decision is not None
    assert decision.reason == "BE 1R"
    assert decision.new_sl == pytest.approx(100.2)
    assert decision.r_multiple == pytest.approx(1.02, rel=1e-3)


def test_lock_half_r_at_1_5r_long():
    decision = compute_trailing_decision(_long_trade(), 107.6)
    assert decision is not None
    assert decision.new_sl == pytest.approx(102.5)
    assert "0.5R" in decision.reason


def test_lock_1r_at_2r_long():
    decision = compute_trailing_decision(_long_trade(), 110.0)
    assert decision is not None
    assert decision.new_sl == pytest.approx(105.0)
    assert "1R" in decision.reason


def test_be_at_1r_short():
    decision = compute_trailing_decision(_short_trade(), 94.9)
    assert decision is not None
    assert decision.reason == "BE 1R"
    assert decision.new_sl == pytest.approx(99.8)


def test_lock_half_r_at_1_5r_short():
    decision = compute_trailing_decision(_short_trade(), 92.4)
    assert decision is not None
    assert decision.new_sl == pytest.approx(97.5)


def test_does_not_loosen_existing_sl():
    trade = _long_trade()
    trade["sl"] = 104.0
    decision = compute_trailing_decision(trade, 110.0)
    # 2R lock would be 105 > 104, so still upgrades
    assert decision is not None
    assert decision.new_sl == pytest.approx(105.0)
    trade["sl"] = 106.0
    assert compute_trailing_decision(trade, 110.0) is None


def test_initial_sl_keeps_r_after_be_move():
    trade = _long_trade()
    trade["sl"] = 100.2
    decision = compute_trailing_decision(trade, 107.6)
    assert decision is not None
    assert decision.new_sl == pytest.approx(102.5)


def test_freeze_initial_sl_latches_once():
    from app.core.trailing_logic import freeze_initial_sl

    trade = {"sl": 0, "initial_sl": 0}
    assert freeze_initial_sl(trade, 95.0) is True
    assert trade["initial_sl"] == 95.0
    assert freeze_initial_sl(trade, 90.0) is False  # already latched
    assert trade["initial_sl"] == 95.0


def test_adopt_seed_zero_then_freeze_arms_trailing():
    """Sync-adopt seeds initial_sl=0; after analysis freezes ATR/exchange SL, R-ladder works."""
    from app.core.trailing_logic import freeze_initial_sl

    trade = {
        "symbol": "ETH",
        "side": "BUY",
        "entry": 100.0,
        "sl": 0,
        "initial_sl": 0,
        "tp": 110.0,
    }
    assert compute_trailing_decision(trade, 106.0) is None  # no risk base
    atr_sl = 95.0
    trade["sl"] = atr_sl
    freeze_initial_sl(trade, atr_sl)
    decision = compute_trailing_decision(trade, 105.1)
    assert decision is not None
    assert decision.reason == "BE 1R"


def test_adopt_smart_be_keeps_original_risk_sl():
    """When adopt Smart-BE tightens sl to entry, initial_sl must stay the protective stop."""
    from app.core.trailing_logic import freeze_initial_sl

    entry = 100.0
    exchange_sl = 95.0
    be_sl = entry * 1.002
    trade = {
        "symbol": "BTC",
        "side": "BUY",
        "entry": entry,
        "sl": 0,
        "initial_sl": 0,
        "tp": 110.0,
    }
    trade["sl"] = be_sl
    freeze_initial_sl(trade, exchange_sl)  # prefer pre-BE protective SL
    assert trade["initial_sl"] == exchange_sl
    # 1.5R from original risk=5 → price 107.5; lock 0.5R = 102.5
    decision = compute_trailing_decision(trade, 107.6)
    assert decision is not None
    assert decision.new_sl == pytest.approx(102.5)
