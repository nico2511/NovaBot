
from app.services.indicators import ta
import pandas as pd
from app.core.config import config
from app.core.risk_manager import RiskManager
from strategies.base import BaseStrategy
from strategies.elastic_reversion import ElasticReversionStrategy
from strategies.scalp_ema_rsi import ScalpEmaRsi
from strategies.breakout_squeeze import BreakoutSqueezeStrategy

from strategies.bollinger_middle_bounce import BollingerMiddleBounceStrategy
from strategies.institutional_scalp import InstitutionalScalp
from strategies.fibo_pullback import StrategyFiboPullback
from strategies.elastic_nibbler import ElasticNibblerStrategy
from strategies.liquidity_lightning import LiquidityLightning
from strategies.sniper_precision_trend import SniperPrecisionTrend
from strategies.gamma_bear_vortex import GammaBearVortex
from strategies.supertrend import StrategySupertrend

# Import robuste pour Panic Close
try:
    from strategies.utils import should_panic_close
except ImportError:
    print("⚠️ Warning: strategies.utils not found. Panic close disabled.")
    def should_panic_close(strategy_name, df, regime="RANGE"): return (False, "")

import json

class StrategyEngine:
    def __init__(self, risk_manager=None, config=None):
        self.risk_manager = risk_manager
        if config:
            self.config = config
        else:
            self.load_config()
        
        
        # Initialize strategies with their specific config
        strats_config = self.config
        
        self.strategies = {
            # Active strategies
            "scalp_ema_rsi": ScalpEmaRsi(strats_config.get("scalp_ema_rsi")),
            "elastic_reversion": ElasticReversionStrategy(strats_config.get("elastic_reversion")),
            
            # Trend strategies
            "bollinger_middle_bounce": BollingerMiddleBounceStrategy(strats_config.get("bollinger_middle_bounce")),
            
            # Range trading strategies
            "institutional_scalp": InstitutionalScalp(strats_config.get("institutional_scalp")),
            "fibo_pullback": StrategyFiboPullback(strats_config.get("fibo_pullback")),
            "elastic_nibbler": ElasticNibblerStrategy(strats_config.get("elastic_nibbler")),
            "liquidity_lightning": LiquidityLightning(strats_config.get("liquidity_lightning")),
            "sniper_precision_trend": SniperPrecisionTrend(strats_config.get("sniper_precision_trend")),
            "gamma_bear_vortex": GammaBearVortex(strats_config.get("gamma_bear_vortex")),
            "supertrend": StrategySupertrend(strats_config.get("supertrend")),
            
            # Breakout strategy
            "breakout_squeeze": BreakoutSqueezeStrategy(strats_config.get("breakout_squeeze")),
        }

        # 🔧 FIX: Enforce strategy names to match config keys (snake_case)
        # This prevents mismatches between "ScalpEmaRsi" (Class) and "scalp_ema_rsi" (Config)
        for key, strategy in self.strategies.items():
            if strategy:
                strategy.name = key

    def load_config(self):
        try:
            with open("data/config/strategies.json", "r") as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error loading data/config/strategies.json: {e}")
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
        # FIX: ADX returns a DataFrame, access specific column properly
        adx_df = ta.adx(df['high'], df['low'], df['close'], length=14)
        rsi_series = ta.rsi(df['close'], length=14)
        ema_9 = ta.ema(df['close'], length=9)
        ema_20 = ta.ema(df['close'], length=20)
        ema_50 = ta.ema(df['close'], length=50)

        # 1. Standard Regime (ADX based on confirmed candle iloc[-2] for stability)
        # FIX: Access 'ADX' column explicitly from adx_df
        current_adx = adx_df['ADX'].iloc[-2] 
        # Calculate Slope using iloc [-2] and [-3] (Previous confirmed candles)
        prev_adx = adx_df['ADX'].iloc[-3]
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
        df['ADX_14'] = adx_df['ADX'] # Save specific column
        df['RSI_14'] = rsi_series
        df['EMA_9'] = ema_9
        df['EMA_20'] = ema_20
        df['EMA_50'] = ema_50
        
        # 3. Select Strategies
        active_strategies = []
        for name, params in self.config.items():
            if not isinstance(params, dict): continue # Skip non-dict meta keys if any
            if not params.get("enabled"):
                continue
            
            strat_type = params.get("type")
            
            # FIX: Logic for Strategy Selection
            if (regime == "TREND" or regime == "TREND_BEAR_STRONG") and strat_type == "trend":
                active_strategies.append(self.strategies[name])
                
            elif regime == "RANGE":
                if strat_type == "range":
                    active_strategies.append(self.strategies[name])
                elif strat_type == "reversion": # FIX: Reversion works in Range
                    active_strategies.append(self.strategies[name])
                    
            elif strat_type in ["sniper", "scalp_choc", "always_active"]: 
                # Sniper and Always Active are trigger-based, always check
                active_strategies.append(self.strategies[name])

        # Log active strategies
        if active_strategies:
            strat_names = ", ".join([s.name for s in active_strategies])
            print(f"[BOT] 🎯 Stratégies actives > {strat_names}")

        # 4. Generate Signals
        signals = []
        for strat in active_strategies:
            
            # --- PANIC CLOSE / KILL SWITCH (Imported or Fallback) ---
            # NOTE: Kill Switch now only BLOCKS new entries for incompatible strategies
            # It does NOT generate SELL signals (that would be sent to AI for nothing)
            # Actual panic close of existing positions is handled in bot.py trade management
            try:
                should_panic, panic_reason = should_panic_close(strat.name, df, regime=regime)
                if should_panic:
                    print(f"🚨 KILL SWITCH: {strat.name} BLOCKED - {panic_reason}")
                    continue  # Skip this strategy entirely (no signal generation)
            except Exception as e:
                print(f"⚠️ Panic check error: {e}")
            
            # Normal Signal Generation
            sig = strat.generate_signal(df, extra_data=extra_data)
            
            if sig:
                # Check execution type
                params = strat.config.get("params", {})
                is_manual = params.get("execution_type") == "manual" or params.get("requires_confirmation") == True
                
                symbol = extra_data.get("symbol") if extra_data else None
                if isinstance(sig, dict):
                    # Strategy returned rich object
                    signal_data = sig
                    signal_data["strategy"] = strat.name
                    signal_data["symbol"] = symbol or sig.get("symbol", "UNKNOWN")
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
                        "symbol": symbol or "UNKNOWN",
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
                    # Exception: Panic close should override 'allow_shorts' if it's just closing a long?
                    # But 'SELL' here usually means 'Open Short' or 'Close Long'.
                    # If it's a CLOSE signal specifically, we should allow it.
                    # But our signals are usually BUY/SELL.
                    if signal_data.get("metadata", {}).get("panic_close"):
                        direction_allowed = True # ALWAYS allow panic exit
                    else:
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
                            # EXCEPTION: Panic Close ignores this
                            if not signal_data.get("metadata", {}).get("panic_close"):
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
        
        # 5. Calculate Progress, Conditions AND Threshold Comparisons + Signal Scoring (STORY-004)
        progress = {}
        conditions = {}
        thresholds = {}
        for strat in active_strategies:
            try:
                progress[strat.name] = strat.calculate_progress(df, extra_data=extra_data)
                
                if hasattr(strat, "check_conditions"):
                    conditions[strat.name] = strat.check_conditions(df, extra_data=extra_data)
                else:
                    conditions[strat.name] = []
                
                if hasattr(strat, "get_threshold_comparisons"):
                    thresholds[strat.name] = strat.get_threshold_comparisons(df, extra_data=extra_data)
                else:
                    thresholds[strat.name] = {}
            except Exception as e:
                progress[strat.name] = 0
                conditions[strat.name] = []
                thresholds[strat.name] = {}

        # Add basic scoring to signals (higher = better)
        for signal in signals:
            score = 50  # base
            if signal.get("confidence"):
                score += int(signal.get("confidence", 0))
            if "strong" in str(signal).lower():
                score += 20
            signal["score"] = score

        # Sort signals by score descending
        signals.sort(key=lambda s: s.get("score", 0), reverse=True)

        # === CAPTURE FULL MARKET SNAPSHOT ===
        # Calculate BB for snapshot
        try:
            sma_20 = df['close'].rolling(window=20).mean().iloc[-1]
            std_20 = df['close'].rolling(window=20).std().iloc[-1]
            bb_upper = sma_20 + (std_20 * 2)
            bb_lower = sma_20 - (std_20 * 2)
            bb_width = ((bb_upper - bb_lower) / sma_20) * 100 if sma_20 > 0 else 0
        except:
            sma_20 = bb_upper = bb_lower = bb_width = 0
        
        # Volume ratio
        try:
            # FIX: Use closed candle for volume ratio context (avoid 0% at open)
            avg_volume = df['volume'].iloc[:-1].rolling(50).mean().iloc[-1]
            current_volume = df['volume'].iloc[-2]
            volume_ratio = (current_volume / avg_volume) * 100 if avg_volume > 0 else 100
        except:
            volume_ratio = 100

        return {
            "regime": regime,
            "adx": current_adx,
            "adx_slope": adx_slope,
            "rsi": rsi_series.iloc[-1],
            "ema_9": ema_9.iloc[-1],
            "ema_20": ema_20.iloc[-1],
            "ema_50": ema_50.iloc[-1],
            "sma_20": sma_20,
            "bb_upper": bb_upper,
            "bb_lower": bb_lower,
            "bb_width": bb_width,
            "volume_ratio": volume_ratio,
            "current_price": df['close'].iloc[-1],
            "strategies": [s.name for s in active_strategies],
            "progress": progress,
            "conditions": conditions,
            "thresholds": thresholds,
            "signals": signals
        }
