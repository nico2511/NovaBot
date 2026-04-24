"""
Unit tests for PositionReconciler.

These tests fully mock HyperliquidService and SafeOrderManager so they never
touch the network, and verify the three responsibilities:
  1. CLEANUP GHOSTS   — drop active_trades entries not present on exchange
  2. ADOPT ORPHANS    — register exchange positions unknown to the bot
  3. ENFORCE SL/TP    — call safety.ensure_sl_tp for each real position
"""
from __future__ import annotations

import threading
from unittest.mock import MagicMock

import pytest

from app.services.position_reconciler import PositionReconciler


class _BotStub:
    """Minimal BotContext replacement for reconciler tests."""

    def __init__(self, active_trades: dict | None = None):
        self.active_trades = active_trades or {}
        self.trade_lock = threading.RLock()
        self.adopt_calls: list[tuple[dict, float, float]] = []

    def _adopt_existing_position(self, pos: dict, sl: float = 0, tp: float = 0):
        self.adopt_calls.append((pos, sl, tp))
        self.active_trades[pos["symbol"]] = {
            "symbol": pos["symbol"],
            "side": pos.get("side", "BUY"),
            "entry": pos.get("entry_price", 0),
            "size": pos.get("size", 0),
            "sl": sl,
            "tp": tp,
        }


@pytest.fixture
def mocks():
    hl = MagicMock()
    safety = MagicMock()
    safety.ensure_sl_tp.return_value = False  # nothing to fix by default
    reconciler = PositionReconciler(hl, safety)
    return reconciler, hl, safety


# ----------------------------------------------------------------------
# Step 1 — Ghost cleanup
# ----------------------------------------------------------------------

def test_ghost_trade_is_removed(mocks):
    reconciler, hl, _ = mocks
    bot = _BotStub(active_trades={"BTC": {"side": "BUY"}, "ETH": {"side": "SELL"}})
    reconciler.bot_context = bot

    # Exchange only has BTC now; ETH is a ghost.
    hl.get_positions.return_value = [{"symbol": "BTC", "size": 0.1}]
    hl.get_open_orders.return_value = []

    reconciler.reconcile()

    assert "ETH" not in bot.active_trades
    assert "BTC" in bot.active_trades


def test_no_ghost_when_all_match(mocks):
    reconciler, hl, _ = mocks
    bot = _BotStub(active_trades={"BTC": {"side": "BUY"}})
    reconciler.bot_context = bot

    hl.get_positions.return_value = [{"symbol": "BTC", "size": 0.1}]
    hl.get_open_orders.return_value = []

    reconciler.reconcile()
    assert "BTC" in bot.active_trades


def test_zero_size_position_is_treated_as_ghost(mocks):
    """Exchange can return closed positions with size=0; they must not keep trades alive."""
    reconciler, hl, _ = mocks
    bot = _BotStub(active_trades={"BTC": {"side": "BUY"}})
    reconciler.bot_context = bot

    hl.get_positions.return_value = [{"symbol": "BTC", "size": 0}]
    hl.get_open_orders.return_value = []

    reconciler.reconcile()
    assert "BTC" not in bot.active_trades


# ----------------------------------------------------------------------
# Step 2 — Orphan adoption
# ----------------------------------------------------------------------

def test_orphan_long_is_adopted_with_correct_side(mocks):
    reconciler, hl, _ = mocks
    bot = _BotStub()
    reconciler.bot_context = bot

    hl.get_positions.return_value = [{
        "symbol": "BTC",
        "size": 0.05,
        "entry_price": 50000.0,
        "side": "LONG",
    }]
    hl.get_open_orders.return_value = []

    reconciler.reconcile()

    assert "BTC" in bot.active_trades
    assert bot.active_trades["BTC"]["side"] == "BUY"
    assert bot.active_trades["BTC"]["entry"] == 50000.0


def test_orphan_short_is_adopted_with_correct_side(mocks):
    reconciler, hl, _ = mocks
    bot = _BotStub()
    reconciler.bot_context = bot

    hl.get_positions.return_value = [{
        "symbol": "ETH",
        "size": 1.0,
        "entry_price": 3000.0,
        "side": "SHORT",
    }]
    hl.get_open_orders.return_value = []

    reconciler.reconcile()
    assert bot.active_trades["ETH"]["side"] == "SELL"


def test_orphan_side_inferred_from_signed_szi(mocks):
    """When 'side' is missing, reconciler uses the signed szi field."""
    reconciler, hl, _ = mocks
    bot = _BotStub()
    reconciler.bot_context = bot

    hl.get_positions.return_value = [{
        "symbol": "SOL",
        "size": 5.0,
        "entry_price": 150.0,
        "szi": "-5.0",  # negative = SHORT
    }]
    hl.get_open_orders.return_value = []

    reconciler.reconcile()
    assert bot.active_trades["SOL"]["side"] == "SELL"


def test_orphan_preserves_existing_sl_tp_from_exchange(mocks):
    reconciler, hl, _ = mocks
    bot = _BotStub()
    reconciler.bot_context = bot

    hl.get_positions.return_value = [{
        "symbol": "BTC",
        "size": 0.1,
        "entry_price": 50000.0,
        "side": "LONG",
    }]
    # Existing reduce-only orders on the exchange: SL at 49000, TP at 52000
    hl.get_open_orders.return_value = [
        {"reduceOnly": True, "triggerPx": "49000"},   # below entry (long) → SL
        {"reduceOnly": True, "triggerPx": "52000"},   # above entry (long) → TP
    ]

    reconciler.reconcile()

    trade = bot.active_trades["BTC"]
    assert trade["sl"] == 49000.0
    assert trade["tp"] == 52000.0


def test_already_tracked_position_is_not_re_adopted(mocks):
    reconciler, hl, _ = mocks
    bot = _BotStub(active_trades={"BTC": {"side": "BUY", "entry": 99999}})
    reconciler.bot_context = bot

    hl.get_positions.return_value = [{
        "symbol": "BTC",
        "size": 0.1,
        "entry_price": 50000.0,
        "side": "LONG",
    }]
    hl.get_open_orders.return_value = []

    reconciler.reconcile()

    # No adoption call, existing record preserved
    assert bot.adopt_calls == []
    assert bot.active_trades["BTC"]["entry"] == 99999


# ----------------------------------------------------------------------
# Step 3 — SL/TP enforcement + error handling
# ----------------------------------------------------------------------

def test_ensure_sl_tp_is_called_for_each_position(mocks):
    reconciler, hl, safety = mocks
    bot = _BotStub(active_trades={"BTC": {"side": "BUY"}, "ETH": {"side": "BUY"}})
    reconciler.bot_context = bot

    hl.get_positions.return_value = [
        {"symbol": "BTC", "size": 0.1},
        {"symbol": "ETH", "size": 1.0},
    ]
    hl.get_open_orders.return_value = []

    reconciler.reconcile()

    assert safety.ensure_sl_tp.call_count == 2


def test_reconcile_swallows_exchange_error(mocks):
    """A hyperliquid outage must not crash the reconciler."""
    reconciler, hl, _ = mocks
    bot = _BotStub(active_trades={"BTC": {}})
    reconciler.bot_context = bot

    hl.get_positions.side_effect = RuntimeError("API down")

    # Must not raise
    reconciler.reconcile()
    # State is untouched
    assert "BTC" in bot.active_trades


def test_run_tick_respects_interval(mocks):
    """run_tick should only call reconcile() once per interval window."""
    reconciler, hl, _ = mocks
    bot = _BotStub()
    reconciler.bot_context = bot

    hl.get_positions.return_value = []
    hl.get_open_orders.return_value = []

    # First tick runs reconcile, second one within the 30s window skips
    reconciler.run_tick()
    first_call_count = hl.get_positions.call_count
    reconciler.run_tick()
    assert hl.get_positions.call_count == first_call_count
