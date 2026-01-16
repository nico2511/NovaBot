from strategies.base import BaseStrategy
from app.services.indicators import ta

class ElasticNibblerStrategy(BaseStrategy):
    """
    The Elastic Nibbler Strategy
    ----------------------------
    Type: Reversion Scalp (BTC/ETH Only)
    Timeframe: 1m or 5m
    
    Logic:
    - BB Breakout (Price > Upper or < Lower)
    - RSI Extreme (<20 or >80)
    - Volume Spike (>2x Avg)
    - Filter: ADX > 25 (skip strong trends)
    
    Management (Custom):
    - No fixed TP
    - Trailing SL: 
      - Trigger at +0.15% PnL -> Move SL to Break-Even + Fees (+0.08%)
      - Above +0.30% PnL -> Tight Trail (ATR based or logical step)
    """
    
    def __init__(self, config):
        super().__init__(config)
        self.params = self.config.get("params", {})
        
    def generate_signal(self, df, extra_data=None):
        # 0. BTC-Only Restriction (Best-Effort)
        # Check if symbol is provided in extra_data, otherwise infer from price
        # Default to False so it doesn't break other strategies if copied without config
        is_btc_only = self.params.get("is_btc_only", False)
        
        if is_btc_only:
            symbol = None
            if extra_data and isinstance(extra_data, dict):
                symbol = extra_data.get("symbol", "").upper()
            
            # If symbol explicitly provided and not BTC, skip
            if symbol and symbol != "BTC":
                return None
            
            # Fallback: If no symbol provided, infer from price (BTC > $5000)
            if not symbol:
                current_price = df['close'].iloc[-1]
                if current_price < 5000:  # Likely ETH or other, not BTC
                    return None

        # 1. Indicators
        close = df['close']
        high = df['high']
        low = df['low']
        volume = df['volume']
        
        # Bollinger Bands (20, 3.0) - Note: User asked for 3.0 SD
        bb_period = self.params.get("bb_period", 20)
        bb_std = self.params.get("bb_std", 3.0)
        
        bb_df = ta.bbands(close, length=bb_period, std=bb_std)
        bb_upper = bb_df['BBU']
        bb_lower = bb_df['BBL']
        
        # RSI (14)
        rsi_period = self.params.get("rsi_period", 14)
        rsi = ta.rsi(close, length=rsi_period)
        
        # Volume Avg (using 50 periods like others)
        vol_avg = ta.sma(volume, length=50)
        
        # ADX (for filtering strong trends)
        adx_df = ta.adx(high, low, close, length=14)
        adx = adx_df['ADX'].iloc[-1]
        
        # Current Values
        current_close = close.iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_vol = volume.iloc[-1]
        current_vol_avg = vol_avg.iloc[-1]
        
        upper_band = bb_upper.iloc[-1]
        lower_band = bb_lower.iloc[-1]
        
        # PARAMS
        entry_vol_mult = self.params.get("entry_vol_multiplier", 2.0)
        adx_limit = self.params.get("adx_limit", 25)
        
        # 2. Conditions
        # A. Volume Spike
        # Avoid division by zero
        if current_vol_avg == 0: return None
        is_vol_spike = current_vol > (current_vol_avg * entry_vol_mult)
        
        # B. ADX Filter (Skip if trend is too strong)
        # User said: "Skip si ADX > 25"
        if adx > adx_limit:
            return None
            
        # C. LONG Setup
        # Price < BB Lower AND RSI < 20
        if current_close < lower_band and current_rsi < 20 and is_vol_spike:
            return {
                "signal": "BUY",
                "price": current_close,
                "metadata": {
                    "reason": f"BB Breakout (Low) + RSI {current_rsi:.1f} + Vol {current_vol/current_vol_avg:.1f}x",
                    "adx": adx
                }
            }
            
        # D. SHORT Setup
        # Price > BB Upper AND RSI > 80
        if current_close > upper_band and current_rsi > 80 and is_vol_spike:
             return {
                "signal": "SELL",
                "price": current_close,
                "metadata": {
                    "reason": f"BB Breakout (High) + RSI {current_rsi:.1f} + Vol {current_vol/current_vol_avg:.1f}x",
                    "adx": adx
                }
            }
            
        return None

    def manage_trade(self, trade, current_price, df=None, extra_data=None):
        """
        Custom Trailing Logic for Elastic Nibbler
        """
        if not trade: return None
        
        entry_price = trade.get("entry")
        side = trade.get("side")
        sl_price = trade.get("sl")
        
        if not entry_price: return None
        
        # Params
        activation_pnl = self.params.get("activation_pnl_pct", 0.0015) # 0.15%
        secure_pnl = self.params.get("secure_pnl_pct", 0.0008)     # 0.08% (~fees+profit)
        hard_trail_start = 0.003 # 0.30%
        
        updates = {}
        
        if side == "BUY":
            pnl_pct = (current_price - entry_price) / entry_price
            
            # 1. First Step: Secure Fees
            if pnl_pct >= activation_pnl:
                target_sl = entry_price * (1 + secure_pnl)
                # Only move SL up
                if not sl_price or target_sl > sl_price:
                     updates["sl"] = target_sl
            
            # 2. Hard Trailing (Above 0.3%)
            if pnl_pct >= hard_trail_start:
                # Trail at 0.15% distance for example (aggressive)
                trail_dist = entry_price * 0.0015
                target_sl = current_price - trail_dist
                
                # Check current SL to ensure we don't loosen it
                # Logic: If existing SL is lower than target, raise it.
                if not sl_price or target_sl > sl_price:
                    updates["sl"] = target_sl
                    
        else: # SELL
            pnl_pct = (entry_price - current_price) / entry_price
            
            # 1. First Step: Secure Fees
            if pnl_pct >= activation_pnl:
                target_sl = entry_price * (1 - secure_pnl)
                # Only move SL down
                if not sl_price or target_sl < sl_price:
                    updates["sl"] = target_sl
                    
            # 2. Hard Trailing
            if pnl_pct >= hard_trail_start:
                 trail_dist = entry_price * 0.0015
                 target_sl = current_price + trail_dist
                 
                 if not sl_price or target_sl < sl_price:
                     updates["sl"] = target_sl
                     
        return updates if updates else {}

    def calculate_progress(self, df, extra_data=None):
        # Visual progress (closeness to band)
        # normalized 0-100
        return 0 
