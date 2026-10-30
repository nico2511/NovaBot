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


def test_short_fetch_merges_fresh_tail_same_bar():
    svc = _service()
    bar = current_bar_open("1m")
    t_new = int(bar.timestamp() * 1000)
    t_old = int((bar - pd.Timedelta(minutes=4)).timestamp() * 1000)
    svc.info.candles_snapshot.side_effect = [
        [_candle(t_old + i * 60_000, px=10 + i) for i in range(4)]
        + [_candle(t_new, px=14.0)],
        [_candle(t_new, px=99.0)],
    ]
    with patch("app.services.hyperliquid_service.time.sleep"):
        svc.get_candles("ETH", "1m", 5)
        svc.get_candles("ETH", "1m", 1)
        df_cached = svc.get_candles("ETH", "1m", 5)
    assert float(df_cached["close"].iloc[-1]) == pytest.approx(99.0)


def test_short_fetch_after_long_uses_new_bar_on_boundary():
    svc = _service()
    bar0 = current_bar_open("1m")
    t0 = int(bar0.timestamp() * 1000)
    svc.info.candles_snapshot.return_value = [_candle(t0 - 60_000, 1.0), _candle(t0, 2.0)]
    with patch("app.services.hyperliquid_service.time.sleep"):
        svc.get_candles("ETH", "1m", 2)
    bar1 = bar0 + pd.Timedelta(minutes=1)
    t1 = int(bar1.timestamp() * 1000)
    svc.info.candles_snapshot.return_value = [_candle(t1, 77.0)]
    with patch("app.services.hyperliquid_service.time.sleep"):
        with patch("app.core.candle_timing.current_bar_open", return_value=bar1):
            svc.get_candles("ETH", "1m", 1)
            df = svc.get_candles("ETH", "1m", 2)
    assert float(df["close"].iloc[-1]) == pytest.approx(77.0)


def test_get_current_price_1m1_after_1m100_is_fresh():
    svc = _service()
    svc.ws_manager = None
    svc._fetch_rest_mid = MagicMock(return_value=0.0)
    bar = current_bar_open("1m")
    t_bar = int(bar.timestamp() * 1000)
    t0 = int((bar - pd.Timedelta(minutes=99)).timestamp() * 1000)
    svc.info.candles_snapshot.side_effect = [
        [_candle(t0 + i * 60_000, px=1.0) for i in range(99)] + [_candle(t_bar, px=1.0)],
        [_candle(t_bar, px=555.0)],
    ]
    with patch("app.services.hyperliquid_service.time.sleep"):
        svc.get_candles("ETH", "1m", 100)
        px = svc.get_current_price("ETH")
    assert px == pytest.approx(555.0)


def test_higher_limit_triggers_refetch():
    svc = _service()
    now_ms = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    svc.info.candles_snapshot.return_value = [_candle(now_ms - i * 60_000) for i in range(5)]
    with patch("app.services.hyperliquid_service.time.sleep"):
        svc.get_candles("BCH", "1m", 2)
        svc.get_candles("BCH", "1m", 5)
    assert svc.info.candles_snapshot.call_count == 2
