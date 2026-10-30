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
    svc.log = MagicMock()
    svc.get_canonical_symbol = lambda s: s.upper()
    return svc


def test_forming_ttl_expires(monkeypatch):
    svc = _service()
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    svc.info.candles_snapshot.return_value = [_candle(now_ms - 60_000), _candle(now_ms)]
    mono = {"t": 1000.0}
    monkeypatch.setattr("app.services.hyperliquid_service.time.monotonic", lambda: mono["t"])
    with patch("app.services.hyperliquid_service.time.sleep"):
        svc.get_candles("ETH", "1m", 2)
    mono["t"] = 1011.0
    with patch("app.services.hyperliquid_service.time.sleep"):
        svc.get_candles("ETH", "1m", 2)
    assert svc.info.candles_snapshot.call_count == 2


def test_require_forming_tail_misaligned_returns_empty():
    svc = _service()
    bar = current_bar_open("4h")
    stale = int((bar - pd.Timedelta(hours=4)).timestamp() * 1000)
    svc.info.candles_snapshot.return_value = [_candle(stale, 1.0)]
    with patch("app.services.hyperliquid_service.time.sleep"):
        df = svc.get_candles("ETH", "4h", 1, require_forming_tail=True)
    assert df.empty


def test_stale_fallback_on_429_non_strict():
    svc = _service()
    bar = current_bar_open("15m")
    ts = int(bar.timestamp() * 1000)
    svc.info.candles_snapshot.return_value = [_candle(ts - 900_000, 1.0), _candle(ts, 2.0)]
    with patch("app.services.hyperliquid_service.time.sleep"):
        svc.get_candles("ETH", "15m", 2)
    svc.info.candles_snapshot.side_effect = Exception((429, None, "null", None, {}))
    with patch("app.services.hyperliquid_service.time.sleep"):
        df = svc.get_candles("ETH", "15m", 2)
    assert not df.empty
    assert float(df["close"].iloc[-1]) == pytest.approx(2.0)


def test_smaller_limit_served_from_cache():
    svc = _service()
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    svc.info.candles_snapshot.return_value = [_candle(now_ms - i * 60_000) for i in range(10)]
    with patch("app.services.hyperliquid_service.time.sleep"):
        svc.get_candles("ETH", "1m", 10)
        short = svc.get_candles("ETH", "1m", 3)
    assert len(short) == 3
    assert svc.info.candles_snapshot.call_count == 1
