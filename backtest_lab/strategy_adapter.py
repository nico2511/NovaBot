
import pandas as pd
import sys
import os
import importlib
from backtesting import Strategy

# Support for dynamic imports
sys.path.append(os.getcwd())

class UniversalStrategyAdapter(Strategy):
    """
    Adapter that wraps any BaseStrategy from the strategies/ folder
    to be compatible with the backtesting-py library.
    """
    
    strategy_name = "ElasticReversionStrategy" 
    strategy_config = {}
    original_df = None # To support MTF (1m data)

    def init(self):
        # Dynamically import the strategy class
        import sys
        import os
        import importlib
        
        strategy_name_snake = self.class_to_snake_case(self.strategy_name)
        
        # Try different module name patterns (fibo_pullback, strategy_fibo_pullback, etc.)
        patterns = [
            strategy_name_snake,
            strategy_name_snake.replace("strategy_", ""),
            "strategy_" + strategy_name_snake if not strategy_name_snake.startswith("strategy_") else strategy_name_snake
        ]
        
        module = None
        for p in patterns:
            try:
                module = importlib.import_module(f"strategies.{p}")
                if hasattr(module, self.strategy_name):
                    break
                else:
                    module = None
            except ImportError:
                continue
                
        if not module:
            raise ImportError(f"Could not find strategy module for {self.strategy_name} in strategies/ folder (tried: {patterns})")

        StrategyClass = getattr(module, self.strategy_name)
        self.custom_strategy = StrategyClass(config=self.strategy_config)
        print(f"🛠  Initialized Strategy: {self.strategy_name}")

    def next(self):
        # 1. Prepare the 15m (or resampled) dataframe for the custom strategy
        df_15m = self.data.df.iloc[:len(self.data)]
        df_15m_mapped = df_15m.rename(columns={
            'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
        })

        # 2. Prepare MTF data if available
        extra_data = {}
        if self.original_df is not None:
            # Get current timestamp of the backtest
            current_ts = self.data.index[-1]
            # Slice 1m data up to this timestamp
            df_1m = self.original_df.loc[:current_ts].tail(100) # Keep last 100 bars for trigger
            extra_data["1m"] = df_1m.rename(columns={
                'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
            })

        # Generate signal
        signal_data = self.custom_strategy.generate_signal(df_15m_mapped, extra_data=extra_data)

        if signal_data:
            # ... rest of signal processing
            sig = signal_data.get("signal")
            sl = signal_data.get("sl")
            tp = signal_data.get("tp")
            
            try:
                if sig == "BUY" and not self.position:
                    self.buy(sl=sl, tp=tp)
                elif sig == "SELL" and not self.position:
                    self.sell(sl=sl, tp=tp)
            except Exception as e:
                # Log and continue (invalid SL/TP usually)
                print(f"⚠️  Skipped {sig} order: {e}")

    def class_to_snake_case(self, name):
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower().replace("_strategy", "")

def get_strategy_adapter(class_name, config=None, original_df=None):
    """
    Factory to create a UniversalStrategyAdapter class with specific attributes.
    This is necessary because backtesting.py uses class-level parameters.
    """
    return type(f"Adapter_{class_name}", (UniversalStrategyAdapter,), {
        "strategy_name": class_name,
        "strategy_config": config or {},
        "original_df": original_df
    })
