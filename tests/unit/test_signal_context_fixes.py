"""Regression tests for signal timestamp, EMA, and MACD context fixes."""
import numpy as np
import pandas as pd

from app.core.bot import BotContext
from app.services.indicators import Indicators, ta
from app.utils.ai_context import normalize_strategy_context
from strategies.engine import StrategyEngine


class _SignalStrategy:
    def __init__(self, name="SignalProbe"):
        self.name = name
        self.config = {"params": {"allow_longs": True, "skip_bb_anti_chase": True}}
        self.last_rejection_reason = None

    def generate_signal(self, df, extra_data=None):
        return {"signal": "BUY", "price": float(df["close"].iloc[-2])}


def _ohlcv_df(n=100, freq="15min"):
    dates = pd.date_range("2026-01-01", periods=n, freq=freq, tz="UTC")
    close = np.linspace(50.0, 55.0, n) + np.sin(np.linspace(0, 6, n)) * 0.2
    return pd.DataFrame(
        {
            "open": close - 0.05,
            "high": close + 0.15,
            "low": close - 0.15,
            "close": close,
            "volume": np.full(n, 1000.0),
        },
        index=dates,
    )


def test_engine_signal_timestamp_uses_confirmed_candle():
    engine = StrategyEngine()
    strat = _SignalStrategy()
    engine.strategies = {"SignalProbe": strat}
    engine.config = {
        "market_regime": {"adx_threshold": 25},
        "SignalProbe": {"enabled": True, "type": "always_active", "timeframe": "15m"},
    }
    df = _ohlcv_df()
    result = engine.analyze(df, extra_data={"symbol": "LTC"})
    signals = result.get("signals") or []
    assert signals, "expected a probe signal"
    assert signals[0]["timestamp"] == str(df.index[-2])
    assert signals[0]["timestamp"] != str(df.index[-1])


def test_engine_signal_timestamp_uses_strategy_timeframe():
    engine = StrategyEngine()
    strat = _SignalStrategy(name="TrendProbe")
    engine.strategies = {"TrendProbe": strat}
    engine.config = {
        "market_regime": {"adx_threshold": 25},
        "TrendProbe": {"enabled": True, "type": "always_active", "timeframe": "1h"},
    }
    df_15m = _ohlcv_df(freq="15min")
    df_1h = _ohlcv_df(n=80, freq="1h")
    result = engine.analyze(
        df_15m,
        extra_data={"symbol": "LTC", "1h": df_1h},
    )
    signals = result.get("signals") or []
    assert signals, "expected a probe signal"
    assert signals[0]["timestamp"] == str(df_1h.index[-2])
    assert signals[0]["timestamp"] != str(df_15m.index[-2])


def test_normalize_strategy_context_includes_ema_values():
    raw = {
        "strategy_timeframe": "15m",
        "current_price": 53.646,
        "ema_20": 53.14,
        "ema_50": 52.70,
        "macd_hist": 0.0198,
    }
    out = normalize_strategy_context(raw)
    assert out["ema_20"] == 53.14
    assert out["ema_50"] == 52.70
    assert out["macd_hist"] == 0.0198


def test_prepare_ai_context_ema_and_macd_on_confirmed_bar():
    df = _ohlcv_df()
    ema_20 = ta.ema(df["close"], length=20)
    ema_50 = ta.ema(df["close"], length=50)
    df = df.copy()
    df["EMA_20"] = ema_20
    df["EMA_50"] = ema_50
    df["RSI_14"] = ta.rsi(df["close"], length=14)

    bot = BotContext.__new__(BotContext)
    bot.active_symbol = "LTC"
    ctx = bot._prepare_ai_context(df=df, timeframe="15m")

    idx = -2
    macd_df = Indicators.macd(df["close"])

    assert ctx["ema_20"] == float(ema_20.iloc[idx])
    assert ctx["ema_50"] == float(ema_50.iloc[idx])
    assert abs(ctx["macd_hist"] - float(macd_df["MACDh"].iloc[idx])) < 1e-4

    snap = normalize_strategy_context(ctx)
    assert snap["ema_20"] == ctx["ema_20"]
    assert snap["ema_50"] == ctx["ema_50"]
