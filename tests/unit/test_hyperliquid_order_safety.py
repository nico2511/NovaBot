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


def test_avg_px_and_sz_from_fills():
    filled = [{"oid": 1, "totalSz": "0.25", "avgPx": "101.5"}]
    assert HyperliquidService._avg_px_from_fills(filled) == 101.5
    assert HyperliquidService._sz_from_fills(filled, 1.0) == 0.25
    assert HyperliquidService._avg_px_from_fills([]) == 0.0


def test_confirm_or_place_sl_true_when_sl_exists():
    svc = object.__new__(HyperliquidService)
    svc.log_callback = None
    svc.find_protection_orders = MagicMock(
        return_value={
            "sl": {"oid": 9, "sz": 1.0, "reduceOnly": True, "triggerPx": 99},
            "tp": None,
            "fetch_failed": False,
            "orders": [],
        }
    )
    svc._modify_protection_order = MagicMock()
    assert svc.confirm_or_place_sl("BTC", True, 1.0, 99.0, entry=100.0) is True
    svc._modify_protection_order.assert_not_called()


def test_confirm_or_place_sl_places_when_missing_then_ok():
    svc = object.__new__(HyperliquidService)
    svc.log_callback = None
    svc._place_protection_orders = MagicMock()
    svc.find_protection_orders = MagicMock(
        side_effect=[
            {"sl": None, "tp": None, "fetch_failed": False, "orders": []},
            {"sl": {"oid": 3}, "tp": None, "fetch_failed": False, "orders": []},
        ]
    )
    assert svc.confirm_or_place_sl("ETH", True, 2.0, 90.0, tp_price=110.0, entry=100.0) is True
    svc._place_protection_orders.assert_called_once()


def test_confirm_or_place_sl_false_when_still_missing():
    svc = object.__new__(HyperliquidService)
    svc.log_callback = None
    svc._place_protection_orders = MagicMock()
    svc.find_protection_orders = MagicMock(
        return_value={"sl": None, "tp": None, "fetch_failed": False, "orders": []}
    )
    assert svc.confirm_or_place_sl("ETH", True, 2.0, 90.0, entry=100.0) is False


def test_confirm_or_place_sl_none_when_book_unreadable():
    svc = object.__new__(HyperliquidService)
    svc.log_callback = None
    svc.find_protection_orders = MagicMock(
        return_value={"sl": None, "tp": None, "fetch_failed": True, "orders": []}
    )
    assert svc.confirm_or_place_sl("ETH", True, 2.0, 90.0, entry=100.0) is None


def test_master_key_refused_without_override():
    with pytest.raises(RuntimeError, match="MASTER wallet"):
        HyperliquidService._assert_not_master_wallet("0xAbC", "0xabc", allow=False)


def test_master_key_allowed_with_override():
    warn = HyperliquidService._assert_not_master_wallet("0xAbC", "0xabc", allow=True)
    assert "MASTER wallet" in warn


def test_agent_key_is_not_master():
    assert (
        HyperliquidService._assert_not_master_wallet("0xagent", "0xmaster", allow=False)
        is None
    )


def _svc_for_execute():
    svc = object.__new__(HyperliquidService)
    svc.exchange = MagicMock()
    svc.log_callback = None
    svc.get_canonical_symbol = MagicMock(side_effect=lambda s: s)
    svc._get_precision = MagicMock(return_value=(4, 2))
    svc.get_current_price = MagicMock(return_value=100.0)
    svc._round_price = MagicMock(side_effect=lambda px, _d: round(float(px), 4))
    svc._position_open_on_exchange = MagicMock(return_value=False)
    return svc


def test_execute_order_reuses_cloid_after_timeout():
    svc = _svc_for_execute()
    clo_a, clo_b = MagicMock(name="cloid-a"), MagicMock(name="cloid-b")
    clo_a.__str__.return_value = "0xaaaa"
    svc._new_cloid = MagicMock(side_effect=[clo_a, clo_b])
    svc.exchange.bulk_orders.side_effect = [
        RuntimeError("timeout"),
        {
            "status": "ok",
            "response": {
                "data": {"statuses": [{"filled": {"oid": 1, "totalSz": "1", "avgPx": "100"}}]}
            },
        },
    ]

    with patch("time.sleep"):
        result = HyperliquidService.execute_order(
            svc, "BTC", True, 1.0, price=100, sl_price=99, tp_price=110
        )

    assert result["status"] == "success"
    assert svc.exchange.bulk_orders.call_count == 2
    first = svc.exchange.bulk_orders.call_args_list[0][0][0][0]
    second = svc.exchange.bulk_orders.call_args_list[1][0][0][0]
    assert first["cloid"] is clo_a
    assert second["cloid"] is clo_a
    assert svc._new_cloid.call_count == 1


def test_execute_order_mints_new_cloid_after_ioc_cancel():
    svc = _svc_for_execute()
    clo_a, clo_b = MagicMock(name="cloid-a"), MagicMock(name="cloid-b")
    clo_b.__str__.return_value = "0xbbbb"
    svc._new_cloid = MagicMock(side_effect=[clo_a, clo_b])
    svc.exchange.bulk_orders.side_effect = [
        {"status": "ok", "response": {"data": {"statuses": [{"canceled": {"oid": 1}}]}}},
        {
            "status": "ok",
            "response": {
                "data": {"statuses": [{"filled": {"oid": 2, "totalSz": "1", "avgPx": "100"}}]}
            },
        },
    ]

    with patch("time.sleep"):
        result = HyperliquidService.execute_order(
            svc, "BTC", True, 1.0, price=100, sl_price=99
        )

    assert result["status"] == "success"
    first = svc.exchange.bulk_orders.call_args_list[0][0][0][0]
    second = svc.exchange.bulk_orders.call_args_list[1][0][0][0]
    assert first["cloid"] is clo_a
    assert second["cloid"] is clo_b


def test_execute_order_btc_uses_0_8pct_ioc_slip():
    svc = _svc_for_execute()
    svc._new_cloid = MagicMock(return_value=None)
    svc.exchange.bulk_orders.return_value = {
        "status": "ok",
        "response": {
            "data": {"statuses": [{"filled": {"oid": 1, "totalSz": "1", "avgPx": "100"}}]}
        },
    }
    HyperliquidService.execute_order(svc, "BTC", True, 1.0, price=100, sl_price=99)
    entry = svc.exchange.bulk_orders.call_args[0][0][0]
    assert entry["limit_px"] == pytest.approx(100.8)


def test_sync_sl_tp_modifies_existing_instead_of_cancel_all():
    svc = object.__new__(HyperliquidService)
    svc.exchange = MagicMock()
    svc.log_callback = None
    sl_order = {"oid": 11, "coin": "BTC", "reduceOnly": True, "triggerPx": 99, "orderType": "Stop Market"}
    svc.find_protection_orders = MagicMock(
        return_value={"sl": sl_order, "tp": None, "fetch_failed": False, "orders": [sl_order]}
    )
    svc._modify_protection_order = MagicMock(return_value=True)
    svc._place_protection_orders = MagicMock()
    svc.cancel_all_orders = MagicMock()

    result = HyperliquidService.sync_sl_tp.__wrapped__(
        svc, "BTC", True, 1.0, 99.5, 0, entry_price=100.0
    )
    assert result["status"] == "success"
    svc.cancel_all_orders.assert_not_called()
    svc._modify_protection_order.assert_called_once()
    svc._place_protection_orders.assert_not_called()
