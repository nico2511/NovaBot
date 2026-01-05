
from app.services.indicators import ta
import pandas as pd
from app.core.config import config
from app.core.risk_manager import RiskManager
from strategies.base import BaseStrategy
from strategies.elastic_reversion import ElasticReversionStrategy
from strategies.scalp_ema_rsi import ScalpEmaRsi
from strategies.smart_trend import StrategySmartTrend
from strategies.smart_mean_reversion import SmartMeanReversionStrategy
from strategies.double_bottom import DoubleBottomStrategy
from strategies.double_top import DoubleTopStrategy
from strategies.bull_flag import BullFlagStrategy
from strategies.head_shoulders import HeadShouldersStrategy
from strategies.bollinger_bounce import BollingerBounceStrategy
from strategies.rsi_ping_pong import RSIPingPongStrategy
from strategies.institutional_scalp import InstitutionalScalp
import json

class StrategyEngine:
    def __init__(self, risk_manager=None, config=None):
        self.risk_manager = risk_manager
        if config:
            self.config = config
        else:
            self.load_config()
        
        
        # Initialize strategies with their specific config
        strats_config = self.config.get("strategies", {})
        
        self.strategies = {
            # Active strategies
            "scalp_ema_rsi": ScalpEmaRsi(strats_config.get("scalp_ema_rsi")),
            "elastic_reversion": ElasticReversionStrategy(strats_config.get("elastic_reversion")),
            "smart_trend": StrategySmartTrend(strats_config.get("smart_trend")),
            "smart_mean_reversion": SmartMeanReversionStrategy(strats_config.get("smart_mean_reversion")),
            
            # Pattern recognition strategies
            "double_bottom": DoubleBottomStrategy(strats_config.get("double_bottom")),
            "double_top": DoubleTopStrategy(strats_config.get("double_top")),
            "bull_flag": BullFlagStrategy(strats_config.get("bull_flag")),
            "head_shoulders": HeadShouldersStrategy(strats_config.get("head_shoulders")),
            
            # Range trading strategies
            "bollinger_bounce": BollingerBounceStrategy(strats_config.get("bollinger_bounce")),
            "rsi_ping_pong": RSIPingPongStrategy(strats_config.get("rsi_ping_pong")),
            "institutional_scalp": InstitutionalScalp(strats_config.get("institutional_scalp")),
        }

        # 🔧 FIX: Enforce strategy names to match config keys (snake_case)
        # This prevents mismatches between "ScalpEmaRsi" (Class) and "scalp_ema_rsi" (Config)
        for key, strategy in self.strategies.items():
            if strategy:
                strategy.name = key

    def load_config(self):
        try:
            with open("strategies.json", "r") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error loading strategies.json: {e}")
            self.config = {}

    def analyze(self, df: pd.DataFrame, extra_data=None):
        """
        Analyze market data and generate signals.
        
        Args:
            df: Primary dataframe (typically main timeframe)
            extra_data: Optional dict with additional dataframes for MTF strategies
        """
        # 1. Determine Regime (ADX)
        if len(df) < 50:
            return {"action": "WAIT", "reason": "Not enough data"}

        # Use new custom indicators service
        adx_res = ta.adx(df['high'], df['low'], df['close'], length=14)
        rsi_series = ta.rsi(df['close'], length=14)
        ema_9 = ta.ema(df['close'], length=9)
        ema_20 = ta.ema(df['close'], length=20)
        ema_50 = ta.ema(df['close'], length=50)

        # 1. Standard Regime (ADX based on confirmed candle iloc[-2] for stability)
        current_adx = adx_res['ADX'].iloc[-2] 
        # Calculate Slope using iloc [-2] and [-3] (Previous confirmed candles)
        prev_adx = adx_res['ADX'].iloc[-3]
        adx_slope = current_adx - prev_adx
        
        threshold = self.config.get("market_regime", {}).get("adx_threshold", 25)
        
        # DYNAMIC REGIME LOGIC
        # To be in TREND, we need ADX > Threshold AND Slope >= -3 (Not crashing hard)
        # Allows minor ADX declines (e.g., 41 -> 39) while still detecting strong trends
        # Only rejects if ADX is dropping rapidly (slope < -3)
        
        if current_adx > threshold and adx_slope >= -3:
            regime = "TREND"
        else:
            regime = "RANGE"
            
        # Log if trend rejected due to slope
        if current_adx > threshold and adx_slope < -3:
            print(f"📉 Trend Rejected: ADX {current_adx:.1f} but Slope {adx_slope:.2f} (dropping too fast)")

        # 2. WATERFALL DETECTION (Anti-Lag / Crash Detection)
        # Priority: IMMÉDIATE. Uses current forming candle (iloc[-1]) to catch crash *during* the fall.
        try:
            curr_close = df['close'].iloc[-1]
            curr_open = df['open'].iloc[-1]
            curr_ema9 = ema_9.iloc[-1]
            curr_ema20 = ema_20.iloc[-1]
            
            # Previous candle (confirmed)
            prev_close = df['close'].iloc[-2]
            prev_open = df['open'].iloc[-2]
            prev_low = df['low'].iloc[-2]

            is_curr_red = curr_close < curr_open
            is_prev_red = prev_close < prev_open
            
            # Waterfall Condition: Price < EMA9 < EMA20 AND Double Red Candles AND Making Lower Lows
            if (curr_close < curr_ema9) and (curr_ema9 < curr_ema20) and \
               is_curr_red and is_prev_red and \
               (curr_close < prev_low):
                regime = "TREND_BEAR_STRONG"
                # print(f"🌊 WATERFALL DETECTED! Price: {curr_close} < EMA9 < EMA20. Regime forced to: {regime}")
        except Exception as e:
            print(f"⚠️ Waterfall check failed: {e}")

        # Add indicators to df for strategies
        df['ADX_14'] = adx_res['ADX']
        df['RSI_14'] = rsi_series
        df['EMA_9'] = ema_9
        df['EMA_20'] = ema_20
        df['EMA_50'] = ema_50
        
        # 3. Select Strategies
        active_strategies = []
        for name, params in self.config.get("strategies", {}).items():
            if not params.get("enabled"):
                continue
            
            strat_type = params.get("type")
            if regime == "TREND" and strat_type == "trend":
                active_strategies.append(self.strategies[name])
            elif regime == "RANGE" and strat_type == "range":
                active_strategies.append(self.strategies[name])
            elif strat_type == "sniper": # FVG always active?
                active_strategies.append(self.strategies[name])
            elif strat_type == "reversion": # Reversion always active (Counter-trend or Range)
                active_strategies.append(self.strategies[name])

        # 4. Generate Signals
        signals = []
        for strat in active_strategies:
            sig = strat.generate_signal(df, extra_data=extra_data)
            if sig:
                # Check execution type
                params = strat.config.get("params", {})
                is_manual = params.get("execution_type") == "manual" or params.get("requires_confirmation") == True
                
                if isinstance(sig, dict):
                    # Strategy returned rich object
                    signal_data = sig
                    signal_data["strategy"] = strat.name
                    signal_data["price"] = sig.get("price", df['close'].iloc[-1])
                    signal_data["timestamp"] = df.index[-1]
                    if is_manual:
                        signal_data["manual_approval"] = True
                    signals.append(signal_data)
                else:
                    # Legacy string return
                    signal_data = {
                        "strategy": strat.name,
                        "signal": sig, 
                        "price": df['close'].iloc[-1],
                        "timestamp": df.index[-1]
                    }
                
                # --- GLOBAL DIRECTION FILTER ---
                # This ensures ALL strategies respect allow_longs/allow_shorts from config
                # even if the strategy code doesn't implement it explicitly.
                
                signal_type = signal_data.get("signal", "").upper()
                allow_longs = params.get("allow_longs", True) 
                allow_shorts = params.get("allow_shorts", True)
                
                direction_allowed = True
                rejection_reason = ""

                if signal_type == "BUY" and not allow_longs:
                    direction_allowed = False
                    rejection_reason = "Longs disabled"
                elif signal_type == "SELL" and not allow_shorts:
                    direction_allowed = False
                    rejection_reason = "Shorts disabled"
                
                # --- NEW: ANTI-CHASING FILTER (Bollinger Bands) ---
                # Calculate BB only if we have a signal to verify
                if direction_allowed:
                    try:
                        # 20 SMA for BB
                        sma_20 = df['close'].rolling(window=20).mean().iloc[-1]
                        std_20 = df['close'].rolling(window=20).std().iloc[-1]
                        bb_upper = sma_20 + (std_20 * 2)
                        bb_lower = sma_20 - (std_20 * 2)
                        curr_close = df['close'].iloc[-1]
                        
                        # Filter Logic
                        if signal_type == "SELL":
                            # Reject if close <= Lower Band * 1.01 (1% from support)
                            # Prevents shorting the bottom
                            if curr_close <= (bb_lower * 1.01):
                                direction_allowed = False
                                rejection_reason = "Price too close to support/lower band (Oversold)"
                                
                        elif signal_type == "BUY":
                            # Reject if close >= Upper Band * 0.99 (1% from resistance)
                            # Prevents longing the top
                            if curr_close >= (bb_upper * 0.99):
                                direction_allowed = False
                                rejection_reason = "Price too close to resistance/upper band (Overbought)"
                    except Exception as e:
                        print(f"⚠️ BB Filter Error: {e}")

                if direction_allowed:
                    if is_manual:
                        signal_data["manual_approval"] = True
                    signals.append(signal_data)
                elif rejection_reason:
                     # Optional: Log rejection
                     pass
                     # print(f"🚫 Signal REJECTED: {strat.name} {signal_type} -> {rejection_reason}")
        
        # 5. Calculate Progress AND Conditions
        progress = {}
        conditions = {}
        for strat in active_strategies:
            try:
                progress[strat.name] = strat.calculate_progress(df, extra_data=extra_data)
                
                # Check detailed conditions
                if hasattr(strat, "check_conditions"):
                    conditions[strat.name] = strat.check_conditions(df, extra_data=extra_data)
                else:
                    conditions[strat.name] = []
            except Exception as e:
                print(f"Error calculating progress for {strat.name}: {e}")
                progress[strat.name] = 0
                conditions[strat.name] = []

        return {
            "regime": regime,
            "adx": current_adx,
            "rsi": rsi_series.iloc[-1],
            "ema_20": ema_20.iloc[-1],
            "ema_50": ema_50.iloc[-1],
            "strategies": [s.name for s in active_strategies],
            "progress": progress,
            "conditions": conditions,
            "signals": signals
        }
