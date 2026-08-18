"""Routine filter logs stay off Discord; real errors still forward."""
from unittest.mock import MagicMock

from app.core.bot import BotContext


def _bot():
    bot = BotContext.__new__(BotContext)
    return bot


def test_forward_skips_no_signal_and_hard_veto(monkeypatch):
    notify = MagicMock()
    monkeypatch.setattr("app.core.bot.discord_service.notify", notify)
    bot = _bot()
    bot._forward_log_to_discord("⛔ No signal (XRP/trend_lt): 1h ADX below threshold (13.7 < 20.0)")
    bot._forward_log_to_discord("⛔ HARD VETO SELL XRP (supertrend): ADX slope dying")
    bot._forward_log_to_discord("❌ AI REJECTED: Sell signal lacks strong trend")
    notify.assert_not_called()


def test_forward_keeps_execution_errors(monkeypatch):
    notify = MagicMock(return_value=True)
    monkeypatch.setattr("app.core.bot.discord_service.notify", notify)
    bot = _bot()
    bot._forward_log_to_discord("❌ ATOMIC EXIT ERROR: No position found for NEAR")
    notify.assert_called_once()
    args = notify.call_args[0]
    assert args[0] == "ERROR"
    assert "ATOMIC EXIT" in args[2]
