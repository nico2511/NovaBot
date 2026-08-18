import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock
from strategies.engine import StrategyEngine

class CrashingStrategy:
    def __init__(self, name="CrashingStrategy"):
        self.name = name
        self.config = {"params": {}}
        self.enabled = True

    def generate_signal(self, df, extra_data=None):
        raise ValueError("Simulated strategy crash")

class HealthyStrategy:
    def __init__(self, name="HealthyStrategy"):
        self.name = name
        self.config = {"params": {}}
        self.enabled = True

    def generate_signal(self, df, extra_data=None):
        # Return a BUY signal
        return {"signal": "BUY", "price": 90.0}

def test_engine_isolates_crashing_strategy():
    # Setup Engine
    engine = StrategyEngine()
    
    # Mock strategies
    strat_crash = CrashingStrategy()
    strat_ok = HealthyStrategy()
    
    engine.strategies = {
        "CrashingStrategy": strat_crash,
        "HealthyStrategy": strat_ok
    }
    
    # Mock config to include our test strategies
    # engine.analyze iterates over self.config items
    engine.config = {
        "market_regime": {"adx_threshold": 25},
        "CrashingStrategy": {"enabled": True, "type": "always_active", "allow_longs": True},
        "HealthyStrategy": {"enabled": True, "type": "always_active", "allow_longs": True}
    }
    
    # Simple DF with enough data for indicators
    # We need high/low/close for ADX/BB
    dates = pd.date_range(start="2023-01-01", periods=100, freq="15min")
    # Use a price that drops at the end to avoid Bollinger Band "Overbought" rejection on BUY
    close_prices = [100.0] * 80 + list(np.linspace(100, 90, 20)) 
    
    df = pd.DataFrame({
        "close": close_prices,
        "high": [p + 0.5 for p in close_prices],
        "low": [p - 0.5 for p in close_prices],
        "open": close_prices,
        "volume": [1000] * 100
    }, index=dates)
    
    # Act
    results = engine.analyze(df, extra_data={"symbol": "BTC"})
    
    # Assert
    signals = results.get("signals", [])
    print(f"DEBUG: Results regime: {results.get('regime')}")
    print(f"DEBUG: Signals: {signals}")

    # HealthyStrategy should have produced a signal
    found_healthy = any(s["strategy"] == "HealthyStrategy" for s in signals)
    if not found_healthy:
        print("❌ HealthyStrategy signal NOT found in signals")
        # Try to see if it was rejected
    
    # CrashingStrategy should NOT be in signals and should NOT have crashed the engine
    found_crash = any(s["strategy"] == "CrashingStrategy" for s in signals)
    
    assert found_healthy, "HealthyStrategy signal should be found and NOT rejected by filters"
    assert not found_crash, "CrashingStrategy should not produce a signal (it crashed)"
    assert results["regime"] is not None
    print("✅ Engine correctly isolated the crashing strategy")


def _engine_df():
    dates = pd.date_range(start="2023-01-01", periods=100, freq="15min")
    close_prices = [100.0] * 80 + list(np.linspace(100, 90, 20))
    return pd.DataFrame(
        {
            "close": close_prices,
            "high": [p + 0.5 for p in close_prices],
            "low": [p - 0.5 for p in close_prices],
            "open": close_prices,
            "volume": [1000] * 100,
        },
        index=dates,
    )


def test_engine_only_strategies_skips_other_lanes():
    engine = StrategyEngine()
    ok = HealthyStrategy()
    skipped = HealthyStrategy()
    skipped.name = "SkipMe"
    engine.strategies = {"HealthyStrategy": ok, "SkipMe": skipped}
    engine.config = {
        "market_regime": {"adx_threshold": 25},
        "HealthyStrategy": {"enabled": True, "type": "always_active"},
        "SkipMe": {"enabled": True, "type": "always_active"},
    }
    results = engine.analyze(
        _engine_df(),
        extra_data={"symbol": "XRP", "only_strategies": ["HealthyStrategy"]},
    )
    names = [s["strategy"] for s in results.get("signals", [])]
    assert "HealthyStrategy" in names
    assert "SkipMe" not in names
    assert all(r.get("strategy") != "SkipMe" for r in results.get("rejections") or [])

if __name__ == "__main__":
    try:
        test_engine_isolates_crashing_strategy()
    except Exception as e:
        import traceback
        print(f"Test FATAL error: {e}")
        traceback.print_exc()
        exit(1)
