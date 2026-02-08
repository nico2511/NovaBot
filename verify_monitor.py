import os
import sys
import pandas as pd
import numpy as np

# Add strategies path
sys.path.append(os.path.abspath('.'))

def test_monitor():
    from app.core.config import config
    from strategies.engine import StrategyEngine
    
    # Mock bot context
    class MockBot:
        def __init__(self):
            self.active_symbol = "BTC"
            self.latest_data = pd.DataFrame({
                'close': [100.0] * 300,
                'high': [101.0] * 300,
                'low': [99.0] * 300,
                'open': [100.0] * 300,
                'volume': [1000.0] * 300
            })
            
    bot = MockBot()
    engine = StrategyEngine(bot)
    
    # Mock extra_data
    extra_data = {
        "1m": pd.DataFrame({
            'close': [100.5] * 10,
            'high': [101.0] * 10,
            'low': [100.0] * 10,
            'open': [100.5] * 10,
            'volume': [100.0] * 10
        })
    }
    
    print(f"{'Strategy':<25} | {'Bias':<10} | {'Score':<5} | {'MTF Status'}")
    print("-" * 60)
    
    for name, strat in engine.strategies.items():
        try:
            res = strat.calculate_progress(bot.latest_data, extra_data=extra_data)
            bias = res.get("bias", "MISSING")
            score = res.get("score", 0)
            
            # Check MTF Detail in Smart Trend/Sniper Trend
            mtf_detail = "N/A"
            if name in ["smart_trend", "sniper_trend"]:
                for stage in res.get("stages", []):
                    if "1m" in stage.get("name", ""):
                        if "100.50" in stage.get("details", ""):
                            mtf_detail = "FIXED"
                        else:
                            mtf_detail = "NO_DATA"
            
            print(f"{name:<25} | {bias:<10} | {score:<5} | {mtf_detail}")
        except Exception as e:
            import traceback
            print(f"{name:<25} | ERROR: {e}")
            traceback.print_exc()

if __name__ == "__main__":
    test_monitor()
