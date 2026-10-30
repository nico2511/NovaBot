from __future__ import annotations

from app.services.hyperliquid_service import HyperliquidService


def test_safe_err_strips_http_headers_from_client_error():
    svc = object.__new__(HyperliquidService)
    err = Exception((429, None, "null", None, {"x-amz-cf-id": "secret-header"}))
    text = svc._safe_err(err)
    assert "x-amz" not in text.lower()
    assert "secret-header" not in text


def test_open_orders_log_uses_safe_err(monkeypatch):
    svc = object.__new__(HyperliquidService)
    messages = []
    svc.log = lambda msg, level="INFO": messages.append(msg)
    svc.info = type(
        "I",
        (),
        {"open_orders": lambda _a: (_ for _ in ()).throw(Exception((429, None, "hdr", None, {})))},
    )()
    svc._open_orders_cache = {"time": 0, "data": None}
    monkeypatch.setattr("app.services.hyperliquid_service.config.HL_ACCOUNT_ADDRESS", "0xabc")
    svc.get_open_orders()
    joined = " ".join(messages)
    assert "hdr" not in joined
