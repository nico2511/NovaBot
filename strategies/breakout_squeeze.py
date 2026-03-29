from app.services.indicators import ta
import pandas as pd
from strategies.base import BaseStrategy


class BreakoutSqueezeStrategy(BaseStrategy):
    """
    Breakout Squeeze Strategy (LONG & SHORT)
    
    Détecte les compressions de volatilité (squeeze Bollinger) puis trade la cassure
    directionnelle avec confirmation de volume et momentum.
    
    Logique :
    1. SETUP : BB Width < seuil (squeeze) pendant N bougies
    2. FILTRE : ADX en hausse (énergie qui monte)
    3. TRIGGER : Close casse au-dessus/en-dessous des bandes avec volume spike
    4. DIRECTION : Confirmée par EMA alignment + RSI momentum
    
    Régime : Fonctionne en transition Range → Trend (type "trend" pour l'engine)
    
    Risk Management :
    - SL : Bande opposée ou ATR-based
    - TP : Extension ATR (expansion post-squeeze)
    """

    AI_PERSONA = """
    CODENAME: "BREAKOUT HUNTER"
    
    ROLE:
    You are a SPRING-LOADED TRAP. You wait patiently during compression, then strike 
    with precision when the market breaks free from its cage.
    
    PRIME DIRECTIVE:
    "Compression precedes expansion." We only fire when the squeeze is REAL and the 
    breakout is CONFIRMED. False breakouts are our enemy.
    
    RULES OF ENGAGEMENT:
    1. VERIFY THE SQUEEZE: Bollinger Width must be genuinely tight (< threshold). 
       A "normal" range is NOT a squeeze.
    2. ENERGY CHECK: ADX must be RISING. A flat ADX during squeeze = no energy = no breakout.
    3. VOLUME EXPLOSION: The breakout candle MUST have significantly higher volume. 
       A low-volume breakout is a trap.
    4. MOMENTUM ALIGNMENT: RSI must confirm direction (> 50 for LONG, < 50 for SHORT).
    
    RESPONSE STYLE:
    Patient during setup, decisive on trigger.
    "Squeeze detected - Coiling..." → "BREAKOUT CONFIRMED - Engaging."
    """

    def __init__(self, config=None):
        super().__init__(config)
        
        params = self.config.get("params", {})
        self.bb_period = params.get("bb_period", 20)
        self.bb_std = params.get("bb_std", 2.0)
        self.squeeze_width_pct = params.get("squeeze_width_pct", 1.5)
        self.squeeze_lookback = params.get("squeeze_lookback", 6)
        self.adx_min = params.get("adx_min", 18)
        self.adx_rising_bars = params.get("adx_rising_bars", 2)
        self.volume_multiplier = params.get("volume_multiplier", 1.8)
        self.rsi_period = params.get("rsi_period", 14)
        self.min_rr = params.get("min_rr", 1.5)
        self.sl_atr_mult = params.get("sl_atr_mult", 1.2)
        self.tp_atr_mult = params.get("tp_atr_mult", 2.5)
        self.ema_fast = params.get("ema_fast", 9)
        self.ema_slow = params.get("ema_slow", 21)

    def add_indicators(self, df):
        """Add indicators for breakout detection."""
        # Bollinger Bands
        bb = ta.bbands(df['close'], length=self.bb_period, std=self.bb_std)
        df['BBU'] = bb['BBU']
        df['BBL'] = bb['BBL']
        df['BBM'] = bb['BBM']
        
        # BB Width (percentual)
        df['BB_Width_Pct'] = ((df['BBU'] - df['BBL']) / df['BBM']) * 100
        
        # EMAs
        df[f'EMA_{self.ema_fast}'] = ta.ema(df['close'], length=self.ema_fast)
        df[f'EMA_{self.ema_slow}'] = ta.ema(df['close'], length=self.ema_slow)
        
        # RSI
        df[f'RSI_{self.rsi_period}'] = ta.rsi(df['close'], length=self.rsi_period)
        
        # ATR
        df['ATRr_14'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        
        return df

    def generate_signal(self, df, extra_data=None):
        if df is None or df.empty or len(df) < 60:
            return None
        
        self.add_indicators(df)
        
        params = self.config.get("params", {})
        
        # === Column references ===
        rsi_col = f'RSI_{self.rsi_period}'
        ema_fast_col = f'EMA_{self.ema_fast}'
        ema_slow_col = f'EMA_{self.ema_slow}'
        
        required_cols = ['BBU', 'BBL', 'BB_Width_Pct', rsi_col, ema_fast_col, ema_slow_col, 'ATRr_14']
        for col in required_cols:
            if col not in df.columns:
                return None
        
        # === Anti-repainting: use confirmed candle [-2] for trigger ===
        curr = df.iloc[-2]
        prev = df.iloc[-3]
        
        close = curr['close']
        high = curr['high']
        low = curr['low']
        bb_upper = curr['BBU']
        bb_lower = curr['BBL']
        bb_width = curr['BB_Width_Pct']
        rsi = curr[rsi_col]
        ema_fast = curr[ema_fast_col]
        ema_slow = curr[ema_slow_col]
        atr = curr['ATRr_14']
        
        if pd.isna(atr) or atr == 0:
            return None
        
        # ==========================================
        # STEP 1: SQUEEZE DETECTION
        # ==========================================
        # BB Width must have been tight for at least N bars (building compression)
        squeeze_window = df['BB_Width_Pct'].iloc[-(self.squeeze_lookback + 2):-2]
        
        if len(squeeze_window) < self.squeeze_lookback:
            return None
        
        # Count how many bars were in squeeze
        bars_in_squeeze = (squeeze_window < self.squeeze_width_pct).sum()
        
        # Need at least 60% of lookback in squeeze (allows brief spikes)
        min_squeeze_bars = int(self.squeeze_lookback * 0.6)
        if bars_in_squeeze < min_squeeze_bars:
            return None
        
        # ==========================================
        # STEP 2: ADX FILTER (Energy Rising)
        # ==========================================
        if 'ADX_14' in df.columns:
            current_adx = df['ADX_14'].iloc[-2]
            
            # ADX must meet minimum
            if current_adx < self.adx_min:
                return None
            
            # ADX must be rising over last N bars
            adx_rising = True
            for i in range(1, self.adx_rising_bars + 1):
                if df['ADX_14'].iloc[-2 - i] >= df['ADX_14'].iloc[-1 - i]:
                    adx_rising = False
                    break
            
            if not adx_rising:
                return None
        
        # ==========================================
        # STEP 3: BREAKOUT TRIGGER
        # ==========================================
        # The current candle must CLOSE outside the Bollinger Band
        # Previous candle should have been inside (or near) → confirms fresh breakout
        
        prev_close = prev['close']
        prev_bb_upper = prev['BBU']
        prev_bb_lower = prev['BBL']
        
        is_bullish_breakout = (close > bb_upper) and (prev_close <= prev_bb_upper * 1.002)
        is_bearish_breakout = (close < bb_lower) and (prev_close >= prev_bb_lower * 0.998)
        
        if not (is_bullish_breakout or is_bearish_breakout):
            return None
        
        # ==========================================
        # STEP 4: VOLUME CONFIRMATION
        # ==========================================
        if 'volume' in df.columns:
            current_vol = df['volume'].iloc[-2]
            avg_vol = df['volume'].iloc[-22:-2].mean()
            
            if avg_vol > 0 and current_vol < avg_vol * self.volume_multiplier:
                return None  # No volume = no conviction
        
        # ==========================================
        # STEP 5: DIRECTION CONFIRMATION (EMA + RSI)
        # ==========================================
        
        if is_bullish_breakout:
            # EMA alignment: fast > slow
            if ema_fast <= ema_slow:
                return None
            # RSI momentum: > 50 (bullish)
            if rsi < 50:
                return None
            # RSI not extreme (avoid chasing)
            if rsi > 80:
                return None
            
            # SL below lower band or ATR-based
            sl = max(bb_lower, close - (self.sl_atr_mult * atr))
            tp = close + (self.tp_atr_mult * atr)
            
            risk = close - sl
            reward = tp - close
            
            if risk <= 0:
                return None
            
            rr = reward / risk
            if rr < self.min_rr:
                return None
            
            return {
                "signal": "BUY",
                "sl": sl,
                "tp": tp,
                "price": close,
                "comment": f"💥 Breakout UP! Squeeze {bars_in_squeeze}/{self.squeeze_lookback} bars, Vol {current_vol/avg_vol:.1f}x, RSI {rsi:.0f}",
                "metadata": {
                    "squeeze_bars": bars_in_squeeze,
                    "bb_width": bb_width,
                    "vol_ratio": current_vol / avg_vol if avg_vol > 0 else 0,
                    "rr": rr
                }
            }
        
        elif is_bearish_breakout:
            # EMA alignment: fast < slow
            if ema_fast >= ema_slow:
                return None
            # RSI momentum: < 50 (bearish)
            if rsi > 50:
                return None
            # RSI not extreme
            if rsi < 20:
                return None
            
            # SL above upper band or ATR-based
            sl = min(bb_upper, close + (self.sl_atr_mult * atr))
            tp = close - (self.tp_atr_mult * atr)
            
            risk = sl - close
            reward = close - tp
            
            if risk <= 0:
                return None
            
            rr = reward / risk
            if rr < self.min_rr:
                return None
            
            return {
                "signal": "SELL",
                "sl": sl,
                "tp": tp,
                "price": close,
                "comment": f"💥 Breakout DOWN! Squeeze {bars_in_squeeze}/{self.squeeze_lookback} bars, Vol {current_vol/avg_vol:.1f}x, RSI {rsi:.0f}",
                "metadata": {
                    "squeeze_bars": bars_in_squeeze,
                    "bb_width": bb_width,
                    "vol_ratio": current_vol / avg_vol if avg_vol > 0 else 0,
                    "rr": rr
                }
            }
        
        return None

    def calculate_progress(self, df, extra_data=None):
        """
        Returns detailed progress stages for monitoring.
        Stages:
        1. Squeeze Detection (BB Width)
        2. Energy (ADX Rising)
        3. Trigger (Breakout + Volume)
        """
        if df is None or df.empty or len(df) < 60:
            return {
                "strategy": "Breakout Squeeze",
                "score": 0,
                "stages": [{"name": "Data Check", "status": "FAIL", "details": "Not enough data"}]
            }
        
        try:
            self.add_indicators(df)
            
            rsi_col = f'RSI_{self.rsi_period}'
            ema_fast_col = f'EMA_{self.ema_fast}'
            ema_slow_col = f'EMA_{self.ema_slow}'
            
            close = df['close'].iloc[-1]
            bb_upper = df['BBU'].iloc[-1]
            bb_lower = df['BBL'].iloc[-1]
            bb_width = df['BB_Width_Pct'].iloc[-1]
            rsi = df[rsi_col].iloc[-1]
            ema_fast = df[ema_fast_col].iloc[-1]
            ema_slow = df[ema_slow_col].iloc[-1]
            
            stages = []
            score = 0
            
            # --- Stage 1: Squeeze Detection ---
            squeeze_window = df['BB_Width_Pct'].iloc[-self.squeeze_lookback:]
            bars_in_squeeze = (squeeze_window < self.squeeze_width_pct).sum()
            min_squeeze_bars = int(self.squeeze_lookback * 0.6)
            
            is_squeezing = bars_in_squeeze >= min_squeeze_bars
            
            s1_status = "WAIT"
            s1_details = f"BB Width: {bb_width:.2f}% (Squeeze < {self.squeeze_width_pct}%)"
            
            if is_squeezing:
                s1_status = "READY"
                s1_details = f"SQUEEZE! {bars_in_squeeze}/{self.squeeze_lookback} bars tight"
                score += 40
            elif bb_width < self.squeeze_width_pct * 1.5:
                s1_status = "NEAR"
                s1_details = f"Tightening... Width: {bb_width:.2f}%"
                score += 15
            
            stages.append({
                "name": "1. Squeeze",
                "status": s1_status,
                "details": s1_details,
                "metrics": {
                    "bb_width": {"value": round(bb_width, 2), "threshold": self.squeeze_width_pct, "op": "<"}
                }
            })
            
            # --- Stage 2: ADX Energy ---
            adx_val = 0
            adx_rising = False
            if 'ADX_14' in df.columns:
                adx_val = df['ADX_14'].iloc[-1]
                prev_adx = df['ADX_14'].iloc[-2]
                adx_rising = adx_val > prev_adx
            
            s2_status = "WAIT"
            s2_details = f"ADX: {adx_val:.1f}"
            
            if adx_val >= self.adx_min and adx_rising:
                s2_status = "PASS"
                s2_details = f"ADX: {adx_val:.1f} ↑ (Energy Rising)"
                score += 25
            elif adx_rising:
                s2_status = "NEAR"
                s2_details = f"ADX: {adx_val:.1f} ↑ (Rising but weak)"
                score += 10
            
            stages.append({
                "name": "2. ADX Energy",
                "status": s2_status,
                "details": s2_details,
                "metrics": {
                    "adx": {"value": round(adx_val, 1), "threshold": self.adx_min, "op": ">"}
                }
            })
            
            # --- Stage 3: Breakout State ---
            at_upper = close >= bb_upper * 0.998
            at_lower = close <= bb_lower * 1.002
            
            s3_status = "WAIT"
            s3_details = "Inside bands"
            
            if close > bb_upper:
                s3_status = "TRIGGER!"
                s3_details = f"ABOVE Upper Band ({bb_upper:.2f})"
                score += 35
            elif close < bb_lower:
                s3_status = "TRIGGER!"
                s3_details = f"BELOW Lower Band ({bb_lower:.2f})"
                score += 35
            elif at_upper or at_lower:
                s3_status = "NEAR"
                s3_details = f"Testing {'Upper' if at_upper else 'Lower'} Band"
                score += 15
            
            stages.append({
                "name": "3. Breakout",
                "status": s3_status,
                "details": s3_details
            })
            
            # Determine Bias
            bias = "NEUTRAL"
            if ema_fast > ema_slow:
                bias = "LONG"
            elif ema_fast < ema_slow:
                bias = "SHORT"
            
            return {
                "strategy": "Breakout Squeeze",
                "score": min(100, score),
                "bias": bias,
                "stages": stages
            }
        
        except Exception as e:
            return {
                "strategy": "Breakout Squeeze",
                "score": 0,
                "error": str(e),
                "bias": "NEUTRAL",
                "stages": []
            }

    def check_conditions(self, df, extra_data=None):
        return self.calculate_progress(df, extra_data)

    def get_threshold_comparisons(self, df, extra_data=None):
        """Get detailed threshold comparisons for Parameters section"""
        if df is None or df.empty:
            return {}
        
        try:
            self.add_indicators(df)
            
            bb_width = df['BB_Width_Pct'].iloc[-1]
            rsi = df[f'RSI_{self.rsi_period}'].iloc[-1]
            ema_fast = df[f'EMA_{self.ema_fast}'].iloc[-1]
            ema_slow = df[f'EMA_{self.ema_slow}'].iloc[-1]
            
            adx_val = 0
            if 'ADX_14' in df.columns:
                adx_val = df['ADX_14'].iloc[-1]
            
            squeeze_status = "ACTIVE" if bb_width < self.squeeze_width_pct else "Waiting"
            ema_dir = "Bullish" if ema_fast > ema_slow else "Bearish"
            
            return {
                "BB Width": f"{bb_width:.2f}% (Squeeze < {self.squeeze_width_pct}%) — {squeeze_status}",
                "ADX": f"{adx_val:.1f} (Min: {self.adx_min})",
                "RSI": f"{rsi:.1f} (Dir: {'Bull' if rsi > 50 else 'Bear'})",
                "EMA Alignment": f"{ema_dir} (EMA{self.ema_fast} vs EMA{self.ema_slow})"
            }
        except Exception as e:
            return {"Error": str(e)}
