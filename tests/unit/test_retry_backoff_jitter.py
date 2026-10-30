"""backoff_delay jitter bounds and get_candles total sleep cap."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.utils.retry_decorator import backoff_delay
from app.services.hyperliquid_service import HyperliquidService


def test_backoff_delay_jitter_within_bounds(monkeypatch):
    monkeypatch.setattr("app.utils.retry_decorator.random.random", lambda: 0.0)
    d = backoff_delay(0, base=1.0, cap=4.0, rate_limited=True, jitter=True)
    assert 1.5 <= d <= 2.5
    monkeypatch.setattr("app.utils.retry_decorator.random.random", lambda: 1.0)
    d2 = backoff_delay(1, base=1.0, cap=4.0, rate_limited=False, jitter=True)
    assert 1.875 <= d2 <= 3.125


def test_get_candles_429_total_sleep_under_8s():
    svc = object.__new__(HyperliquidService)
    svc.info = MagicMock()
    svc._meta_cache = {}
    svc.log = MagicMock()
    svc.log_callback = None
    svc.get_canonical_symbol = lambda s: s
    svc.info.candles_snapshot.side_effect = Exception((429, None, "null", None, {}))
    sleeps = []

    with patch("app.services.hyperliquid_service.time.sleep", side_effect=lambda s: sleeps.append(s)):
        df = svc.get_candles("ETH", "15m", 10)

    assert df.empty
    assert sum(sleeps) <= 8.0 + 1e-6
