"""Retry decorator must not retry business rejects (insufficient margin, etc.)."""
from __future__ import annotations

import pytest

from app.utils.retry_decorator import (
    _is_retryable_error,
    exponential_backoff,
)


def test_insufficient_margin_is_not_retryable():
    assert _is_retryable_error(Exception("Insufficient margin")) is False


def test_429_and_504_are_retryable():
    assert _is_retryable_error(Exception((429, None, "null"))) is True
    assert _is_retryable_error(Exception((504, "<!DOCTYPE HTML"))) is True
    assert _is_retryable_error(Exception("gateway timeout")) is True


def test_decorator_does_not_retry_business_error():
    calls = {"n": 0}

    @exponential_backoff(max_retries=3, base_delay=0.01, jitter=False)
    def boom():
        calls["n"] += 1
        raise Exception("Insufficient margin")

    with pytest.raises(Exception, match="Insufficient margin"):
        boom()
    assert calls["n"] == 1


def test_decorator_retries_504(monkeypatch):
    calls = {"n": 0}

    @exponential_backoff(max_retries=2, base_delay=0.01, jitter=False)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise Exception((504, "timeout"))
        return "ok"

    monkeypatch.setattr("app.utils.retry_decorator.time.sleep", lambda *_a, **_k: None)
    assert flaky() == "ok"
    assert calls["n"] == 3
