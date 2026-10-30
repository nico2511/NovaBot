from __future__ import annotations

import time

from app.utils import discord_dedup
from app.utils.discord_dedup import normalize_alert_key, should_send_alert


def test_normalize_collapses_symbols_and_tf():
    k1 = normalize_alert_key("bot", "ERROR", "x", "Error fetching candles for ETH 15m")
    k2 = normalize_alert_key("bot", "ERROR", "x", "Error fetching candles for BTC 4h")
    assert k1 == k2 or "hl_rate_limit" in k1


def test_rate_limit_key():
    k = normalize_alert_key("bot", "WARNING", "t", "Hyperliquid 429 rate limit SOL 1m")
    assert k.endswith("hl_rate_limit")


def test_suppressed_counter_and_window():
    discord_dedup.reset_for_tests()
    base = time.time()
    t = {"now": base}
    import app.utils.discord_dedup as dd

    orig = time.time
    dd.time.time = lambda: t["now"]
    try:
        for i in range(5):
            should_send_alert("bot", "ERROR", "t", f"429 fail {i}")
        send, _k, sup, _since = should_send_alert("bot", "ERROR", "t", "429 fail again")
        assert send is False
        t["now"] = base + 16 * 60
        send2, _k2, sup2, _since2 = should_send_alert("bot", "ERROR", "t", "429 fail new")
        assert send2 is True
        assert sup2 >= 4
    finally:
        dd.time.time = orig


def test_execution_keeps_short_window():
    discord_dedup.reset_for_tests()
    send1, _, _, _ = should_send_alert("execution", "ERROR", "t", "fail A")
    send2, _, _, _ = should_send_alert("execution", "ERROR", "t", "fail A")
    assert send1 and not send2
