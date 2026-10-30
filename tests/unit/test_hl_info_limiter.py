from __future__ import annotations

import threading

import pytest
from hyperliquid.utils.error import ClientError

from app.services.hyperliquid_service import ThrottledInfo
from app.utils.rate_limiter import (
    HyperliquidInfoLimiter,
    InfoRateLimited,
    estimate_info_weight,
    hl_info_limiter,
)


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


def test_high_priority_never_raises_even_with_empty_bucket():
    clock = {"t": 0.0}

    def monotonic():
        return clock["t"]

    def sleep(dt):
        clock["t"] += dt

    lim = HyperliquidInfoLimiter(clock=monotonic, sleep=sleep, budget_per_min=600)
    lim.tokens = 0
    lim.acquire(31, "high")
    assert lim.weight == 31


def test_high_priority_waits_during_cooldown_without_reject():
    clock = {"t": 0.0}

    def monotonic():
        return clock["t"]

    def sleep(dt):
        clock["t"] += dt

    lim = HyperliquidInfoLimiter(clock=monotonic, sleep=sleep, budget_per_min=600)
    lim.note_rate_limited()
    lim.acquire(2, "high")
    assert lim.calls == 1


def test_normal_rejected_during_cooldown():
    lim = HyperliquidInfoLimiter(budget_per_min=600)
    lim.note_rate_limited()
    with pytest.raises(InfoRateLimited):
        lim.acquire(2, "normal")


def test_cooldown_tiers_and_success_resets_step_only():
    clock = {"t": 0.0}

    def monotonic():
        return clock["t"]

    lim = HyperliquidInfoLimiter(clock=monotonic, sleep=lambda _d: None, budget_per_min=600)
    lim.note_rate_limited()
    t1 = lim.cooldown_until - clock["t"]
    lim.note_rate_limited()
    t2 = lim.cooldown_until - clock["t"]
    assert 4 <= t1 <= 7
    assert 8 <= t2 <= 14
    lim.note_rate_limited()
    lim.note_rate_limited()
    t4 = lim.cooldown_until - clock["t"]
    assert 48 <= t4 <= 72
    until = lim.cooldown_until
    lim.note_success()
    assert lim.cooldown_until == until
    assert lim._cooldown_step == 0


def test_token_bucket_refill_over_simulated_minute():
    clock = {"t": 0.0}

    def monotonic():
        return clock["t"]

    def sleep(dt):
        clock["t"] += dt

    lim = HyperliquidInfoLimiter(clock=monotonic, sleep=sleep, budget_per_min=60)
    lim.acquire(60, "normal")
    assert lim.weight == 60
    clock["t"] = 60.0
    lim.acquire(60, "normal")
    assert lim.weight == 120


def test_throttled_info_post_notes_429_without_retry(monkeypatch):
    calls = {"post": 0, "notes": 0}

    def fake_post(_self, _url, _payload):
        calls["post"] += 1
        raise ClientError(429, None, "rate", None, {})

    monkeypatch.setattr("hyperliquid.info.Info.post", fake_post)

    def note():
        calls["notes"] += 1

    monkeypatch.setattr("app.services.hyperliquid_service.hl_info_limiter.note_rate_limited", note)
    info = ThrottledInfo.__new__(ThrottledInfo)
    with pytest.raises(ClientError):
        ThrottledInfo.post(info, "/info", {"type": "allMids"})
    assert calls["post"] == 1
    assert calls["notes"] == 1


def test_high_under_contention_from_multiple_threads():
    hl_info_limiter.reset()
    hl_info_limiter.tokens = 0
    hl_info_limiter.note_rate_limited()
    errors = []

    def worker():
        try:
            hl_info_limiter.acquire(25, "high")
        except InfoRateLimited as e:
            errors.append(e)

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
