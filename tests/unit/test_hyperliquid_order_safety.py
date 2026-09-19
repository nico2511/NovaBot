"""Guardrails: no double entries, no reverse closes, no fake-empty order books."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.core.bot import BotContext
from app.services.hyperliquid_service import HyperliquidService
from app.services.safe_order_manager import SafeOrderManager


def test_classify_filled_plus_sl_error_is_fill():
    result = {
        "status": "ok",
        "response": {
            "data": {
                "statuses": [
                    {"filled": {"oid": 1, "totalSz": "0.01", "avgPx": "100"}},
                    {"error": "Insufficient margin for trigger"},
                ]
            }
        },
    }
    parsed = HyperliquidService._classify_order_statuses(result)
    assert parsed["filled"]
    assert parsed["errors"]


def test_classify_ioc_cancel_is_not_success():
    result = {
        "status": "ok",
        "response": {"data": {"statuses": [{"canceled": {"oid": 9}}]}},
    }
    parsed = HyperliquidService._classify_order_statuses(result)
    assert not parsed["filled"]
    assert parsed["canceled"]


def test_classify_waiting_trigger_ok():
    result = {
        "status": "ok",
        "response": {
            "data": {
                "statuses": [
                    {"filled": {"oid": 1}},
                    "waitingForTrigger",
                    "waitingForTrigger",
                ]
            }
        },
    }
    parsed = HyperliquidService._classify_order_statuses(result)
    assert parsed["filled"]
    assert len(parsed["waiting"]) == 2


def test_api_url_defaults_and_override():
    with patch("app.services.hyperliquid_service.config") as cfg:
        cfg.HYPERLIQUID_API_URL = ""
        assert HyperliquidService._api_base_url() == "https://api.hyperliquid.xyz"
        cfg.HYPERLIQUID_API_URL = "https://api.hyperliquid-testnet.xyz"
        assert HyperliquidService._api_base_url() == "https://api.hyperliquid-testnet.xyz"
        assert (
            HyperliquidService._ws_url_from_rest("https://api.hyperliquid-testnet.xyz")
            == "wss://api.hyperliquid-testnet.xyz/ws"
        )


def test_live_execution_helper():
    bot = object.__new__(BotContext)
    bot.execution_mode = "Live"
    assert bot._is_live_execution() is True
    bot.execution_mode = "Dry Run"
    assert bot._is_live_execution() is False
    bot.execution_mode = "paper"
    assert bot._is_live_execution() is False


def test_open_orders_rate_limit_does_not_look_empty():
    svc = object.__new__(HyperliquidService)
    svc.log_callback = None
    svc._open_orders_cache = {
        "time": 1.0,
        "data": [{"coin": "BTC", "oid": 1, "reduceOnly": True, "triggerPx": 1}],
    }
    svc._open_orders_fetch_failed = False

    with patch("app.services.hyperliquid_service.config") as cfg:
        cfg.HL_ACCOUNT_ADDRESS = "0xabc"
        with patch("app.services.hyperliquid_service.rate_limiter") as rl:
            rl.can_call.return_value = False
            orders = svc.get_open_orders("BTC")

    assert svc._open_orders_fetch_failed is True
    assert orders and orders[0]["oid"] == 1


def test_ensure_sl_tp_skips_when_orders_fetch_failed():
    hl = MagicMock()
    hl.get_open_orders.return_value = []
    hl._open_orders_fetch_failed = True
    mgr = SafeOrderManager(hl)
    placed = mgr.ensure_sl_tp(
        {"symbol": "ETH", "entry_price": 3000.0, "side": "BUY", "size": 1.0}
    )
    assert placed is False
    hl._place_protection_orders.assert_not_called()


def test_close_position_refuses_stale_snapshot():
    svc = object.__new__(HyperliquidService)
    svc.exchange = MagicMock()
    svc.log_callback = None
    svc._positions_fetch_failed = False
    svc._positions_stale = True
    svc.get_positions = MagicMock(return_value=[{"symbol": "BTC", "size": 1, "side": "BUY"}])
    svc.get_canonical_symbol = MagicMock(return_value="BTC")

    result = HyperliquidService.close_position.__wrapped__(svc, "BTC")
    assert result["status"] == "error"
    svc.exchange.market_open.assert_not_called()
    svc.exchange.market_close.assert_not_called()


def test_close_position_uses_reduce_only_market_close():
    svc = object.__new__(HyperliquidService)
    svc.exchange = MagicMock()
    svc.exchange.market_close.return_value = {
        "status": "ok",
        "response": {"data": {"statuses": [{"filled": {"oid": 7}}]}},
    }
    svc.log_callback = None
    svc._positions_fetch_failed = False
    svc._positions_stale = False
    svc.get_positions = MagicMock(
        side_effect=[
            [{"symbol": "ETH", "size": 2.0, "side": "BUY"}],
            [],
        ]
    )
    svc._get_precision = MagicMock(return_value=(4, 2))
    svc.get_canonical_symbol = MagicMock(return_value="ETH")
    svc.cancel_all_orders = MagicMock()

    with patch("app.services.hyperliquid_service.time.sleep"):
        result = HyperliquidService.close_position.__wrapped__(svc, "ETH")

    assert result["status"] == "success"
    svc.exchange.market_close.assert_called_once_with("ETH", sz=2.0)
    svc.exchange.market_open.assert_not_called()
    svc.cancel_all_orders.assert_called_once_with("ETH")
