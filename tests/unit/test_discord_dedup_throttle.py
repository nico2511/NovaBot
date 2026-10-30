from __future__ import annotations

import time

from unittest.mock import MagicMock

from app.services.discord_service import DiscordService
from app.utils import discord_dedup
from app.utils.discord_dedup import normalize_alert_key, should_send_alert


def test_normalize_collapses_real_429_not_prices():
    k1 = normalize_alert_key(
        "bot", "WARNING", "x", "⚠️ Hyperliquid 429 (rate limit) – candles ETH 15m"
    )
    k2 = normalize_alert_key(
        "bot", "WARNING", "x", "⚠️ Hyperliquid 429 (rate limit) – candles BTC 4h"
    )
    assert k1.endswith("hl_rate_limit")
    assert k1 == k2
    assert not normalize_alert_key("bot", "ERROR", "x", "FAILED ETH @ 3429.5").endswith(
        "hl_rate_limit"
    )


def test_hundred_429_alerts_one_send_then_plus_99():
    discord_dedup.reset_for_tests()
    svc = DiscordService()
    svc.alert_url = "http://example.invalid/webhook"
    svc.send_alert = MagicMock()
    base = time.time()
    t = {"now": base}
    import app.utils.discord_dedup as dd

    orig = time.time
    dd.time.time = lambda: t["now"]
    try:
        for i in range(100):
            svc.notify("WARNING", "NovaBot", f"Hyperliquid 429 rate limit sym{i}", source="bot")
        assert svc.send_alert.call_count == 1
        t["now"] = base + 16 * 60
        svc.notify("WARNING", "NovaBot", "Hyperliquid 429 rate limit again", source="bot")
        body = svc.send_alert.call_args[0][1]
        assert "+99 similaires" in body
    finally:
        dd.time.time = orig


def test_critical_keeps_45s_exact_key():
    discord_dedup.reset_for_tests()
    send1, _, _, _ = should_send_alert("app", "CRITICAL", "t", "disk full")
    send2, _, _, _ = should_send_alert("app", "CRITICAL", "t", "disk full")
    assert send1 and not send2


def test_execution_keeps_short_window():
    discord_dedup.reset_for_tests()
    send1, _, _, _ = should_send_alert("execution", "ERROR", "t", "fail A")
    send2, _, _, _ = should_send_alert("execution", "ERROR", "t", "fail A")
    assert send1 and not send2
