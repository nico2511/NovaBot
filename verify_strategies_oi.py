
import pandas as pd
import numpy as np
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from strategies.elastic_reversion import ElasticReversionStrategy
from strategies.elastic_nibbler import ElasticNibblerStrategy
from strategies.liquidity_lightning import LiquidityLightning
from strategies.institutional_scalp import InstitutionalScalp
from strategies.bollinger_bounce import BollingerBounceStrategy
from strategies.fibo_pullback import StrategyFiboPullback
from strategies.smart_trend import StrategySmartTrend

def create_mock_df(length=200):
    start_date = pd.Timestamp("2023-01-01")
    dates = pd.date_range(start_date, periods=length, freq="15min")
    
    data = {
        "open": np.random.uniform(100, 110, length),
        "high": np.random.uniform(110, 115, length),
        "low": np.random.uniform(95, 100, length),
        "close": np.random.uniform(100, 110, length),
        "volume": np.random.uniform(1000, 5000, length),
        "OI_Change_Pct": np.random.uniform(-2.0, 2.0, length), # Simulated OI Change
        "open_interest": np.random.uniform(1000000, 2000000, length)
    }
    
    df = pd.DataFrame(data, index=dates)
    return df

def test_strategy(strat_class, name):
    print(f"Testing {name}...")
    try:
        strat = strat_class(config={"params": {}})
        df_15m = create_mock_df()
        df_1m = create_mock_df() # For smart trend
        
        # Test 1: Standard Run
        signal = strat.generate_signal(df_15m, extra_data={"1m": df_1m})
        print(f"  [OK] generate_signal ran successfully (Result: {signal})")
        
        # Test 2: UI Conditions
        conditions = strat.check_conditions(df_15m, extra_data={"1m": df_1m})
        print(f"  [OK] check_conditions ran successfully (len={len(conditions)})")
        
        # Test 3: OI Specific Case (Force Spike)
        # Create a dataframe where OI Spikes > 2.0%
        df_spike = df_15m.copy()
        df_spike['OI_Change_Pct'].iloc[-1] = 2.5 # Spike at end
        df_spike['OI_Change_Pct'].iloc[-2] = 2.5 # Spike prev
        
        signal_spike = strat.generate_signal(df_spike, extra_data={"1m": df_1m})
        print(f"  [OK] generate_signal with OI Spike ran successfully (Result: {signal_spike})")
        
    except Exception as e:
        print(f"  [FAIL] Error testing {name}: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_strategy(ElasticReversionStrategy, "Elastic Reversion")
    test_strategy(ElasticNibblerStrategy, "Elastic Nibbler")
    test_strategy(LiquidityLightning, "Liquidity Lightning")
    test_strategy(InstitutionalScalp, "Institutional Scalp")
    test_strategy(BollingerBounceStrategy, "Bollinger Bounce")
    test_strategy(StrategyFiboPullback, "Fibo Pullback")
    test_strategy(StrategySmartTrend, "Smart Trend")
    print("All tests completed.")
