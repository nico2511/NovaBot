from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.hyperliquid_service import HyperliquidService


def _balance_service(monkeypatch):
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
        lambda _s, _a: "default",
    )
    return svc


def test_balance_cached_within_ttl(monkeypatch):
    svc = _balance_service(monkeypatch)
    t = {"now": 1000.0}
    monkeypatch.setattr("app.services.hyperliquid_service.time.time", lambda: t["now"])

    HyperliquidService.get_account_balance.__wrapped__(svc)
    t["now"] = 1040.0
    HyperliquidService.get_account_balance.__wrapped__(svc)
    assert svc.info.user_state.call_count == 1


def test_force_refresh_always_calls(monkeypatch):
    svc = _balance_service(monkeypatch)
    HyperliquidService.get_account_balance.__wrapped__(svc)
    HyperliquidService.get_account_balance.__wrapped__(svc, force_refresh=True)
    assert svc.info.user_state.call_count == 2
