"""Unit tests for HyperliquidService.get_candles resilience."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.services.hyperliquid_service import HyperliquidService


def _candle(ts_ms: int, px: float = 100.0) -> dict:
    return {"t": ts_ms, "o": px, "h": px + 1, "l": px - 1, "c": px, "v": 10}


@pytest.fixture
def service():
    svc = object.__new__(HyperliquidService)
    svc.info = MagicMock()
    svc._meta_cache = {"universe": [{"name": "BCH", "szDecimals": 2}, {"name": "kPEPE", "szDecimals": 0}]}
    svc.log_callback = None
    svc.ws_manager = None
    return svc


def test_get_candles_canonicalizes_alias(service):
    """PEPE must resolve to kPEPE before the snapshot call."""
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    service.info.candles_snapshot.return_value = [_candle(now_ms - 60_000), _candle(now_ms)]

    df = service.get_candles("PEPE", "1m", 2)

    assert not df.empty
    called_symbol = service.info.candles_snapshot.call_args[0][0]
    assert called_symbol == "kPEPE"


def test_get_candles_retries_empty_then_succeeds(service):
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    service.info.candles_snapshot.side_effect = [
        [],
        [_candle(now_ms - 60_000), _candle(now_ms)],
    ]

    with patch("app.services.hyperliquid_service.time.sleep"):
        df = service.get_candles("BCH", "1m", 2)

    assert not df.empty
    assert service.info.candles_snapshot.call_count == 2
    assert {"open", "high", "low", "close"}.issubset(df.columns)


def test_get_candles_retries_429_tuple(service):
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    service.info.candles_snapshot.side_effect = [
        Exception((429, None, "null", None, {})),
        [_candle(now_ms)],
    ]

    with patch("app.services.hyperliquid_service.time.sleep"):
        df = service.get_candles("BCH", "1m", 1)

    assert not df.empty
    assert service.info.candles_snapshot.call_count == 2


def test_get_candles_returns_empty_after_exhausted_retries(service):
    service.info.candles_snapshot.return_value = []

    with patch("app.services.hyperliquid_service.time.sleep"):
        df = service.get_candles("BCH", "1m", 10)

    assert df.empty
    assert service.info.candles_snapshot.call_count == 3
