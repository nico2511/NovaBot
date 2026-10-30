from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pandas as pd

from app.core.bot import BotContext
from app.utils.rate_limiter import hl_info_limiter


def test_manage_trade_called_when_limiter_bucket_empty():
    hl_info_limiter.reset()
    hl_info_limiter.tokens = 0
    hl_info_limiter.note_rate_limited()

    trade = {"symbol": "ETH", "strategy": "a3_ema_trend_4h", "side": "BUY"}
    bot = object.__new__(BotContext)
    bot.trading_enabled = True
    bot.trade_lock = threading.Lock()
    bot.active_trades = {"ETH": trade}
    bot._last_thesis_check = {}
    bot._thesis_check_interval_sec = 9999
    bot.add_log = MagicMock()

    strat = MagicMock()
    strat.supports_trade_thesis.return_value = False
    strat.get_thesis_timeframe.return_value = "4h"
    strat.manage_trade.return_value = None
    strat.name = "a3_ema_trend_4h"

    bot.strategy_engine = MagicMock()
    bot.strategy_engine.strategies = {"a3_ema_trend_4h": strat}

    df = pd.DataFrame({"close": [1.0]})
    hl = MagicMock()
    hl.get_current_price.return_value = 100.0
    hl.get_candles.return_value = df

    with patch("app.core.bot.hyperliquid_service", hl):
        bot._manage_all_trades()

    strat.manage_trade.assert_called_once()
    assert hl.get_candles.call_args.kwargs.get("priority") == "high"
    assert not hl.get_candles.return_value.empty
