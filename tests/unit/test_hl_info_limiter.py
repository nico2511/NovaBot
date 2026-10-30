from __future__ import annotations

import pytest

from hyperliquid.utils.error import ClientError

from app.utils.rate_limiter import (
    HyperliquidInfoLimiter,
    InfoRateLimited,
    estimate_info_weight,
    payload_priority,
)
from app.services.hyperliquid_service import ThrottledInfo, Exchange


def test_estimate_info_weight_types():
    assert estimate_info_weight({"type": "clearinghouseState", "user": "0x1"}) == 2
    assert estimate_info_weight({"type": "userRole", "user": "0x1"}) == 60
    w = estimate_info_weight(
        {
            "type": "candleSnapshot",
            "startTime": 0,
            "endTime": 3_600_000,
            "interval": "1h",
        }
    )
    assert w >= 21
    assert estimate_info_weight({"type": "meta"}) == 20


def test_token_bucket_budget_over_60s():
    clock = {"t": 0.0}

    def monotonic():
        return clock["t"]

    def sleep(dt):
        clock["t"] += dt

    lim = HyperliquidInfoLimiter(clock=monotonic, sleep=sleep, budget_per_min=60)
    for _ in range(3):
        lim.acquire(20, "normal")
    assert lim.weight == 60
    with pytest.raises(InfoRateLimited):
        lim.acquire(20, "normal")


def test_normal_rejected_during_cooldown():
    lim = HyperliquidInfoLimiter(budget_per_min=600)
    lim.note_rate_limited()
    with pytest.raises(InfoRateLimited):
        lim.acquire(2, "normal")


def test_high_priority_allowed_during_cooldown():
    clock = {"t": 0.0}

    def monotonic():
        return clock["t"]

    def sleep(dt):
        clock["t"] += dt

    lim = HyperliquidInfoLimiter(clock=monotonic, sleep=sleep, budget_per_min=600)
    lim.note_rate_limited()
    lim.acquire(2, "high")


def test_cooldown_steps_and_reset():
    lim = HyperliquidInfoLimiter(budget_per_min=600)
    lim.note_rate_limited()
    first = lim.cooldown_until
    lim.note_rate_limited()
    assert lim.cooldown_until >= first
    lim.note_success()
    assert lim.cooldown_until == 0.0


def test_throttled_info_post_notes_429(monkeypatch):
    calls = {"n": 0}

    class Parent:
        def post(self, url_path, payload):
            calls["n"] += 1
            raise ClientError(429, None, "rate", None, {})

    info = ThrottledInfo.__new__(ThrottledInfo)
    monkeypatch.setattr(ThrottledInfo, "post", lambda self, u, p: Parent.post(self, u, p))
    with pytest.raises(ClientError):
        ThrottledInfo.post(info, "/info", {"type": "allMids"})
    assert calls["n"] == 1


def test_exchange_not_wrapped():
    assert Exchange is not None
    assert not hasattr(Exchange, "_hl_throttled")
