"""A3 must never call Hyperliquid order APIs in Dry Run / paper execution modes."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.bot import BotContext
from strategies.a3_ema_trend_4h import A3_STRATEGY_ID


@pytest.fixture
def bot_minimal():
    bot = object.__new__(BotContext)
    bot.trading_enabled = True
    bot.execution_mode = "Dry Run"
    bot.active_symbol = "BTC"
    bot.max_positions = 2
    bot.add_log = MagicMock()
    bot._log_execution_error = MagicMock()
    bot._sync_daily_risk_pnl = MagicMock()
    bot.risk_manager = MagicMock()
    bot.risk_manager.check_can_trade.return_value = (True, "OK")
    bot.can_open_trade = MagicMock(return_value=(True, "ok"))
    bot._resolve_trade_leverage = MagicMock(return_value=1)
    bot.trade_lock = __import__("threading").Lock()
    bot.active_trades = {}
    return bot


def test_execute_entry_atomically_blocks_a3_dry_run(bot_minimal):
    with patch("app.core.live_execution.hyperliquid_service") as hl:
        hl.execute_order = MagicMock()
        hl.get_positions.return_value = []
        hl._positions_fetch_failed = False
        hl._positions_stale = False
        result = BotContext.execute_entry_atomically(
            bot_minimal,
            "BTC",
            "BUY",
            0.01,
            price=50000.0,
            sl=48000.0,
            tp=60000.0,
            strategy=A3_STRATEGY_ID,
        )
    assert result["status"] == "ignored"
    hl.execute_order.assert_not_called()


def test_execute_entry_atomically_blocks_a3_paper_mode(bot_minimal):
    bot_minimal.execution_mode = "paper"
    with patch("app.core.live_execution.hyperliquid_service") as hl:
        hl.execute_order = MagicMock()
        hl.bulk_orders = MagicMock()
        result = BotContext.execute_entry_atomically(
            bot_minimal,
            "ETH",
            "SELL",
            0.1,
            price=3000.0,
            sl=3200.0,
            tp=2000.0,
            strategy=A3_STRATEGY_ID,
        )
    assert result["status"] == "ignored"
    hl.execute_order.assert_not_called()
    hl.bulk_orders.assert_not_called()
