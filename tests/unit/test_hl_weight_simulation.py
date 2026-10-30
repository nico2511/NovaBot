"""Simulate A3-only per-minute /info weight (<400/min)."""
from __future__ import annotations

import pandas as pd

from strategies.engine import StrategyEngine
from app.utils.rate_limiter import estimate_info_weight


def test_a3_only_required_timeframes_exclude_extra_tfs():
    engine = StrategyEngine()
    engine.config = {
        "a3_ema_trend_4h": {"enabled": True, "type": "always_active", "timeframe": "4h"},
    }
    tfs = engine.required_timeframes()
    assert tfs == {"15m", "4h"}
    assert "5m" not in tfs and "1m" not in tfs and "1h" not in tfs


def test_a3_only_one_minute_weight_under_400():
    symbols = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK"]
    minute_weight = 0
    for sym in symbols:
        end = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
        start = end - 300 * 900 * 1000
        minute_weight += estimate_info_weight(
            {
                "type": "candleSnapshot",
                "interval": "15m",
                "startTime": start,
                "endTime": end,
            }
        )
    end = int(pd.Timestamp.now(tz="UTC").timestamp() * 1000)
    start = end - 400 * 14400 * 1000
    minute_weight += 8 // 5 * estimate_info_weight(
        {
            "type": "candleSnapshot",
            "interval": "4h",
            "startTime": start,
            "endTime": end,
        }
    )
    minute_weight += estimate_info_weight({"type": "clearinghouseState"})
    minute_weight += estimate_info_weight({"type": "spotClearinghouseState"})
    assert minute_weight < 400
