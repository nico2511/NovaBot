from __future__ import annotations

from unittest.mock import patch

import numpy as np
import pandas as pd

from strategies.engine import StrategyEngine


def _df():
    dates = pd.date_range(start="2023-01-01", periods=120, freq="15min")
    close = [100.0] * 100 + list(np.linspace(100, 110, 20))
    return pd.DataFrame(
        {
            "close": close,
            "high": [p + 0.5 for p in close],
            "low": [p - 0.5 for p in close],
            "open": close,
            "volume": [1000] * 120,
        },
        index=dates,
    )


def test_a3_only_skips_regime_and_adx():
    engine = StrategyEngine()
    engine.config = {
        "a3_ema_trend_4h": {"enabled": True, "type": "always_active", "timeframe": "4h"},
        "supertrend": {"enabled": False, "type": "trend"},
    }
    with patch("strategies.engine.ta.adx") as adx_mock:
        out = engine.analyze(_df(), extra_data={"symbol": "BTC", "4h": _df()})
    assert out.get("regime_skipped") is True
    assert out["regime"] == "UNKNOWN"
    adx_mock.assert_not_called()


def test_unknown_strategy_still_requires_regime():
    engine = StrategyEngine()
    engine.config = {
        "ProbeX": {"enabled": True, "type": "always_active", "timeframe": "15m"},
    }
    engine.strategies = {}
    assert engine.regime_required() is True
