"""OpenRouter remaining-credit probe and IAService spend gate."""
from __future__ import annotations

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.main import app
from app.services.ia import IAService
from app.services.openrouter_credits import (
    STATUS_CRITICAL,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_UNKNOWN,
    STATUS_WARN,
    build_credit_snapshot,
    classify_credit_status,
    remaining_from_credits_payload,
    remaining_from_key_payload,
    tighter_remaining,
)


def test_classify_credit_status_thresholds():
    assert classify_credit_status(None, 1.0, 0.10) == STATUS_UNKNOWN
    assert classify_credit_status(5.0, 1.0, 0.10) == STATUS_OK
    assert classify_credit_status(1.0, 1.0, 0.10) == STATUS_WARN
    assert classify_credit_status(0.50, 1.0, 0.10) == STATUS_WARN
    assert classify_credit_status(0.10, 1.0, 0.10) == STATUS_CRITICAL
    assert classify_credit_status(0.0, 1.0, 0.10) == STATUS_CRITICAL
    assert classify_credit_status(-1.0, 1.0, 0.10) == STATUS_CRITICAL


def test_remaining_from_credits_and_key():
    assert remaining_from_credits_payload({"data": {"total_credits": 10.5, "total_usage": 2.5}}) == 8.0
    assert remaining_from_credits_payload({"total_credits": 4, "total_usage": 1}) == 3.0
    assert remaining_from_credits_payload({}) is None
    assert remaining_from_key_payload({"data": {"limit_remaining": 1.25}}) == 1.25
    assert remaining_from_key_payload({"data": {"limit_remaining": None}}) is None
    assert tighter_remaining(8.0, 1.25) == 1.25
    assert tighter_remaining(8.0, None) == 8.0
    assert tighter_remaining(None, None) is None


def test_build_snapshot_prefers_tighter_key_cap():
    snap = build_credit_snapshot(
        credits_payload={"data": {"total_credits": 20.0, "total_usage": 5.0}},
        key_payload={"data": {"limit_remaining": 0.50, "is_free_tier": False}},
        warn_usd=1.0,
        min_usd=0.10,
    )
    assert snap["remaining_usd"] == 0.50
    assert snap["account_remaining_usd"] == 15.0
    assert snap["status"] == STATUS_WARN
    assert snap["source"] == "credits+key"


def test_build_snapshot_error_when_no_remaining():
    snap = build_credit_snapshot(error="/credits: HTTP 500", warn_usd=1.0, min_usd=0.10)
    assert snap["status"] == STATUS_ERROR
    assert snap["ok"] is False
    assert snap["remaining_usd"] is None


def test_refresh_credits_from_account_payload():
    ia = IAService()
    ia.openrouter_key = "sk-test"
    payload = (
        {"data": {"total_credits": 10.0, "total_usage": 2.0}},
        {"data": {"limit_remaining": None}},
        None,
    )
    with patch("app.services.ia.fetch_credit_payloads", return_value=payload) as fetch:
        with patch.object(ia, "_notify_credit_status"):
            snap = ia.refresh_credits(notify=True, reason="startup")
    fetch.assert_called_once()
    assert snap["remaining_usd"] == 8.0
    assert snap["status"] == STATUS_OK
    assert ia.credits_allow_ai_call() is True


def test_maybe_refresh_respects_interval():
    ia = IAService()
    ia.openrouter_key = "sk-test"
    ia._last_credit_check = datetime.now()
    ia._credit_status = {"status": STATUS_OK, "remaining_usd": 9.0}
    with patch("app.services.ia.fetch_credit_payloads") as fetch:
        out = ia.maybe_refresh_credits()
    fetch.assert_not_called()
    assert out["remaining_usd"] == 9.0


def test_critical_credits_skip_openrouter_call():
    ia = IAService()
    ia.openrouter_key = "sk-test"
    ia.client = MagicMock()
    ia._last_credit_check = datetime.now()
    ia._credit_status = {"status": STATUS_CRITICAL, "remaining_usd": 0.01}
    result = ia._call_openrouter_api("neutral market commentary only")
    ia.client.chat.completions.create.assert_not_called()
    assert result["model"] == "rule-based-fallback"
    parsed = json.loads(result.get("raw_output") or "{}")
    assert parsed.get("approved") is False
    assert parsed.get("rejection_reason_category") == "AI_UNAVAILABLE"


def test_402_marks_credits_critical_and_returns_fallback():
    ia = IAService()
    ia.openrouter_key = "sk-test"
    ia.client = MagicMock()
    ia.client.chat.completions.create.side_effect = Exception(
        "Error code: 402 - Payment Required, Insufficient credits"
    )
    ia._last_credit_check = datetime.now()
    ia._credit_status = {"status": STATUS_OK, "remaining_usd": 3.0}
    with patch.object(ia, "_notify_credit_status"):
        result = ia._call_openrouter_api("analyze market")
    assert result["model"] == "rule-based-fallback"
    assert ia._credit_status["status"] == STATUS_CRITICAL
    assert ia.credits_allow_ai_call() is False
    assert ia.circuit_breaker_until is not None
    assert ia.circuit_breaker_until > datetime.now()


def test_notify_escalates_once_then_stays_quiet():
    ia = IAService()
    warn_snap = {
        "status": STATUS_WARN,
        "remaining_usd": 0.80,
    }
    with patch("app.services.discord_service.discord_service") as discord:
        ia._notify_credit_status(warn_snap, reason="periodic")
        ia._notify_credit_status(warn_snap, reason="periodic")
    assert discord.notify.call_count == 1


def test_health_includes_cached_openrouter_snapshot():
    with patch("app.services.internal.bridge.bot_bridge") as bridge:
        bridge.is_connected.return_value = False
        response = TestClient(app).get("/health")
    data = response.json()
    assert "openrouter" in data
    assert "status" in data["openrouter"]
    assert "remaining_usd" in data["openrouter"]
