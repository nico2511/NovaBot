from app.services.indicators import ta
import pandas as pd
from app.core.config import config
from app.core.risk_manager import RiskManager
from strategies.definitions import *
import json

class StrategyEngine:
    def __init__(self, risk_manager: RiskManager):
        self.risk_manager = risk_manager
        self.load_config()
        
        # Initialize strategies with their specific config
        strats_config = self.config.get("strategies", {})
        
        self.strategies = {
            "scalp_ema_rsi": ScalpEmaRsi(strats_config.get("scalp_ema_rsi")),
            "institutional_scalp": InstitutionalScalp(strats_config.get("institutional_scalp")),
            "smart_trend": StrategySmartTrend(strats_config.get("smart_trend")),
            "double_top_bottom": StrategyDoubleTopBottom(strats_config.get("double_top_bottom")),
            "triangle_breakout": StrategyTriangleBreakout(strats_config.get("triangle_breakout")),
            "head_shoulders": StrategyHeadShoulders(strats_config.get("head_shoulders"))
        }

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
        current_adx = adx_res['ADX'].iloc[-1]
        
        # Add to df for strategies to use if needed
        # Strategies typically use df.ta... we need to check definitions.py too to ensure they don't break
        # But for now let's ensure engine works
        df['ADX_14'] = adx_res['ADX']

        threshold = self.config.get("market_regime", {}).get("adx_threshold", 25)
        
        regime = "TREND" if current_adx > threshold else "RANGE"
        
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
                if isinstance(sig, dict):
                    # Strategy returned rich object
                    signal_data = sig
                    signal_data["strategy"] = strat.name
                    signal_data["price"] = sig.get("price", df['close'].iloc[-1])
                    signal_data["timestamp"] = df.index[-1]
                    signals.append(signal_data)
                else:
                    # Legacy string return
                    signal_data = {
                        "strategy": strat.name,
                        "signal": sig, 
                        "price": df['close'].iloc[-1],
                        "timestamp": df.index[-1]
                    }
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
            "adx": current_adx,
            "strategies": [s.name for s in active_strategies],
            "progress": progress,
            "signals": signals
        }
