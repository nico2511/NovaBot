"""
Unit tests for RiskManager.

Covers:
  - Daily stop-loss enforcement (blocks trading once breached)
  - Max positions enforcement
  - record_trade_open / record_trade_close accounting
  - sync_with_hyperliquid: exchange is source of truth
  - calculate_position_size: min clamp, max cap, fixed/notional/risk_pct modes
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.core.risk_manager import RiskManager


def test_check_can_trade_initially_ok():
    rm = RiskManager(max_positions=2, daily_stop_loss=50.0)
    ok, reason = rm.check_can_trade()
    assert ok is True
    assert reason == "OK"


def test_max_positions_blocks_trading():
    rm = RiskManager(max_positions=1, daily_stop_loss=50.0)
    rm.record_trade_open()
    ok, reason = rm.check_can_trade()
    assert ok is False
    assert "Max positions" in reason


def test_daily_stop_loss_triggers_stop_mode():
    rm = RiskManager(max_positions=5, daily_stop_loss=50.0)
    rm.record_trade_open()
    rm.record_trade_close(pnl=-60.0)

    assert rm.state.is_stop_mode is True
    ok, reason = rm.check_can_trade()
    assert ok is False
    assert "Daily Stop Loss" in reason


def test_record_trade_close_decrements_positions():
    rm = RiskManager(max_positions=3, daily_stop_loss=100.0)
    rm.record_trade_open()
    rm.record_trade_open()
    assert rm.state.open_positions == 2

    rm.record_trade_close(pnl=10.0)
    assert rm.state.open_positions == 1
    assert rm.state.daily_pnl == 10.0


def test_record_trade_close_floors_at_zero():
    """If accounting gets out of sync, open_positions never goes negative."""
    rm = RiskManager(max_positions=3, daily_stop_loss=100.0)
    rm.record_trade_close(pnl=0.0)  # no open trade, but should not underflow
    assert rm.state.open_positions == 0


def test_update_settings_changes_limits():
    rm = RiskManager(max_positions=1, daily_stop_loss=50.0)
    rm.update_settings(max_positions=3, daily_stop_loss=100.0)
    assert rm.max_positions == 3
    assert rm.daily_stop_loss == 100.0


def test_sync_with_hyperliquid_forces_real_count():
    rm = RiskManager(max_positions=5, daily_stop_loss=100.0)
    rm.state.open_positions = 3  # bot thinks 3

    fake_hl = MagicMock()
    fake_hl.get_positions.return_value = [{"symbol": "BTC"}]  # exchange has 1

    result = rm.sync_with_hyperliquid(fake_hl)

    assert result["synced"] is True
    assert result["old_count"] == 3
    assert result["new_count"] == 1
    assert rm.state.open_positions == 1


def test_sync_with_hyperliquid_no_change_when_matching():
    rm = RiskManager(max_positions=5, daily_stop_loss=100.0)
    rm.state.open_positions = 2

    fake_hl = MagicMock()
    fake_hl.get_positions.return_value = [{"symbol": "BTC"}, {"symbol": "ETH"}]

    result = rm.sync_with_hyperliquid(fake_hl)

    assert result["synced"] is False
    assert result["count"] == 2
    assert rm.state.open_positions == 2


def test_sync_with_hyperliquid_handles_error():
    rm = RiskManager()
    fake_hl = MagicMock()
    fake_hl.get_positions.side_effect = RuntimeError("API down")

    result = rm.sync_with_hyperliquid(fake_hl)
    assert result["synced"] is False
    assert "API down" in result["error"]


def test_calculate_position_size_fixed_margin():
    """size_type=margin (default): notional = margin * leverage."""
    rm = RiskManager()
    # $20 margin * 5 leverage = $100 notional; at $50/coin -> 2 coins
    size = rm.calculate_position_size(
        price=50.0, sl_price=49.0, equity=1000.0,
        size_type="margin", size_value=20.0, leverage=5,
    )
    assert size == pytest.approx(2.0)


def test_calculate_position_size_notional():
    rm = RiskManager()
    # $1000 notional / $100 price = 10 coins
    size = rm.calculate_position_size(
        price=100.0, sl_price=99.0, equity=5000.0,
        size_type="notional", size_value=1000.0,
    )
    assert size == pytest.approx(10.0)


def test_calculate_position_size_risk_pct():
    """When size_value > 1 the code treats it as a percentage (size_value / 100)."""
    rm = RiskManager(max_positions=1)
    # Risk 2% of $1000 = $20. price=100, sl=99, diff=1 -> 20 coins
    size = rm.calculate_position_size(
        price=100.0, sl_price=99.0, equity=1000.0,
        method="risk_pct", size_value=2.0,
    )
    assert size == pytest.approx(20.0)


def test_risk_pct_splits_across_max_positions():
    """Portfolio risk budget is divided by max_positions (no N× stacking)."""
    rm = RiskManager(max_positions=2)
    # 2% of $1000 = $20 total → $10/slot → 10 coins at $1 risk/coin
    size = rm.calculate_position_size(
        price=100.0, sl_price=99.0, equity=1000.0,
        method="risk_pct", size_value=2.0,
    )
    assert size == pytest.approx(10.0)


def test_fixed_margin_splits_across_max_positions():
    rm = RiskManager(max_positions=2)
    # $20 margin / 2 = $10 × 5 lev = $50 notional / $50 = 1 coin
    size = rm.calculate_position_size(
        price=50.0, sl_price=49.0, equity=1000.0,
        size_type="margin", size_value=20.0, leverage=5,
    )
    assert size == pytest.approx(1.0)


def test_per_slot_notional_cap_splits():
    """Account notional cap is shared across slots."""
    rm = RiskManager(max_positions=2, max_notional_cap_multiplier=10.0)
    # equity $100 → account cap $1000 → per-slot $500
    size = rm.calculate_position_size(
        price=1.0, sl_price=0.9, equity=100.0,
        size_type="notional", size_value=5000.0,
    )
    assert size * 1.0 == pytest.approx(500.0)


def test_calculate_position_size_clamps_to_min():
    """Position below $12 minimum gets clamped up when max_positions=1."""
    rm = RiskManager(max_positions=1)
    # $1 margin * 1 leverage = $1 notional -> clamped to $12
    size = rm.calculate_position_size(
        price=100.0, sl_price=99.0, equity=1000.0,
        size_type="margin", size_value=1.0, leverage=1,
    )
    assert size * 100.0 == pytest.approx(12.0)


def test_multi_pos_refuses_upsize_below_hl_min():
    """With max_positions>1, do not clamp up below HL min (would defeat split)."""
    rm = RiskManager(max_positions=3, max_notional_cap_multiplier=50.0)
    # $1 margin / 3 slots * 1x lev ≈ $0.33 notional — refuse instead of upsizing to $12
    size = rm.calculate_position_size(
        price=100.0, sl_price=99.0, equity=1000.0,
        size_type="margin", size_value=1.0, leverage=1,
    )
    assert size == 0.0


def test_calculate_position_size_returns_zero_for_invalid_price():
    rm = RiskManager()
    assert rm.calculate_position_size(price=0.0, sl_price=0.0, equity=1000.0) == 0.0


def test_calculate_position_size_returns_zero_when_equity_is_zero():
    rm = RiskManager()
    assert rm.calculate_position_size(
        price=100.0, sl_price=99.0, equity=0.0,
        size_type="margin", size_value=20.0, leverage=5,
    ) == 0.0


def test_calculate_position_size_returns_zero_when_equity_too_low_for_min():
    """Equity $0.20 × cap 50 → max $10, below Hyperliquid $12 minimum."""
    rm = RiskManager(max_notional_cap_multiplier=50.0)
    assert rm.calculate_position_size(
        price=1.0, sl_price=0.9, equity=0.2,
        size_type="margin", size_value=20.0, leverage=5,
    ) == 0.0


def test_calculate_position_size_100_target_with_2_dollar_equity():
    """Cap ×50: $2 equity allows $100 notional (default margin × leverage)."""
    rm = RiskManager(max_notional_cap_multiplier=50.0)
    size = rm.calculate_position_size(
        price=0.5, sl_price=0.49, equity=2.0,
        size_type="margin", size_value=20.0, leverage=5,
    )
    assert size * 0.5 == pytest.approx(100.0)
