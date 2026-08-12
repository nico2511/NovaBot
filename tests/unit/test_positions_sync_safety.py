"""Guardrails: positions/history failures must not create ghost closes."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.hyperliquid_service import HyperliquidService


@pytest.fixture
def service():
    svc = object.__new__(HyperliquidService)
    svc.info = MagicMock()
    svc.log_callback = None
    svc.ws_manager = None
    svc._positions_cache = {"time": 0, "data": None}
    svc._positions_cache_ttl = 10
    svc._positions_fetch_failed = False
    return svc


def test_stale_positions_returned_on_error(service):
    service._positions_cache = {
        "time": 1.0,
        "data": [{"symbol": "BTC", "size": 0.01, "side": "SELL"}],
    }
    service.info.user_state.side_effect = Exception("504 Gateway Timeout")

    with patch("app.services.hyperliquid_service.config") as cfg:
        cfg.HL_ACCOUNT_ADDRESS = "0xabc"
        with patch("app.services.hyperliquid_service.rate_limiter") as rl:
            rl.can_call.return_value = True
            positions = service.get_positions()

    assert service._positions_fetch_failed is False
    assert positions[0]["symbol"] == "BTC"


def test_no_cache_marks_fetch_failed(service):
    with patch("app.services.hyperliquid_service.config") as cfg:
        cfg.HL_ACCOUNT_ADDRESS = "0xabc"
        with patch("app.services.hyperliquid_service.rate_limiter") as rl:
            rl.can_call.return_value = False
            positions = service.get_positions()

    assert positions == []
    assert service._positions_fetch_failed is True


def test_trade_history_returns_none_after_exhausted_504(service):
    service.info.user_fills.side_effect = Exception((504, "<!DOCTYPE HTML"))

    with patch("app.services.hyperliquid_service.time.sleep"):
        with patch("app.services.hyperliquid_service.config") as cfg:
            cfg.HL_ACCOUNT_ADDRESS = "0xabc"
            result = service.get_trade_history(limit=10)

    assert result is None
    assert service.info.user_fills.call_count == 3


def test_trade_history_retries_then_succeeds(service):
    service.info.user_fills.side_effect = [
        Exception((504, "timeout")),
        [{"coin": "BTC", "side": "A", "px": "1", "sz": "1", "time": 1, "oid": 1, "closedPnl": "-0.3", "fee": 0, "dir": "Close Short"}],
    ]

    with patch("app.services.hyperliquid_service.time.sleep"):
        with patch("app.services.hyperliquid_service.config") as cfg:
            cfg.HL_ACCOUNT_ADDRESS = "0xabc"
            result = service.get_trade_history(limit=10)

    assert result is not None
    assert len(result) == 1
    assert result[0]["symbol"] == "BTC"
