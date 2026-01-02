from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy

# ============================================
# STRATEGY: RSI Reversal (Intraday)
# ============================================
class StrategyRSIReversal(BaseStrategy):
    """
    RSI Reversal V3 - Optimized Version
    
    Intraday reversal strategy based on RSI exits from extreme zones.
    
    Entry:
    - LONG: RSI was < 30 (N-1) and now > 30 (N) - Exit from oversold
    - SHORT: RSI was > 70 (N-1) and now < 70 (N) - Exit from overbought
           + FILTER: Price must be below EMA 200 (bearish trend)
    
    Risk Management:
    - Stop Loss: 1.5% from entry
    - Take Profit: 3.0% from entry (1:2 ratio)
    
    Performance: +11.49% on BTC 15m (vs +8.36% for V1)
    Improvement: SHORT improved from -10.42% to -1.15%
    """
    
    def add_indicators(self, df):
        params = self.config.get("params", {})
        rsi_len = params.get("rsi_period", 14)
        use_short_filter = params.get("use_short_filter", True)
        
        df['RSI'] = ta.rsi(df['close'], length=rsi_len)
        
        # EMA 200 for SHORT filter
        df['EMA_200'] = ta.ema(df['close'], length=200)
        
        return df
    
    def generate_signal(self, df, extra_data=None):
        df = self.add_indicators(df)
        
        if len(df) < 210:  # Need 200 for EMA + 10 buffer
            return None
        
        params = self.config.get("params", {})
        use_short_filter = params.get("use_short_filter", True)
        sl_pct = params.get("sl_pct", 0.015)  # 1.5%
        tp_pct = params.get("tp_pct", 0.030)  # 3.0%
        
        rsi_curr = df['RSI'].iloc[-1]
        rsi_prev = df['RSI'].iloc[-2]
        close = df['close'].iloc[-1]
        ema_200 = df['EMA_200'].iloc[-1]
        
        # LONG: Exit from oversold (RSI crosses above 30)
        # No filter - keep V1 logic (works well)
        if rsi_prev < 30 and rsi_curr > 30:
            sl = close * (1 - sl_pct)
            tp = close * (1 + tp_pct)
            
            return {
                'signal': 'BUY',
                'price': close,
                'sl': sl,
                'tp': tp,
                'comment': f'RSI Reversal V3 Long - Exit from oversold (RSI: {rsi_curr:.1f})'
            }
        
        # SHORT: Exit from overbought (RSI crosses below 70)
        # V3: Add EMA 200 filter to improve SHORT performance
        short_filter_ok = not use_short_filter or close < ema_200
        
        if rsi_prev > 70 and rsi_curr < 70 and short_filter_ok:
            sl = close * (1 + sl_pct)
            tp = close * (1 - tp_pct)
            
            return {
                'signal': 'SELL',
                'price': close,
                'sl': sl,
                'tp': tp,
                'comment': f'RSI Reversal V3 Short - Exit from overbought (RSI: {rsi_curr:.1f}, Trend: Bearish)'
            }
        
        return None
    
    def calculate_progress(self, df, extra_data=None):
        """Calculate proximity to RSI reversal zones"""
        try:
            df = self.add_indicators(df)
            if len(df) < 210:
                return 0
            
            rsi = df['RSI'].iloc[-1]
            close = df['close'].iloc[-1]
            ema_200 = df['EMA_200'].iloc[-1]
            
            progress = 0
            
            # In oversold zone (approaching long signal)
            if rsi < 30:
                progress = int(100 * (30 - rsi) / 30)  # Deeper = higher progress
            
            # In overbought zone (approaching short signal)
            elif rsi > 70:
                base_progress = int(100 * (rsi - 70) / 30)
                
                # Bonus if in bearish trend (better SHORT setup)
                if close < ema_200:
                    progress = min(100, base_progress + 20)
                else:
                    progress = base_progress
            
            # Approaching zones
            elif 30 <= rsi <= 40:
                progress = int(50 * (40 - rsi) / 10)
            elif 60 <= rsi <= 70:
                base_progress = int(50 * (rsi - 60) / 10)
                
                # Bonus if approaching in bearish trend
                if close < ema_200:
                    progress = min(100, base_progress + 10)
                else:
                    progress = base_progress
            
            return min(100, max(0, progress))
        except:
            return 0
