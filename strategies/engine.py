
from app.services.indicators import ta
import pandas as pd
from app.core.config import config
from app.core.risk_manager import RiskManager
from strategies.base import BaseStrategy
from strategies.elastic_reversion import ElasticReversionStrategy
from strategies.scalp_ema_rsi import ScalpEmaRsi
from strategies.supertrend import StrategySupertrend
from strategies.meme_hunter import StrategyMemeHunter
from strategies.meme_breakout_retest import StrategyMemeBreakoutRetest
from strategies.meme_range_funding_oi import StrategyMemeRangeFundingOi

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
            "scalp_ema_rsi": ScalpEmaRsi(strats_config.get("scalp_ema_rsi")),
            "elastic_reversion": ElasticReversionStrategy(strats_config.get("elastic_reversion")),
            "supertrend": StrategySupertrend(strats_config.get("supertrend")),
            "meme_hunter": StrategyMemeHunter(strats_config.get("meme_hunter")),
            "meme_breakout_retest": StrategyMemeBreakoutRetest(strats_config.get("meme_breakout_retest")),
            "meme_range_funding_oi": StrategyMemeRangeFundingOi(strats_config.get("meme_range_funding_oi")),
        }

        # 🔧 FIX: Enforce strategy names to match config keys (snake_case)
        # This prevents mismatches between "ScalpEmaRsi" (Class) and "scalp_ema_rsi" (Config)
        for key, strategy in self.strategies.items():
            if strategy:
                strategy.name = key

        # De-duplicate repetitive rejection logs (same strategy, same candle, same reason)
        self._last_rejection_log = {}

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
            if not isinstance(params, dict): continue
            if not params.get("enabled"): continue
            
            strat_type = params.get("type", "")
            
            if name not in self.strategies:
                continue

            # ALWAYS ACTIVE strategies (Sniper, MemeHunter, etc.)
            if strat_type in ["sniper", "scalp_choc", "always_active"]: 
                active_strategies.append(self.strategies[name])
                continue # Already added

            # REGIME-BASED strategies
            if (regime == "TREND" or regime == "TREND_BEAR_STRONG") and strat_type == "trend":
                active_strategies.append(self.strategies[name])
                
            elif regime == "RANGE":
                if strat_type == "range" or strat_type == "reversion":
                    active_strategies.append(self.strategies[name])

        # Log active strategies
        if active_strategies:
            strat_names = ", ".join([s.name for s in active_strategies])
            print(f"[BOT] 🎯 Stratégies actives > {strat_names}")

        # 4. Generate Signals
        signals = []
        for strat in active_strategies:
            # Reset per-run strategy diagnostic reason
            if hasattr(strat, "last_rejection_reason"):
                strat.last_rejection_reason = None
            
            # --- PANIC CLOSE / KILL SWITCH ---
            try:
                should_panic, panic_reason = should_panic_close(strat.name, df, regime=regime)
                if should_panic:
                    # print(f"🚨 KILL SWITCH: {strat.name} BLOCKED - {panic_reason}")
                    continue  
            except Exception as e:
                print(f"⚠️ Panic check error: {e}")
            
            # Normal Signal Generation
            try:
                sig = strat.generate_signal(df, extra_data=extra_data)
            except Exception as e:
                print(f"⚠️ Strategy {strat.name} crashed during signal generation: {e}")
                continue
            
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
                    signal_data["price"] = float(sig.get("price", df['close'].iloc[-1]))
                    signal_data["timestamp"] = str(df.index[-1])
                    if is_manual:
                        signal_data["manual_approval"] = True
                    
                    # Ensure numeric fields in rich object are serializable
                    for key in ["sl", "tp", "confidence", "score"]:
                        if key in signal_data and signal_data[key] is not None:
                            try:
                                signal_data[key] = float(signal_data[key])
                            except:
                                pass
                else:
                    # Legacy string return
                    signal_data = {
                        "strategy": strat.name,
                        "signal": sig, 
                        "symbol": symbol or "UNKNOWN",
                        "price": float(df['close'].iloc[-1]),
                        "timestamp": str(df.index[-1])
                    }
                
                # --- GLOBAL DIRECTION FILTER ---
                signal_type = signal_data.get("signal", "").upper()
                allow_longs = params.get("allow_longs", True) 
                allow_shorts = params.get("allow_shorts", True)
                
                direction_allowed = True
                rejection_reason = ""

                if signal_type == "BUY" and not allow_longs:
                    direction_allowed = False
                    rejection_reason = "Longs disabled"
                elif signal_type == "SELL" and not allow_shorts:
                    if signal_data.get("metadata", {}).get("panic_close"):
                        direction_allowed = True 
                    else:
                        direction_allowed = False
                        rejection_reason = "Shorts disabled"
                
                # --- NEW: ANTI-CHASING FILTER (Bollinger Bands) ---
                if direction_allowed:
                    # 🔧 TEST MODE BYPASS: If strategy has test_mode=True, skip BB anti-chasing
                    is_test_mode = params.get("test_mode", False)
                    
                    if not is_test_mode:
                        try:
                            sma_20_val = float(df['close'].rolling(window=20).mean().iloc[-1])
                            std_20_val = float(df['close'].rolling(window=20).std().iloc[-1])
                            bb_upper_val = sma_20_val + (std_20_val * 2)
                            bb_lower_val = sma_20_val - (std_20_val * 2)
                            curr_close = float(df['close'].iloc[-1])
                            
                            if signal_type == "SELL":
                                if not signal_data.get("metadata", {}).get("panic_close"):
                                    if curr_close <= (bb_lower_val * 1.01):
                                        direction_allowed = False
                                        rejection_reason = "Price too close to lower Bollinger band (support)"
                                    
                            elif signal_type == "BUY":
                                if curr_close >= (bb_upper_val * 0.99):
                                    direction_allowed = False
                                    rejection_reason = "Price too close to upper Bollinger band (resistance)"
                        except Exception as e:
                            pass

                if direction_allowed:
                    if is_manual:
                        signal_data["manual_approval"] = True
                    signals.append(signal_data)
                else:
                    print(f"[BOT] 🚫 Signal rejected ({strat.name}/{signal_type}): {rejection_reason or 'Filtered by global guard'}")
            else:
                reason = getattr(strat, "last_rejection_reason", None)
                if reason:
                    try:
                        candle_ref = str(df.index[-2])
                    except Exception:
                        candle_ref = "n/a"
                    sig_key = f"{candle_ref}|{reason}"
                    if self._last_rejection_log.get(strat.name) != sig_key:
                        self._last_rejection_log[strat.name] = sig_key
                        print(f"[BOT] ⛔ No signal ({strat.name}): {reason}")


        # === CAPTURE FULL MARKET SNAPSHOT ===
        try:
            sma_20 = float(df['close'].rolling(window=20).mean().iloc[-1])
            std_20 = float(df['close'].rolling(window=20).std().iloc[-1])
            bb_upper = sma_20 + (std_20 * 2)
            bb_lower = sma_20 - (std_20 * 2)
            bb_width = ((bb_upper - bb_lower) / sma_20) * 100 if sma_20 > 0 else 0
        except:
            sma_20 = bb_upper = bb_lower = bb_width = 0
        
        try:
            avg_volume = float(df['volume'].iloc[:-1].rolling(50).mean().iloc[-1])
            current_volume = float(df['volume'].iloc[-2])
            volume_ratio = (current_volume / avg_volume) * 100 if avg_volume > 0 else 100
        except:
            volume_ratio = 100

        # Scoring Logic (Basic)
        for signal in signals:
            score = 50
            if signal.get("confidence"): score += int(signal.get("confidence", 0))
            signal["score"] = score
        signals.sort(key=lambda s: s.get("score", 0), reverse=True)

        # Coherent snapshot for logging/UI: use confirmed candle (-2) for all core metrics.
        # Live values are still exposed separately for debugging.
        return {
            "regime": regime,
            "adx": float(current_adx),
            "adx_slope": float(adx_slope),
            "rsi": float(rsi_series.iloc[-2]),
            "ema_9": float(ema_9.iloc[-2]),
            "ema_20": float(ema_20.iloc[-2]),
            "ema_50": float(ema_50.iloc[-2]),
            "sma_20": float(sma_20),
            "bb_upper": float(bb_upper),
            "bb_lower": float(bb_lower),
            "bb_width": float(bb_width),
            "volume_ratio": float(volume_ratio),
            "current_price": float(df['close'].iloc[-2]),
            "current_price_live": float(df['close'].iloc[-1]),
            "rsi_live": float(rsi_series.iloc[-1]),
            "ema_9_live": float(ema_9.iloc[-1]),
            "ema_20_live": float(ema_20.iloc[-1]),
            "ema_50_live": float(ema_50.iloc[-1]),
            "strategies": [s.name for s in active_strategies],
            "signals": signals
        }
