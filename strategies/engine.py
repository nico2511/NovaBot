from app.services.indicators import ta
import pandas as pd
from app.core.config import config
from app.core.risk_manager import RiskManager
from strategies.base import BaseStrategy
from strategies.elastic_reversion import ElasticReversionStrategy
from strategies.scalp_ema_rsi import ScalpEmaRsi
from strategies.institutional_scalp import InstitutionalScalp
from strategies.swing_trend_pullback import SwingTrendPullback
from strategies.day_trading_orb import DayTradingORB
from strategies.mean_reversion import MeanReversion
from strategies.smc_fvg import SMCFVG
from strategies.smart_trend import StrategySmartTrend
from strategies.macd_crossover import MACDCrossover
from strategies.volume_breakout import VolumeBreakout
from strategies.ema_bounce import EMABounce
from strategies.triple_ema import TripleEMA
from strategies.rsi_bollinger_bands import RBIReversion
from strategies.golden_cross import StrategyGoldenCross
from strategies.rsi_reversal import StrategyRSIReversal
from strategies.bollinger_breakout import StrategyBollingerBreakout
import json

class StrategyEngine:
    def __init__(self, risk_manager: RiskManager):
        self.risk_manager = risk_manager
        self.load_config()
        
        # Initialize strategies with their specific config
        strats_config = self.config.get("strategies", {})
        
        self.strategies = {
            # TREND strategies
            "scalp_ema_rsi": ScalpEmaRsi(strats_config.get("scalp_ema_rsi")),
            "institutional_scalp": InstitutionalScalp(strats_config.get("institutional_scalp")),
            "smart_trend": StrategySmartTrend(strats_config.get("smart_trend")),
            "golden_cross": StrategyGoldenCross(strats_config.get("golden_cross")),
            # "triangle_breakout": None, # Placeholder/ToDo
            # "head_shoulders": None, # Placeholder/ToDo
            "macd_crossover": MACDCrossover(strats_config.get("macd_crossover")),
            "triple_ema": TripleEMA(strats_config.get("triple_ema")),
            
            # RANGE strategies
            "rsi_reversal": StrategyRSIReversal(strats_config.get("rsi_reversal")),
            "bollinger_breakout": StrategyBollingerBreakout(strats_config.get("bollinger_breakout")),
            "rsi_bb": RBIReversion(strats_config.get("rsi_bb")),
            
            # SCALP/MOMENTUM
            "ema_bounce": EMABounce(strats_config.get("ema_bounce")),
            "volume_breakout": VolumeBreakout(strats_config.get("volume_breakout")),

            # MEAN REVERSION
            "elastic_reversion": ElasticReversionStrategy(strats_config.get("elastic_reversion"))
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
        # To be in TREND, we need ADX > Threshold AND Slope >= -1 (Not crashing)
        # Ideally Slope > 0 (Strengthening)
        
        if current_adx > threshold and adx_slope >= -1:
            regime = "TREND"
        else:
            regime = "RANGE"
            
        # Log if trend rejected due to slope
        # if current_adx > threshold and adx_slope < -1:
        #     print(f"📉 Trend Rejected: ADX {current_adx} but Slope {adx_slope:.2f}")

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
                    if is_manual:
                        signal_data["manual_approval"] = True
                    signals.append(signal_data)
        
        # 5. Calculate Progress for each active strategy
        progress = {}
        for strat in active_strategies:
            try:
                progress[strat.name] = strat.calculate_progress(df, extra_data=extra_data)
            except Exception as e:
                print(f"Error calculating progress for {strat.name}: {e}")
                progress[strat.name] = 0

        return {
            "regime": regime,
            "regime": regime,
            "adx": current_adx,
            "rsi": rsi_series.iloc[-1],
            "ema_20": ema_20.iloc[-1],
            "ema_50": ema_50.iloc[-1],
            "strategies": [s.name for s in active_strategies],
            "progress": progress,
            "signals": signals
        }
