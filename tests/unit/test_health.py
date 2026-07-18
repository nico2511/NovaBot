"""Unit tests for /health status mapping (healthy / degraded / unhealthy)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.api.main import app


def _client() -> TestClient:
    return TestClient(app)


def test_health_unhealthy_when_bot_not_connected():
    with patch("app.services.internal.bridge.bot_bridge") as bridge:
        bridge.is_connected.return_value = False
        response = _client().get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["reason"] == "bot_not_connected"
    assert data["bot_connected"] is False


def test_health_degraded_when_engine_stopped():
    bot = MagicMock()
    bot.trading_enabled = False
    bot.is_running = False
    bot.active_trades = {}
    bot._loop_heartbeat = 0
    bot.is_loop_responsive.return_value = False
    bot.trade_lock = MagicMock()

    with patch("app.services.internal.bridge.bot_bridge") as bridge:
        bridge.is_connected.return_value = True
        bridge.get_bot_context.return_value = bot
        response = _client().get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["reason"] == "engine_stopped"


def test_health_unhealthy_when_loop_unresponsive():
    bot = MagicMock()
    bot.trading_enabled = True
    bot.is_running = True
    bot.active_trades = {"BTC": {}}
    bot._loop_heartbeat = 1
    bot.is_loop_responsive.return_value = False
    bot.trade_lock = MagicMock()

    with patch("app.services.internal.bridge.bot_bridge") as bridge:
        bridge.is_connected.return_value = True
        bridge.get_bot_context.return_value = bot
        response = _client().get("/health")

    assert response.status_code == 503
    data = response.json()
    assert data["status"] == "unhealthy"
    assert data["reason"] == "loop_unresponsive"


def test_health_healthy_when_running_and_responsive():
    bot = MagicMock()
    bot.trading_enabled = True
    bot.is_running = True
    bot.active_trades = {}
    bot._loop_heartbeat = 0  # just booted → no stale age
    bot.is_loop_responsive.return_value = True
    bot.trade_lock = MagicMock()

    with patch("app.services.internal.bridge.bot_bridge") as bridge:
        bridge.is_connected.return_value = True
        bridge.get_bot_context.return_value = bot
        response = _client().get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["reason"] is None
    assert "api_auth_enabled" in data
