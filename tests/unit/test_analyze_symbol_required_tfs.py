from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from app.core.bot import BotContext


def test_analyze_symbol_fetches_only_required_timeframes():
    bot = object.__new__(BotContext)
    bot.strategy_engine = MagicMock()
    bot.strategy_engine.required_timeframes.return_value = {"15m", "4h"}
    bot.strategy_engine.analyze.return_value = {
        "regime": "UNKNOWN",
        "regime_skipped": True,
        "adx": 0,
        "rsi": 0,
        "ema_20": 0,
        "ema_50": 0,
        "ema_9": 0,
        "bb_upper": 0,
        "bb_lower": 0,
        "bb_width": 0,
        "volume_ratio": 100,
        "current_price": 1.0,
        "strategies": [],
    }
    bot._restore_strategy_sticky = MagicMock()
    bot._save_strategy_sticky = MagicMock()
    bot._strategies_for_analysis = MagicMock(return_value=None)
    bot.latest_data_map = {}

    df = pd.DataFrame(
        {
            "open": [1.0, 2.0],
            "high": [1.1, 2.1],
            "low": [0.9, 1.9],
            "close": [1.0, 2.0],
            "volume": [10, 10],
        },
        index=pd.date_range("2024-01-01", periods=2, freq="15min", tz="UTC"),
    )
    hl = MagicMock()
    hl.get_candles.return_value = df
    hl.get_funding_rate.return_value = 0.0

    with patch("app.core.bot.hyperliquid_service", hl):
        out = bot._analyze_symbol_market("ETH")

    assert out["ok"] is True
    called = {c.kwargs.get("interval") or c.args[1] for c in hl.get_candles.call_args_list}
    assert called <= {"15m", "4h"}
