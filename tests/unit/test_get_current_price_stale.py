from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from app.core.candle_timing import current_bar_open
from app.services.hyperliquid_service import HyperliquidService


def _candle(ts_ms: int, px: float) -> dict:
    return {"t": ts_ms, "o": px, "h": px, "l": px, "c": px, "v": 1}


def test_get_current_price_returns_zero_on_429_without_seeding_stale():
    svc = object.__new__(HyperliquidService)
    svc.log = MagicMock()
    svc.get_canonical_symbol = lambda s: s.upper()
    svc._fetch_rest_mid = MagicMock(return_value=0.0)
    svc._log_ws_cache_miss_once = MagicMock()

    ws = MagicMock()
    ws.get_price.return_value = None
    ws.seed_price = MagicMock()
    svc.ws_manager = ws

    bar = current_bar_open("1m")
    t_bar = int(bar.timestamp() * 1000)
    t0 = int((bar - pd.Timedelta(minutes=50)).timestamp() * 1000)
    svc.info = MagicMock()
    svc.info.candles_snapshot.side_effect = [
        [_candle(t0 + i * 60_000, 111.0) for i in range(50)] + [_candle(t_bar, 111.0)],
        Exception((429, None, "null", None, {})),
    ]

    with patch("app.services.hyperliquid_service.time.sleep"):
        svc.get_candles("ETH", "1m", 100)
        px = svc.get_current_price("ETH")

    assert px == 0.0
    ws.seed_price.assert_not_called()
