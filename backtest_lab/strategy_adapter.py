
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
        # The backtest should ideally run on 1m data for precision
        # df is the 'main' timeframe passed to generate_signal
        
        # 1. Get current data slice
        df_current = self.data.df.iloc[:len(self.data)]
        
        # 2. Rename columns to lowercase for strategy compatibility
        df_mapped = df_current.rename(columns={
            'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'
        })

        # 3. Detect if the strategy needs MTF (15m/1m)
        # We'll provide both by default if possible
        extra_data = {}
        
        # If the backtest is running on 1min, we can provide resampled 15min as context
        # Check if index frequency or data suggests 1min
        is_1m = len(df_mapped) > 1 and (df_mapped.index[1] - df_mapped.index[0]).total_seconds() <= 60
        
        main_df = df_mapped
        if is_1m:
            # Resample for 15m context
            # We use the full history to resample
            df_15m = df_mapped.resample('15min').agg({
                'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'
            }).dropna()
            
            # The strategy typically expects the 'main' df to be the context (15m)
            # and extra_data to have the trigger (1min)
            main_df = df_15m
            extra_data["1m"] = df_mapped.tail(100) # Keep last 100 1m candles for triggers
        
        # Generate signal
        signal_data = self.custom_strategy.generate_signal(main_df, extra_data=extra_data)

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
