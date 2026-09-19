"""Tests for WebSocket price cache seeding and symbol sync."""
from unittest.mock import MagicMock, patch

from app.services.hyperliquid_service import HyperliquidService
from app.utils.websocket_manager import WebSocketPriceManager


def test_seed_price_populates_cache():
    mgr = WebSocketPriceManager(["BTC"], logger=None)
    mgr.seed_price("ETH", 123.45)
    assert mgr.get_price("ETH") == 123.45


def test_get_current_price_seeds_cache_from_rest_without_warning_spam():
    svc = HyperliquidService.__new__(HyperliquidService)
    svc.log_callback = None
    svc._ws_fallback_last_log = {}
    svc.ws_manager = WebSocketPriceManager(["ADA"], logger=None)
    svc.info = MagicMock()

    with patch.object(svc, "get_canonical_symbol", side_effect=lambda s: s), patch.object(
        svc, "_fetch_rest_mid", return_value=0.42
    ):
        px = HyperliquidService.get_current_price(svc, "ADA")

    assert px == 0.42
    assert svc.ws_manager.get_price("ADA") == 0.42


def test_user_fills_snapshot_is_cached():
    mgr = WebSocketPriceManager(["BTC"], logger=None, user_address="0xabc")
    mgr._process_message(
        '{"channel":"userFills","data":{"isSnapshot":true,"user":"0xabc",'
        '"fills":[{"coin":"ETH","px":"100","sz":"1","side":"A","time":1,'
        '"oid":9,"closedPnl":"-1.5","dir":"Close Long","fee":0}]}}'
    )
    fills = mgr.recent_user_fills("ETH")
    assert len(fills) == 1
    assert fills[0]["oid"] == 9
    assert fills[0]["dir"] == "Close Long"
