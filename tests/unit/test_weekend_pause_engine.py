"""Engine respects weekend pause for cascade strategies."""
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd

from strategies.engine import StrategyEngine

PARIS = ZoneInfo("Europe/Paris")


class _StubRocket:
    name = "rocket"
    config = {"params": {"allow_longs": True, "allow_shorts": False, "skip_bb_anti_chase": True}}
    last_rejection_reason = None

    def generate_signal(self, df, extra_data=None):
        return {"signal": "BUY", "price": float(df["close"].iloc[-1]), "sl": 1.0, "tp": 2.0}


class _StubWaterfall:
    name = "waterfall"
    config = {"params": {"allow_longs": False, "allow_shorts": True, "skip_bb_anti_chase": True}}
    last_rejection_reason = None

    def generate_signal(self, df, extra_data=None):
        return {"signal": "SELL", "price": float(df["close"].iloc[-1]), "sl": 2.0, "tp": 1.0}


class _StubSupertrend:
    name = "supertrend"
    config = {"params": {"allow_longs": True, "allow_shorts": True, "skip_bb_anti_chase": True}}
    last_rejection_reason = None

    def generate_signal(self, df, extra_data=None):
        return {"signal": "BUY", "price": float(df["close"].iloc[-1]), "sl": 1.0, "tp": 2.0}


def _engine_df():
    n = 120
    idx = pd.date_range("2026-01-01", periods=n, freq="15min", tz="UTC")
    close = pd.Series(100.0 + (pd.Series(range(n)) * 0.05), index=idx)
    return pd.DataFrame(
        {
            "open": close - 0.01,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": 1000.0,
        },
        index=idx,
    )


def test_engine_skips_rocket_waterfall_during_weekend_pause(monkeypatch):
    engine = StrategyEngine()
    engine.strategies = {
        "rocket": _StubRocket(),
        "waterfall": _StubWaterfall(),
        "supertrend": _StubSupertrend(),
    }
    engine.config = {
        "weekend_pause": {
            "enabled": True,
            "timezone": "Europe/Paris",
            "start_weekday": 5,
            "start_hour": 6,
            "end_weekday": 0,
            "end_hour": 6,
            "strategies": ["rocket", "waterfall"],
        },
        "rocket": {"enabled": True, "type": "trend"},
        "waterfall": {"enabled": True, "type": "trend"},
        "supertrend": {"enabled": True, "type": "trend"},
    }

    sunday = datetime(2026, 8, 23, 10, 0, tzinfo=PARIS)
    monkeypatch.setattr(
        "app.core.weekend_pause.datetime",
        type(
            "FixedNow",
            (),
            {"now": staticmethod(lambda tz=None: sunday)},
        ),
    )

    results = engine.analyze(_engine_df(), extra_data={"symbol": "BTC"})
    active = results.get("strategies") or []
    assert "rocket" not in active
    assert "waterfall" not in active
    names = [s["strategy"] for s in results.get("signals") or []]
    assert "rocket" not in names
    assert "waterfall" not in names
