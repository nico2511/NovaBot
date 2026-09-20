"""LAN bind auto-requires API key; compare_digest must not 500 on length mismatch."""
from __future__ import annotations

from unittest.mock import patch

from app.core.config import bind_is_loopback, resolve_api_key_required


def test_loopback_hosts():
    assert bind_is_loopback("127.0.0.1") is True
    assert bind_is_loopback("localhost") is True
    assert bind_is_loopback("::1") is True
    assert bind_is_loopback("0.0.0.0") is False
    assert bind_is_loopback("10.0.0.5") is False


def test_api_key_required_auto_on_lan(monkeypatch):
    monkeypatch.delenv("API_KEY_REQUIRED", raising=False)
    assert resolve_api_key_required("0.0.0.0") is True
    assert resolve_api_key_required("127.0.0.1") is False


def test_api_key_required_explicit_false_honored(monkeypatch):
    monkeypatch.setenv("API_KEY_REQUIRED", "false")
    assert resolve_api_key_required("0.0.0.0") is False


def test_auth_length_mismatch_is_401():
    from fastapi import HTTPException
    from app.api import auth

    with patch.object(auth.config, "API_KEY_REQUIRED", True), patch.object(
        auth.config, "API_KEY", "long-secret-key"
    ):
        try:
            auth.require_api_key(x_api_key="x")
            raise AssertionError("should have raised")
        except HTTPException as exc:
            assert exc.status_code == 401
