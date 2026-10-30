from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.core.candle_timing import current_bar_open
from app.services.hyperliquid_service import HyperliquidService


def _candle(ts_ms: int, px: float = 100.0) -> dict:
    return {"t": ts_ms, "o": px, "h": px + 1, "l": px - 1, "c": px, "v": 10}


def _service():
    svc = object.__new__(HyperliquidService)
    svc.info = MagicMock()
    svc._meta_cache = {}
    svc.log = MagicMock()
    svc.log_callback = None
    svc.get_canonical_symbol = lambda s: s.upper()
    return svc


def test_cache_hit_same_bar_single_network_call():
    svc = _service()
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    svc.info.candles_snapshot.return_value = [_candle(now_ms - 3_600_000), _candle(now_ms)]

    with patch("app.services.hyperliquid_service.time.sleep"):
        df1 = svc.get_candles("ETH", "4h", 2)
        df2 = svc.get_candles("ETH", "4h", 2)

    assert not df1.empty and not df2.empty
    assert svc.info.candles_snapshot.call_count == 1


def test_cache_miss_after_bar_boundary():
    svc = _service()
    t0 = current_bar_open("4h")
    ts_ms = int(t0.timestamp() * 1000) + 3_600_000
    svc.info.candles_snapshot.return_value = [_candle(ts_ms - 3_600_000), _candle(ts_ms)]

    with patch("app.services.hyperliquid_service.time.sleep"):
        svc.get_candles("ETH", "4h", 2)
        t1 = t0 + pd.Timedelta(hours=4)
        with patch(
            "app.core.candle_timing.current_bar_open",
            return_value=t1,
        ):
            svc.get_candles("ETH", "4h", 2)

    assert svc.info.candles_snapshot.call_count == 2


def test_returns_copy_not_mutating_cache():
    svc = _service()
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    svc.info.candles_snapshot.return_value = [_candle(now_ms - 60_000), _candle(now_ms)]
    with patch("app.services.hyperliquid_service.time.sleep"):
        df = svc.get_candles("BCH", "1m", 2)
    df["close"] = 0
    with patch("app.services.hyperliquid_service.time.sleep"):
        df2 = svc.get_candles("BCH", "1m", 2)
    assert df2["close"].iloc[-1] != 0


def test_empty_response_not_cached():
    svc = _service()
    svc.info.candles_snapshot.return_value = []
    with patch("app.services.hyperliquid_service.time.sleep"):
        df = svc.get_candles("BCH", "1m", 2)
    assert df.empty
    svc.info.candles_snapshot.return_value = [_candle(int(pd.Timestamp.now(tz="UTC").timestamp() * 1000))]
    with patch("app.services.hyperliquid_service.time.sleep"):
        svc.get_candles("BCH", "1m", 1)
    assert svc.info.candles_snapshot.call_count >= 4


def test_higher_limit_triggers_refetch():
    svc = _service()
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    svc.info.candles_snapshot.return_value = [_candle(now_ms - i * 60_000) for i in range(5)]
    with patch("app.services.hyperliquid_service.time.sleep"):
        svc.get_candles("BCH", "1m", 2)
        svc.get_candles("BCH", "1m", 5)
    assert svc.info.candles_snapshot.call_count == 2
