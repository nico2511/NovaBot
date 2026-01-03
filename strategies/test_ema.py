"""
Test Strategy - Simple EMA Crossover
This strategy WILL generate signals to test if the backtest engine works
"""
from strategies.base import BaseStrategy

class TestEmaStrategy(BaseStrategy):
    """Ultra simple EMA crossover for testing"""
    
    def __init__(self, config: dict):
        super().__init__(config)
        self.name = "test_ema"
    
    def add_indicators(self, df):
        """Add simple EMAs"""
        import pandas_ta as ta
        df['EMA_9'] = ta.ema(df['close'], length=9)
        df['EMA_21'] = ta.ema(df['close'], length=21)
        return df
    
    def generate_signal(self, df, extra_data=None):
        """Generate signal on EMA crossover"""
        if len(df) < 25:
            return None
        
        # Current and previous EMA values
        ema_9_curr = df['EMA_9'].iloc[-1]
        ema_21_curr = df['EMA_21'].iloc[-1]
        ema_9_prev = df['EMA_9'].iloc[-2]
        ema_21_prev = df['EMA_21'].iloc[-2]
        
        # Bullish crossover
        if ema_9_prev <= ema_21_prev and ema_9_curr > ema_21_curr:
            return {
                "signal": "BUY",
                "price": df['close'].iloc[-1],
                "sl": df['close'].iloc[-1] * 0.98,  # 2% SL
                "tp": df['close'].iloc[-1] * 1.04,  # 4% TP
                "confidence": 100,
                "reason": "EMA 9 crossed above EMA 21"
            }
        
        # Bearish crossover
        if ema_9_prev >= ema_21_prev and ema_9_curr < ema_21_curr:
            return {
                "signal": "SELL",
                "price": df['close'].iloc[-1],
                "sl": df['close'].iloc[-1] * 1.02,  # 2% SL
                "tp": df['close'].iloc[-1] * 0.96,  # 4% TP
                "confidence": 100,
                "reason": "EMA 9 crossed below EMA 21"
            }
        
        return None
    
    def calculate_progress(self, df):
        """Not needed for testing"""
        return {"status": "Testing"}
