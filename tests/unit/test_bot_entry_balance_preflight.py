from __future__ import annotations

from unittest.mock import MagicMock

from app.core.bot import BotContext


def test_entry_balance_preflight_clears_cooldown_and_sleeps(monkeypatch):
    bot = object.__new__(BotContext)
    bot.active_symbol = "ETH"
    bot.add_log = MagicMock()
    bot._log_execution_error = MagicMock()
    cleared = []
    slept = []
    bot._clear_strategy_entry_cooldown = lambda *a, **k: cleared.append(a)
    monkeypatch.setattr(
        "app.core.bot.hyperliquid_service.get_account_balance",
        lambda force_refresh=False: {"status": "error", "message": "ClientError(429)"},
    )
    monkeypatch.setattr("app.core.bot.time.sleep", lambda s: slept.append(s))

    sig = {"signal": "BUY", "strategy": "a3_ema_trend_4h"}
    out = bot._entry_balance_preflight(sig, "ETH")

    assert out is None
    assert cleared == [("a3_ema_trend_4h", "ETH")]
    assert slept == [10]
