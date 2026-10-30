from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.hyperliquid_service import HyperliquidService


def _balance_service(monkeypatch):
    svc = object.__new__(HyperliquidService)
    svc.log = MagicMock()
    svc._cache_ttl = 60.0
    svc._balance_cache = {
        "time": 1000.0,
        "data": {"status": "success", "total_equity": 50.0, "available_balance": 40.0},
    }
    svc._abstraction_cache = {"time": 1000.0, "mode": "unifiedAccount"}
    svc.info = MagicMock()
    svc.info.user_state.side_effect = Exception((429, None, "null", None, {}))
    svc.info.spot_user_state.side_effect = Exception((429, None, "null", None, {}))
    monkeypatch.setattr("app.services.hyperliquid_service.config.HL_ACCOUNT_ADDRESS", "0xabc")
    return svc


def test_balance_cached_within_ttl(monkeypatch):
    svc = object.__new__(HyperliquidService)
    svc.log = MagicMock()
    svc._cache_ttl = 60.0
    svc._balance_cache = {"time": 0, "data": None}
    svc._abstraction_cache = {"time": 0, "mode": None}
    svc.info = MagicMock()
    svc.info.user_state.return_value = {
        "marginSummary": {"accountValue": "100", "totalMarginUsed": "10"},
        "withdrawable": "50",
    }
    svc.info.spot_user_state.return_value = {"balances": [{"coin": "USDC", "total": "0", "hold": "0"}]}
    monkeypatch.setattr("app.services.hyperliquid_service.config.HL_ACCOUNT_ADDRESS", "0xabc")
    monkeypatch.setattr(
        "app.services.hyperliquid_service.HyperliquidService._get_account_abstraction_mode",
        lambda _s, _a, **_: "default",
    )
    t = {"now": 1000.0}
    monkeypatch.setattr("app.services.hyperliquid_service.time.time", lambda: t["now"])

    HyperliquidService.get_account_balance.__wrapped__(svc)
    t["now"] = 1040.0
    HyperliquidService.get_account_balance.__wrapped__(svc)
    assert svc.info.user_state.call_count == 1


def test_force_refresh_failure_does_not_return_stale_cache(monkeypatch):
    svc = _balance_service(monkeypatch)
    out = HyperliquidService.get_account_balance.__wrapped__(svc, force_refresh=True)
    assert out["status"] == "error"
    assert out["total_equity"] == 0
    assert svc.info.user_state.call_count >= 1


def test_abstraction_cache_reused_one_hour(monkeypatch):
    svc = object.__new__(HyperliquidService)
    svc.log = MagicMock()
    svc._cache_ttl = 60.0
    svc._balance_cache = {"time": 0, "data": None}
    svc._abstraction_cache = {"time": 2000.0, "mode": "unifiedAccount"}
    svc.info = MagicMock()
    svc.info.user_state.return_value = {
        "marginSummary": {"accountValue": "0", "totalMarginUsed": "0"},
        "withdrawable": "0",
    }
    svc.info.spot_user_state.return_value = {
        "balances": [{"coin": "USDC", "total": "100", "hold": "0"}]
    }
    monkeypatch.setattr("app.services.hyperliquid_service.config.HL_ACCOUNT_ADDRESS", "0xabc")
    monkeypatch.setattr("app.services.hyperliquid_service.time.time", lambda: 3000.0)
    out = HyperliquidService.get_account_balance.__wrapped__(svc)
    assert out["account_abstraction_mode"] == "unifiedAccount"
    svc.info.post.assert_not_called()
