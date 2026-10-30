from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.core.bot import BotContext
from app.utils.hl_log_patterns import is_hl_rate_limit_text


def test_rate_limit_text_not_triggered_by_price():
    assert not is_hl_rate_limit_text("❌ SL placement FAILED ETH @ 3429.1")
    assert is_hl_rate_limit_text("⚠️ Hyperliquid 429 (rate limit) – candles ETH 15m, cooldown 5s")


def test_forward_log_still_sends_stale_balance_and_failed():
    bot = object.__new__(BotContext)
    sent = []

    with patch("app.core.bot.discord_service") as ds:
        ds.notify = lambda level, title, body, source="bot": sent.append((level, body)) or True
        bot._forward_log_to_discord("⚠️ Returning stale balance cache due to API error")
        bot._forward_log_to_discord("Error fetching account balance: ClientError(500)")
        bot._forward_log_to_discord("⚠️ Hyperliquid 429 (rate limit) – candles ETH 15m, cooldown 5s")

    assert sent[0][0] == "WARNING"
    assert sent[1][0] == "ERROR"
    assert sent[2][0] == "WARNING"
