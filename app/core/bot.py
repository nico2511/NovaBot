
"""
Core Bot Logic Module
Contains the central BotContext class that manages the trading loop, state, and services.
"""
import sys
import os
import threading
import time
import asyncio
import json
import pandas as pd
from collections import deque

# Root Directory Logic
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import config
from app.core.risk_manager import RiskManager
from app.core.constants import *
from app.core.state_manager import StateManager
from app.services.hyperliquid_service import hyperliquid_service
from app.services.discord_service import discord_service
from app.core.trade_recorder import TradeRecorder
from strategies.engine import StrategyEngine
from app.services.ia import ia_service
from app.services.indicators import Indicators
from app.utils.data_processing import get_dynamic_context

# Hardening Phase 0
from app.services.safe_order_manager import SafeOrderManager
from app.services.position_reconciler import PositionReconciler
from app.services.storage import storage_service

class BotContext:
    """Main bot context"""
    def __init__(self):
        print("\n\n🤖 [BOOT] BotContext v1.1.0 (Refactored Core)\n")
        
        # Thread Safety Lock
        self.trade_lock = threading.Lock()
        
        self.risk_manager = RiskManager(
            max_positions=config.DEFAULT_MAX_POSITIONS,
            daily_stop_loss=config.DEFAULT_DAILY_STOP_LOSS
        )
        # GLOBAL QUOTA - Will be set from global_settings after initialization
        self.max_positions = config.DEFAULT_MAX_POSITIONS
        self.strategy_engine = StrategyEngine(self.risk_manager)
        self.is_running = False
        self.trading_enabled = False
        self.thread = None
        self.account_value = 0.0
        
        # Multi-Position Support: Dictionary indexed by symbol
        # MUST be initialized BEFORE any property access (like self.latest_data)
        self.active_symbol = config.TRADING_SYMBOL  # Must be set before latest_data
        self.active_trades = {}  # { "HYPE": {...trade_data...}, "ETH": {...} }
        self.latest_data_map = {}  # { "HYPE": DataFrame, "ETH": DataFrame }
        
        self.latest_data = pd.DataFrame()
        self.latest_analysis = {}
        self.signals_log = deque(maxlen=200)
        self.logs = deque(maxlen=1000)
        self.latest_strategy_result = {}
        self.last_candle_time = None
        
        self.trading_enabled = config.AUTO_START_TRADING  # Respect "Auto-start Trading on Bot Launch"
        self.is_running = False      # Loop Switch
        self.active_strategy_name = "SmartTrend"
        self.active_strategies = []

        # Scanner Settings defaults
        # Scanner Settings defaults (Seeded from user_settings API via config)
        self.scanner_settings = {
            "enabled": config.SCANNER_ENABLED,
            "interval": config.SCANNER_INTERVAL,
            "min_score": config.SCANNER_MIN_SCORE,
            "auto_switch": config.SCANNER_AUTO_SWITCH
        }

        # Global Settings Defaults (Seeded from user_settings API via config)
        self.global_settings = {
            "operations": {
                "trading_timeframe": config.TRADING_TIMEFRAME,
                "auto_start_trading": config.AUTO_START_TRADING,
                "log_level": config.LOG_LEVEL
            },
            "risk_defaults": {
                "max_positions": config.DEFAULT_MAX_POSITIONS,
                "daily_stop_loss": config.DEFAULT_DAILY_STOP_LOSS,
                "bot_persona": config.BOT_PERSONA,
                "risk_profile": config.RISK_PROFILE,
                "default_leverage": config.DEFAULT_LEVERAGE,
                "default_margin_type": "ISOLATED",
                "available_personas": ["Conservative Scalper", "Aggressive Day Trader", "Sniper"],
                "available_risk_profiles": ["Capital Preservation First", "Balanced Growth", "High Volatility Hunter"]
            },
            "ai_config": {
                "conf_threshold_high": config.AI_CONF_THRESHOLD_HIGH,
                "conf_threshold_medium": config.AI_CONF_THRESHOLD_MEDIUM,
                "conf_threshold_low": config.AI_CONF_THRESHOLD_LOW,
                "model_name": config.AI_MODEL_NAME,
                "call_cooldown": config.AI_CALL_COOLDOWN
            },
            "notifications": {
                "discord_webhook_alerts": config.DISCORD_WEBHOOK_ALERTS,
                "discord_webhook_logs": config.DISCORD_WEBHOOK_LOGS
            }
        }
        
        # AI Commentary Cache
        self.ai_cache = {
            "last_market_analysis": None,
            "last_market_analysis_time": None,
            "last_position_analysis": None,
            "last_position_analysis_time": None,
            "signal_analyses": deque(maxlen=50),
            "market_snapshots": deque(maxlen=10)
        }
        
        # Startup synchronization flags
        self.startup_sync_done = False
        
        # Periodic Reporting Timers
        self._last_copilot_report_time = time.time()
        self._copilot_report_interval = 600  # 10 minutes
        self._initial_position_analyzed = False
        
        # Candle analysis cache
        self.last_analyzed_candle = None
        
        # Thread health monitoring (heartbeat)
        self._loop_heartbeat = 0  # Timestamp of last trading loop tick
        
        # SL/TP Sync Cooldown (prevent infinite loop)
        self._last_sltp_sync_time = None
        self._sltp_sync_cooldown = 60  # Wait 60s after sync before re-verifying
        
        # AI Call Management
        self.last_ai_call = 0 
        self.ai_call_cooldown = config.AI_CALL_COOLDOWN 
        
        # Leverage state
        self._leverage_synced = False 
        
        # Sync Timers
        self._last_state_sync_time = 0
        self._state_sync_interval = 10  # Seconds
        self._last_pnl_sync = 0  # To track daily PnL sync
        
        # Execution Mode
        self.execution_mode = os.getenv("EXECUTION_MODE", "Live") # Default to Live
        
        # Cooldown tracking (anti-overtrading)
        self._last_trade_info = {"symbol": None, "direction": None, "time": None}
        
        # Open Interest History (InMemory)
        self.oi_history = deque(maxlen=2000) 
        
        # Data Persistence (Core)
        self.trade_recorder = TradeRecorder()
        self.latest_analysis = {}
        
        # Phase 0 Hardening Services
        self.safe_order_manager = SafeOrderManager(hyperliquid_service)
        # Position Reconciler - Set reference to self for adoption check
        self.position_reconciler = PositionReconciler(hyperliquid_service, self.safe_order_manager)
        self.position_reconciler.bot_context = self
        

        self.signal_analysis_file = os.path.abspath(os.path.join(BASE_DIR, "data", "analysis", "signal_analysis.json"))
        self._ensure_data_dir()
        
        # Load persisted state
        try:
            state = StateManager.load_state(self)
            
            # Load trading params from global_settings (centralized source)
            requested_max = self.global_settings.get("risk_defaults", {}).get("max_positions", 1)
            
            self.max_positions = requested_max
            self.add_log(f"⚙️ Max positions: {self.max_positions}")
                    
        except Exception as e:
            print(f"Error loading state: {e}")
            
        # Initialize Services
        self.trade_recorder = TradeRecorder()
        self.latest_analysis = {}

    def add_log(self, message: str, metadata: dict = None):
        """Add log message with optional metadata"""
        timestamp = pd.Timestamp.now().strftime('%H:%M:%S')
        
        # Store structured entry for API/Frontend
        structured_entry = {
            "timestamp": timestamp,
            "message": message,
            "metadata": metadata
        }
        self.logs.append(structured_entry)
        
        # String representation for Console/File
        log_str = f"{timestamp} {message}"
        print(f"[BOT] {message}")
        if metadata:
            print(f"   >>> Metadata: {metadata}")
            
        try:
            with open("bot_activity.log", "a", encoding="utf-8") as f:
                f.write(f"{log_str}\n")
        except Exception as e:
            print(f"⚠️ Log write error: {e}")

    def switch_active_symbol(self, new_symbol: str):
        """Securely switch active symbol and update WebSocket subscription"""
        if self.active_symbol == new_symbol:
            return

        old_symbol = self.active_symbol
        self.add_log(f"🔄 Switching active symbol from {old_symbol} to {new_symbol}")
        
        # Multi-Position: No need to clear trades when switching symbols
        # Each symbol maintains its own trade state in active_trades dict
        
        self.active_symbol = new_symbol
        
        try:
            if hyperliquid_service.ws_manager:
                hyperliquid_service.ws_manager.add_symbol(new_symbol)
        except Exception as e:
            self.add_log(f"⚠️ Failed to update WebSocket subscription: {e}")
        
        StateManager.save_state(self)

    # ==========================================
    # BACKWARD COMPATIBILITY LAYER
    # ==========================================
    @property
    def active_trade(self):
        """Backward compatibility: Returns trade for active_symbol"""
        return self.active_trades.get(self.active_symbol)
    
    @active_trade.setter
    def active_trade(self, value):
        """Backward compatibility: Sets trade for active_symbol"""
        if value is None:
            self.active_trades.pop(self.active_symbol, None)
        else:
            self.active_trades[self.active_symbol] = value
    
    @property
    def latest_data(self):
        """Backward compatibility: Returns data for active_symbol"""
        return self.latest_data_map.get(self.active_symbol, pd.DataFrame())
    
    @latest_data.setter
    def latest_data(self, value):
        """Backward compatibility: Sets data for active_symbol"""
        self.latest_data_map[self.active_symbol] = value

    @property
    def copilot_sentiment(self) -> str:
        """Returns the latest market sentiment from Copilot analysis"""
        cache = self.ai_cache.get("last_market_analysis")
        if not cache:
            return "N/A (No analysis yet)"
        
        # New structure: cache is a dict of timeframes
        if isinstance(cache, dict) and "1h" in cache:
            parts = []
            for tf in ["5m", "1h", "4h"]:
                s = cache.get(tf, {})
                sentiment = s.get('sentiment', 'N/A')
                score = s.get('score', 0)
                parts.append(f"{tf}: {sentiment} ({score})")
            return " | ".join(parts)
        
        return "N/A (Analysis pending)"

    def _prepare_ai_context(self, position_data: dict = None) -> dict:
        """Prepare comprehensive market context for professional AI analysis"""
        if not hasattr(self, 'latest_data') or self.latest_data.empty:
            return {}
        
        df = self.latest_data
        current_price = float(df['close'].iloc[-1])
        
        # Technical Indicators
        rsi = float(df['RSI_14'].iloc[-1]) if 'RSI_14' in df.columns else 0.0
        atr = float(df['ATRr_14'].iloc[-1]) if 'ATRr_14' in df.columns else 0.0
        
        # EMAs
        ema_20 = float(df['close'].ewm(span=20).mean().iloc[-1])
        ema_50 = float(df['close'].ewm(span=50).mean().iloc[-1])
        ema_200 = float(df['close'].ewm(span=200).mean().iloc[-1]) if len(df) >= 200 else None
        
        # Price levels
        swing_high = float(df['high'].rolling(20).max().iloc[-1])
        swing_low = float(df['low'].rolling(20).min().iloc[-1])
        
        # Volume
        avg_volume = float(df['volume'].rolling(50).mean().iloc[-1])
        current_volume = float(df['volume'].iloc[-1])
        volume_ratio = (current_volume / avg_volume) * 100 if avg_volume > 0 else 100
        
        # Volatility percentile
        volatility_percentile = None
        if atr and 'ATRr_14' in df.columns:
            atr_series = df['ATRr_14'].dropna()
            if len(atr_series) > 0:
                volatility_percentile = int((atr_series < atr).sum() / len(atr_series) * 100)
        
        # Custom ADX Calculation for Regime
        adx_value = 0
        try:
            adx_df = Indicators.adx(df['high'], df['low'], df['close'], 14)
            adx_value = float(adx_df['ADX'].iloc[-1])
        except Exception:
            pass
            
        # === ENHANCED CONTEXT: MACD ===
        macd_line = 0
        macd_signal = 0
        macd_hist = 0
        try:
             macd_df = Indicators.macd(df['close'])
             macd_line = float(macd_df['MACD'].iloc[-1])
             macd_signal = float(macd_df['MACDs'].iloc[-1])
             macd_hist = float(macd_df['MACDh'].iloc[-1])
        except Exception: 
            pass

        # FIX: Regime definition aligned with Architecture (ADX > 25 = TREND)
        regime = "TREND" if adx_value > 25 else "RANGE"
        
        # Market Bias maintained via EMA alignment
        market_bias = "BULLISH" if ema_20 > ema_50 else "BEARISH"
        
        # Add ADX and MACD to dynamic context
        dynamic_ctx = get_dynamic_context(df)
        dynamic_ctx['adx'] = round(float(adx_value or 0), 2)
        dynamic_ctx['macd_line'] = round(float(macd_line or 0), 4)
        dynamic_ctx['macd_signal'] = round(float(macd_signal or 0), 4)
        dynamic_ctx['macd_hist'] = round(float(macd_hist or 0), 4)
        
        # === ENHANCED CONTEXT: Bollinger Bands ===
        bb_period = 20
        bb_std = 2.0
        try:
            bb_middle = df['close'].rolling(bb_period).mean().iloc[-1]
            bb_std_val = df['close'].rolling(bb_period).std().iloc[-1]
            bb_upper = bb_middle + (bb_std * bb_std_val)
            bb_lower = bb_middle - (bb_std * bb_std_val)
            
            # BB Position
            if current_price > bb_upper:
                bb_position = "ABOVE_UPPER"
            elif current_price < bb_lower:
                bb_position = "BELOW_LOWER"
            elif abs(current_price - bb_middle) / bb_middle < 0.005:  # Within 0.5% of middle
                bb_position = "AT_MIDDLE"
            else:
                bb_position = "INSIDE_BANDS"
            
            # BB Width (volatility indicator)
            bb_width = ((bb_upper - bb_lower) / bb_middle) * 100 if bb_middle > 0 else 0
            
            dynamic_ctx['bb_upper'] = round(float(bb_upper or 0), 4)
            dynamic_ctx['bb_middle'] = round(float(bb_middle or 0), 4)
            dynamic_ctx['bb_lower'] = round(float(bb_lower or 0), 4)
            dynamic_ctx['bb_position'] = bb_position
            dynamic_ctx['bb_width'] = round(float(bb_width or 0), 2)
        except Exception:
            pass
        
        # === ENHANCED CONTEXT: EMA Slopes ===
        try:
            # Calculate EMA slopes (current vs previous candle)
            ema_20_prev = float(df['close'].ewm(span=20).mean().iloc[-2])
            ema_50_prev = float(df['close'].ewm(span=50).mean().iloc[-2])
            
            ema_20_slope = ((ema_20 - ema_20_prev) / ema_20_prev) if ema_20_prev > 0 else 0
            ema_50_slope = ((ema_50 - ema_50_prev) / ema_50_prev) if ema_50_prev > 0 else 0
            
            dynamic_ctx['ema_20_slope'] = round(ema_20_slope, 6)
            dynamic_ctx['ema_50_slope'] = round(ema_50_slope, 6)
            
            # Slope labels
            if abs(ema_50_slope) < 0.0001:
                dynamic_ctx['ema_50_slope_label'] = "FLAT"
            elif ema_50_slope > 0.0005:
                dynamic_ctx['ema_50_slope_label'] = "RISING"
            elif ema_50_slope < -0.0005:
                dynamic_ctx['ema_50_slope_label'] = "FALLING"
            else:
                dynamic_ctx['ema_50_slope_label'] = "NEUTRAL"
        except Exception:
            pass
        
        # === ENHANCED CONTEXT: Fibonacci Levels ===
        try:
            # Calculate Fibonacci retracement levels from swing high/low
            if swing_high and swing_low and swing_high > swing_low:
                swing_range = swing_high - swing_low
                
                # Key Fibonacci levels
                fib_236 = swing_low + (swing_range * 0.236)
                fib_382 = swing_low + (swing_range * 0.382)
                fib_50 = swing_low + (swing_range * 0.50)
                fib_618 = swing_low + (swing_range * 0.618)
                fib_786 = swing_low + (swing_range * 0.786)
                
                # Determine which Fibo zone price is in
                fib_zone = "UNKNOWN"
                if current_price >= fib_786:
                    fib_zone = "ABOVE_78.6%"
                elif current_price >= fib_618:
                    fib_zone = "GOLDEN_ZONE (61.8-78.6%)"
                elif current_price >= fib_50:
                    fib_zone = "MID_ZONE (50-61.8%)"
                elif current_price >= fib_382:
                    fib_zone = "LOWER_ZONE (38.2-50%)"
                elif current_price >= fib_236:
                    fib_zone = "SHALLOW (23.6-38.2%)"
                else:
                    fib_zone = "BELOW_23.6%"
                
                dynamic_ctx['fib_236'] = round(fib_236, 4)
                dynamic_ctx['fib_382'] = round(fib_382, 4)
                dynamic_ctx['fib_50'] = round(fib_50, 4)
                dynamic_ctx['fib_618'] = round(fib_618, 4)
                dynamic_ctx['fib_786'] = round(fib_786, 4)
                dynamic_ctx['fib_zone'] = fib_zone
                dynamic_ctx['swing_range'] = round(swing_range, 4)
        except Exception:
            pass
        
        # Position-specific data
        pnl_percent = 0
        time_in_trade = None
        sl_distance = None
        tp_distance = None
        rr_ratio = None
        
        if position_data:
            entry = position_data.get('entry_price') if isinstance(position_data, dict) else position_data
            if entry is None:
                entry = position_data.get('entry') if isinstance(position_data, dict) else current_price
            
            try:
                entry = float(entry) if entry else current_price
            except (TypeError, ValueError):
                entry = current_price
            
            side = position_data.get('side', 'BUY') if isinstance(position_data, dict) else 'BUY'
            
            if side == 'BUY':
                pnl_percent = ((current_price - entry) / entry) * 100
            else:
                pnl_percent = ((entry - current_price) / entry) * 100
            
            if isinstance(position_data, dict) and 'timestamp' in position_data:
                entry_time = pd.Timestamp(position_data['timestamp'])
                time_in_trade = str(pd.Timestamp.now() - entry_time).split('.')[0]
            
            if isinstance(position_data, dict):
                if 'sl' in position_data and position_data['sl']:
                    try:
                        sl_val = float(position_data['sl'])
                        sl_distance = abs((sl_val - entry) / entry) * 100
                    except (TypeError, ValueError): pass
                if 'tp' in position_data and position_data['tp']:
                    try:
                        tp_val = float(position_data['tp'])
                        tp_distance = abs((tp_val - entry) / entry) * 100
                    except (TypeError, ValueError): pass
            
            if sl_distance and tp_distance and sl_distance > 0:
                rr_ratio = round(tp_distance / sl_distance, 2)
        
        # === ENHANCED CONTEXT: Open Interest & Funding ===
        funding_rate = 0.0
        try:
            funding_rate = hyperliquid_service.get_funding_rate(self.active_symbol)
        except Exception: pass
            
        # Extract OI Metrics calculated in trading_loop
        oi_change_pct = float(df['OI_Change_Pct'].iloc[-1]) if 'OI_Change_Pct' in df.columns else 0.0
        oi_divergence = float(df['OI_Divergence'].iloc[-1]) if 'OI_Divergence' in df.columns else 0.0
        oi_vs_ma = float(df['OI_vs_MA'].iloc[-1]) if 'OI_vs_MA' in df.columns else 0.0
        
        return {
            "symbol": self.active_symbol,
            "current_price": current_price,
            "regime": regime,
            "market_bias": market_bias,
            "rsi": rsi,
            "atr": atr,
            "volatility_percentile": volatility_percentile,
            "ema_20": ema_20,
            "ema_50": ema_50,
            "ema_200": ema_200,
            "ema20_distance": round(((current_price - ema_20) / ema_20) * 100, 2),
            "ema50_distance": round(((current_price - ema_50) / ema_50) * 100, 2),
            "swing_high": swing_high,
            "swing_low": swing_low,
            "current_volume": current_volume,
            "avg_volume": avg_volume,
            "volume_ratio": round(volume_ratio, 1),
            "pnl_percent": round(pnl_percent, 2) if position_data else None,
            "time_in_trade": time_in_trade,
            "sl_distance": round(sl_distance, 2) if sl_distance else None,
            "tp_distance": round(tp_distance, 2) if tp_distance else None,
            "rr_ratio": rr_ratio,
            "recent_closes": df['close'].tail(20).tolist() if not df.empty else [],
            "open_interest": hyperliquid_service.get_open_interest(self.active_symbol),
            "funding_rate": funding_rate,
            "oi_change_15m": round(oi_change_pct, 4),
            "oi_divergence": round(oi_divergence, 4),
            "oi_sentiment": "ACCUMULATION" if oi_vs_ma > 1.05 and funding_rate > 0 else "DISTRIBUTION" if oi_vs_ma < 0.95 else "NEUTRAL",
            **dynamic_ctx
        }

    async def _update_market_analysis(self):
        """Disabled"""
        pass

    def _fetch_mtf_sentiment(self, symbol: str) -> str:
        """Disabled"""
        return "Multi-Timeframe Data Unavailable"

    def _ensure_data_dir(self):
        """Ensure data directory exists"""
        data_dir = os.path.dirname(self.signal_analysis_file)
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)

    def _record_signal_analysis(self, sig: dict, ai_data: dict, approved: bool, indicators: dict = None):
        """Record AI signal analysis to a persistent JSON file for audit trail."""
        try:
            # Base entry
            entry = {
                "timestamp": pd.Timestamp.now().isoformat(),
                "symbol": self.active_symbol,
                "direction": sig.get("signal"),
                "strategy": sig.get("strategy"),
                "approved": approved,
                "confidence": ai_data.get("confidence", 0),
                "reasoning": ai_data.get("reasoning", "No reasoning provided"),
                "risk_level": ai_data.get("risk_level", "UNKNOWN"),
                "risk_score": ai_data.get("risk_score"),
                "decisive_factors": ai_data.get("decisive_factors", []),
                "rejection_reason_category": ai_data.get("rejection_reason_category"),
                "market_price": sig.get("price"),
                "suggested_sl": ai_data.get("suggested_adjustments", {}).get("sl") or sig.get("sl"),
                "suggested_tp": ai_data.get("suggested_adjustments", {}).get("tp") or sig.get("tp")
            }
            
            # Enrich with market context for retrospective analysis
            try:
                # 1. Technical Indicators (Use explicit pass if available, else try simple extraction)
                if indicators:
                    entry["indicators"] = indicators
                elif not self.latest_data.empty:
                    last_row = self.latest_data.iloc[-1]
                    entry["indicators"] = {
                        "rsi": round(float(last_row.get("rsi", 0)), 2),
                        "adx": round(float(last_row.get("adx", 0)), 2),
                        "ema20": round(float(last_row.get("ema20", 0)), 6),
                        "ema50": round(float(last_row.get("ema50", 0)), 6),
                        "bb_upper": round(float(last_row.get("bb_upper", 0)), 6),
                        "bb_middle": round(float(last_row.get("bb_middle", 0)), 6),
                        "bb_lower": round(float(last_row.get("bb_lower", 0)), 6),
                        "volume_ratio": round(float(last_row.get("volume_ratio", 0)), 2),
                        "macd": round(float(last_row.get("macd", 0)), 6),
                        "macd_signal": round(float(last_row.get("macd_signal", 0)), 6),
                        "macd_hist": round(float(last_row.get("macd_hist", 0)), 6)
                    }
                
                # 2. Market Regime from latest_analysis
                if self.latest_analysis:
                    entry["regime"] = {
                        "type": self.latest_analysis.get("regime", "UNKNOWN"),
                        "bias": self.latest_analysis.get("bias", "NEUTRAL")
                    }
                
                # 3. Copilot Sentiment (from AI cache)
                if self.ai_cache.get("last_market_analysis"):
                    market_sentiment = self.ai_cache["last_market_analysis"]
                    entry["copilot_sentiment"] = {
                        "5m": {
                            "sentiment": market_sentiment.get("5m", {}).get("sentiment", "UNKNOWN"),
                            "score": market_sentiment.get("5m", {}).get("score", 0),
                            "rsi": market_sentiment.get("5m", {}).get("rsi", 0)
                        },
                        "1h": {
                            "sentiment": market_sentiment.get("1h", {}).get("sentiment", "UNKNOWN"),
                            "score": market_sentiment.get("1h", {}).get("score", 0),
                            "rsi": market_sentiment.get("1h", {}).get("rsi", 0),
                            "trend": market_sentiment.get("1h", {}).get("trend", "UNKNOWN")
                        },
                        "4h": {
                            "sentiment": market_sentiment.get("4h", {}).get("sentiment", "UNKNOWN"),
                            "score": market_sentiment.get("4h", {}).get("score", 0),
                            "rsi": market_sentiment.get("4h", {}).get("rsi", 0)
                        }
                    }
                
                # 4. Funding & OI if available (from latest market data fetch)
                try:
                    # Logic improved: Use the bot's own service (Sync)
                    entry["market_data"] = {
                        "funding_rate": hyperliquid_service.get_funding_rate(self.active_symbol),
                        "open_interest": hyperliquid_service.get_open_interest(self.active_symbol)
                    }
                except: pass
                
            except Exception as ctx_err:
                self.add_log(f"⚠️ Failed to enrich signal context: {ctx_err}")
            
            # Read existing or init new
            history = []
            data_dir = os.path.dirname(self.signal_analysis_file)
            if not os.path.exists(data_dir):
                os.makedirs(data_dir, exist_ok=True)
                
            if os.path.exists(self.signal_analysis_file):
                try:
                    with open(self.signal_analysis_file, "r") as f:
                        history = json.load(f)
                except: history = []
            
            history.append(entry)
            # Keep last 500 signals
            if len(history) > 500:
                history = history[-500:]
            
            with open(self.signal_analysis_file, "w") as f:
                json.dump(history, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
                
            self.add_log(f"💾 Signal Analysis saved to history ({'Approved' if approved else 'Rejected'}) with full market context")
        except Exception as e:
            self.add_log(f"⚠️ Failed to record signal analysis: {e}")


    def execute_entry_atomically(self, symbol: str, side: str, size: float, price: float = None, sl: float = None, tp: float = None, strategy: str = "Unknown", metadata: dict = None, entry_indicators: dict = None):
        """ATOMIC ENTRY FLOW (Unified v2) - Now captures entry indicators for analysis"""
        try:
            # 1. LIVE EXECUTION CHECK
            if not self.trading_enabled:
                self.add_log(f"⚠️ Signal ignored (Trading Disabled): {side} {symbol}")
                return { "status": "ignored", "reason": "Trading Disabled" }
            
            current_price = price if price else hyperliquid_service.get_current_price(symbol)
            
            # REAL EXECUTION
            real_positions = hyperliquid_service.get_positions()
            active_count = len([p for p in real_positions if float(p["size"]) > 0])
            
            if active_count >= self.max_positions:
                self.add_log(f"⛔ QUOTA EXCEEDED ({active_count}/{self.max_positions}). Entry aborted.")
                return False

            self.add_log(f"🔒 ATOMIC ENTRY START: {side} {symbol} ({size}) via {strategy}")
            self.add_log(f"🧹 Cleaning pre-trade orphans on {symbol}...")
            hyperliquid_service.cancel_all_orders(symbol)

            is_buy = (side == "BUY")
            result = hyperliquid_service.execute_order(
                symbol=symbol, is_buy=is_buy, quantity=size, price=price, sl_price=sl, tp_price=tp
            )
            
            if result.get("status") != "success":
                self.add_log(f"❌ Entry Failed: {result.get('message')}")
                return False

            self.add_log("⏳ Verifying Fill...")
            filled = False
            oid = "unknown"
            
            try:
                raw_res = result.get("result", {})
                statuses = raw_res.get("response", {}).get("data", {}).get("statuses", [])
                if statuses and isinstance(statuses[0], dict):
                     oid = statuses[0].get("oid") or statuses[0].get("filled", {}).get("oid") or oid
            except: pass

            for i in range(5):
                time.sleep(1)
                positions = hyperliquid_service.get_positions()
                pos = next((p for p in positions if p["symbol"] == symbol and float(p['size']) > 0), None)
                if pos:
                    filled = True
                    entry_px = float(pos['entry_price'])
                    self.add_log(f"✅ ENTRY CONFIRMED: {symbol} Size: {pos['size']} Entry: {entry_px}")
                    
                    with self.trade_lock:
                        # CRITICAL: Always sync active_symbol before setting active_trade
                        # otherwise the setter will use the WRONG key in active_trades
                        if self.active_symbol != symbol:
                            self.active_symbol = symbol
                            
                        self.active_trade = {
                            "symbol": symbol,
                            "side": side,
                            "entry": entry_px,
                            "sl": sl,
                            "tp": tp,
                            "strategy": strategy,
                            "timestamp": pd.Timestamp.now().isoformat(),
                            "size": float(pos['size']),
                            "leverage": float(pos.get("leverage", 1.0)),
                            "oid": oid,
                            "pnl": 0,
                            "max_pnl": 0,
                            "metadata": metadata or {},
                            "entry_indicators": entry_indicators or {}  # Market snapshot at entry
                        }
                        self.risk_manager.record_trade_open()
                        StateManager.save_state(self)
                        # Force Sync to ensure state consistency
                        self._sync_state(silent=False)

                    
                    discord_service.send_alert(
                        f"🚀 ENTERED {side} {symbol}",
                        f"Strategy: {strategy}\nEntry: {entry_px}\nSize: {pos['size']}\nSL: {sl}\nTP: {tp}\nOID: {oid}",
                        color="00FF00" if side == "BUY" else "FF0000"
                    )
                    break
            
            if not filled:
                self.add_log("⚠️ Order sent but position NOT confirmed after 5s.")
                return False
                
            return True

        except Exception as e:
            self.add_log(f"❌ ATOMIC ENTRY ERROR: {e}")
            return False

    def execute_exit_atomically(self, symbol: str, reason: str = "SIGNAL"):
        """ATOMIC EXIT FLOW (THE KILL SWITCH)"""
        # Verify position exists before attempting to close
        try:
            positions = hyperliquid_service.get_positions()
            position_exists = any(p.get("symbol") == symbol and float(p.get("size", 0)) > 0 for p in positions)
            
            if not position_exists:
                self.add_log(f"⚠️ Cannot close {symbol}: No open position found on exchange.")
                # CRITICAL: If the bot thinks we have a trade but exchange says no, CLEAN UP LOCAL MEMORY
                with self.trade_lock:
                    if symbol in self.active_trades:
                        self.add_log(f"🧹 Local memory sync: Removing 'ghost' trade for {symbol}")
                        self.active_trades.pop(symbol, None)
                        StateManager.save_state(self)
                return False
        except Exception as e:
            self.add_log(f"⚠️ Failed to verify position for {symbol}: {e}")
            # Continue anyway - let Hyperliquid API handle the error
            
        self.add_log(f"🔒 ATOMIC EXIT START: Closing {symbol} ({reason})")
        
        # Get position data BEFORE closing for accurate PnL calculation
        positions_before = hyperliquid_service.get_positions()
        position_data = next((p for p in positions_before if p["symbol"] == symbol), None)
        
        if not position_data:
            self.add_log(f"⚠️ No position data found for {symbol}, PnL calculation may be inaccurate")
        
        try:
            result = hyperliquid_service.close_position(symbol)
            
            if result.get("status") == "success":
                final_positions = hyperliquid_service.get_positions()
                remaining = next((p for p in final_positions if p["symbol"] == symbol), None)
                
                if not remaining or float(remaining["size"]) == 0:
                     self.add_log(f"✅ POSITION CLOSED: {symbol}")
                     self.add_log(f"🧹 Cleaning post-trade orphans on {symbol}...")
                     hyperliquid_service.cancel_all_orders(symbol)
                     
                     # Calculate PnL from position data (works for all positions)
                     pnl_usdc = 0
                     entry_price = 0
                     exit_price = hyperliquid_service.get_current_price(symbol)
                     size = 0
                     side = "BUY"
                     
                     if position_data:
                         # Use actual position data
                         entry_price = position_data.get("entry_price", 0)
                         size = position_data.get("size", 0)
                         side = position_data.get("side", "BUY")
                         
                         if side == "BUY":
                             pnl_usdc = (exit_price - entry_price) * size
                         else:
                             pnl_usdc = (entry_price - exit_price) * size
                     elif self.active_trade:
                         # Fallback to active_trade if position_data unavailable
                         entry_price = self.active_trade.get("entry", 0)
                         size = self.active_trade.get("size", 0)
                         side = self.active_trade.get("side", "BUY")
                         
                         if side == "BUY":
                             pnl_usdc = (exit_price - entry_price) * size
                         else:
                             pnl_usdc = (entry_price - exit_price) * size
                     
                     # Record trade
                     with self.trade_lock:
                         self.trade_recorder.add_trade({
                             "symbol": symbol,
                             "strategy": self.active_trade.get("strategy", "Manual") if self.active_trade else "Manual",
                             "side": side,
                             "entry_price": entry_price,
                             "exit_price": exit_price,
                             "size": size,
                             "pnl_usdc": pnl_usdc,
                             "exit_reason": reason,
                             "exit_time": pd.Timestamp.now().isoformat(),
                             "entry_indicators": self.active_trade.get("entry_indicators", {}) if self.active_trade else {}
                         })
                         
                         discord_service.send_alert(
                             f"🏁 TRADE CLOSED: {symbol}",
                             f"Reason: {reason}\nPnL: ${pnl_usdc:.2f}",
                             color="FFFF00"
                         )
                         self.risk_manager.record_trade_close(pnl_usdc)
                         
                         # Clear active_trade only if this was the active trade
                         if self.active_trade and self.active_trade.get("symbol") == symbol:
                             self.active_trade = None
                         
                         StateManager.save_state(self)
                         self._sync_state(silent=False)

                     return True
                else:
                    self.add_log(f"⚠️ Close appeared successful but position remains: {remaining['size']}")
                    return False
            else:
                self.add_log(f"❌ Exit Failed: {result.get('message')}")
                return False

        except Exception as e:
            self.add_log(f"❌ ATOMIC EXIT ERROR: {e}")
            return False

    def _check_hard_veto(self, signal: str, market_context: dict):
        """HARD VETO: Technical guardrails (RSI + Volume + ADX)."""
        try:
            price = market_context.get("current_price", 0)
            
            # 1. RSI Veto (Relaxed: 30 for SELL, 80 for BUY)
            rsi = market_context.get("rsi")
            if rsi is not None:
                if signal == "BUY" and rsi > 80:
                    return f"HARD VETO: RSI Overbought ({rsi:.1f} > 80) @ {price:.2f}"
                if signal == "SELL" and rsi < 30:
                    return f"HARD VETO: RSI Oversold ({rsi:.1f} < 30) @ {price:.2f}"

            # 2. ADX Extreme Veto (Trend Runaway Protection)
            adx = market_context.get("adx", 0)
            if adx is not None and adx > 55:
                return f"HARD VETO: ADX Extreme ({adx:.1f} > 55) - Trend runaway @ {price:.2f}"

            # 3. Volume Veto (Low Volume Warning)
            current_vol = market_context.get("current_volume")
            avg_vol = market_context.get("avg_volume")
            if current_vol and avg_vol and avg_vol > 0:
                vol_ratio = (current_vol / avg_vol) * 100
                if vol_ratio < 20:
                    return f"HARD VETO: Low Volume ({vol_ratio:.1f}% avg) @ {price:.2f}"
            
            return None
        except Exception as e:
            print(f"⚠️ Veto Check Error: {e}")
            return None
    def _verify_and_enforce_sl_tp(self, symbol: str, trade_data: dict, bypass_cooldown: bool = False):
        """Consolidated verification: Fetch Exchange Orders -> Compare -> Enforce if needed."""
        # GUARD: Only enforce if trading is ENABLED (Real Trading)
        if not self.trading_enabled:
             return

        # PREVENT SYSTEMATIC RECALIBRATION: Only enforce on initial adoption or explicit trailing/BE
        if not bypass_cooldown and trade_data.get("initial_sl_tp_set", False):
            return

        # COOLDOWN: Skip verification if we just synced (prevent infinite loop)
        if not bypass_cooldown and self._last_sltp_sync_time:
            elapsed = (pd.Timestamp.now() - self._last_sltp_sync_time).total_seconds()
            if elapsed < self._sltp_sync_cooldown:
                return  # Too soon, wait for cooldown

        try:
            open_orders = hyperliquid_service.info.open_orders(config.HL_ACCOUNT_ADDRESS)
            symbol_orders = [o for o in open_orders if o["coin"] == symbol]
            
            desired_sl = float(trade_data.get("sl", 0))
            desired_tp = float(trade_data.get("tp", 0))
            
            found_sl = False
            found_tp = False
            TOLERANCE = 0.005  # Increased from 0.001 to 0.5% to handle rounding differences
            
            for o in symbol_orders:
                # FIX: For trigger orders (SL/TP), use triggerPx (actual trigger), not limitPx (aggressive fill price)
                price = float(o.get("triggerPx") or o.get("limitPx", 0))
                if desired_sl > 0 and abs(price - desired_sl) / desired_sl < TOLERANCE:
                    found_sl = True
                if desired_tp > 0 and abs(price - desired_tp) / desired_tp < TOLERANCE:
                     found_tp = True
            
            needs_sync = False
            if desired_sl > 0 and not found_sl:
                self.add_log(f"⚠️ Audit: SL missing/mismatched on exchange (Target: {desired_sl:.4f}). Enforcing...")
                needs_sync = True
            if desired_tp > 0 and not found_tp:
                self.add_log(f"⚠️ Audit: TP missing/mismatched on exchange (Target: {desired_tp:.4f}). Enforcing...")
                needs_sync = True
                
            if needs_sync:
                hyperliquid_service.sync_sl_tp(
                    symbol, 
                    trade_data.get("side") == "BUY", 
                    float(trade_data.get("size", 0)), 
                    desired_sl, 
                    desired_tp
                )
                self.add_log("✅ Audit: SL/TP enforced via Sync.")
                self._last_sltp_sync_time = pd.Timestamp.now()  # Mark sync time for cooldown
                
        except Exception as e:
            self.add_log(f"⚠️ Error in _verify_and_enforce_sl_tp: {e}")


    def _update_trailing_stops(self, trade: dict, current_price: float) -> bool:
        """Check and update Smart Break-Even and Trailing Stops"""
        entry_price = trade.get("entry")
        tp_price = trade.get("tp")
        sl_price = trade.get("sl")
        side = trade.get("side")
        new_sl = None
        
        if entry_price and tp_price and sl_price:
            pnl_pct = ((current_price - entry_price) / entry_price) * 100 if side == "BUY" else ((entry_price - current_price) / entry_price) * 100
            
            if side == "BUY":
                total_dist = tp_price - entry_price
                current_dist = current_price - entry_price
                progress_pct = (current_dist / total_dist) * 100 if total_dist != 0 else 0
                
                # 1. Smart BE (Moved to 60% progress OR 1.2% pure profit, locks 0.2% profit with 0.3% buffer)
                if progress_pct > 60 or pnl_pct > 1.2:
                    be_price = entry_price * 1.002 # 0.2% profit (covers fees + buffer)
                    # Safety: Ensure current price is at least 0.3% away from new SL
                    if sl_price < be_price and current_price > (be_price * 1.003):
                        new_sl = be_price
                        self.add_log(f"🛡️ Smart BE: Progress {progress_pct:.1f}% / PnL {pnl_pct:.2f}%. Moving SL to {new_sl:.2f}")

                # 2. Trailing Profit (Locks 20% of gains at 65% progress)
                if progress_pct > 65:
                    secure_price = entry_price + (total_dist * 0.20)
                    if sl_price < secure_price:
                         new_sl = secure_price
                         self.add_log(f"🛡️ Trailing: >65% target. Locking 20% at {new_sl:.2f} (Price: {current_price:.2f})")

                # 3. Aggressive Lock (Locks 40% of gains)
                if progress_pct > 75:
                    lock_price = entry_price + (total_dist * 0.40)
                    if sl_price < lock_price:
                         new_sl = lock_price
                         self.add_log(f"🛡️ Trailing: >75% target. Locking 40% at {new_sl:.2f}")
                
            else: # SELL
                total_dist = entry_price - tp_price
                current_dist = entry_price - current_price
                progress_pct = (current_dist / total_dist) * 100 if total_dist != 0 else 0
                
                # 1. Smart BE (60% progress, 0.2% profit lock, 0.3% buffer)
                if progress_pct > 60:
                    be_price = entry_price * 0.998 # 0.2% profit
                    # Safety: Ensure current price is at least 0.3% away from new SL
                    if sl_price > be_price and current_price < (be_price * 0.997):
                        new_sl = be_price
                        self.add_log(f"🛡️ Smart BE: >60% target. Moving SL to {new_sl:.2f} (Price: {current_price:.2f})")

                # 2. Trailing Profit (65% progress)
                if progress_pct > 65:
                    secure_price = entry_price - (total_dist * 0.20)
                    if sl_price > secure_price:
                        new_sl = secure_price
                        self.add_log(f"🛡️ Trailing: >65% target. Locking 20% at {new_sl:.2f} (Price: {current_price:.2f})")
                        
                # 3. Aggressive Lock
                if progress_pct > 75:
                    lock_price = entry_price - (total_dist * 0.40)
                    if sl_price > lock_price:
                        new_sl = lock_price
                        self.add_log(f"🛡️ Trailing: >75% target. Locking 40% at {new_sl:.2f}")

            if new_sl:
                with self.trade_lock:
                    t_ref = self.active_trades.get(trade.get("symbol"))
                    if t_ref:
                        t_ref["sl"] = new_sl
                        StateManager.save_state(self)
                
                # Discord Notification for Break-Even
                discord_service.send_alert(
                    f"🛡️ BREAK-EVEN TRIGGERED: {trade.get('symbol', self.active_symbol)}",
                    f"New SL: {new_sl:.2f}\nCurrent Price: {current_price:.2f}\nEntry: {entry_price:.2f}",
                    color="FFA500"  # Orange
                )
                return True
                
        return False

    def _check_local_exits(self, trade: dict, symbol: str, current_price: float):
        """Check for local SL/TP triggers"""
        side = trade.get("side")
        sl_val = float(trade.get("sl") or 0)
        tp_val = float(trade.get("tp") or 0)
        
        exit_triggered = False
        reason = ""

        if side == "BUY":
            if sl_val > 0 and current_price <= sl_val:
                exit_triggered = True; reason = "STOP_LOSS"
            elif tp_val > 0 and current_price >= tp_val:
                exit_triggered = True; reason = "TAKE_PROFIT"
        else:
             if sl_val > 0 and current_price >= sl_val:
                exit_triggered = True; reason = "STOP_LOSS"
             elif tp_val > 0 and current_price <= tp_val:
                exit_triggered = True; reason = "TAKE_PROFIT"
                
        if exit_triggered:
            self.add_log(f"🎯 Local Trigger: {reason} @ {current_price}")
            self.execute_exit_atomically(symbol, reason)

    def _manage_all_trades(self):
        """Centralized Management for ALL active trades (Concurrent)"""
        trades_to_manage = []
        with self.trade_lock:
            trades_to_manage = list(self.active_trades.values())
        
        if not trades_to_manage:
            return

        for trade in trades_to_manage:
            try:
                symbol = trade.get("symbol")
                if not symbol: continue
                
                # Use current price for specific symbol
                current_price = hyperliquid_service.get_current_price(symbol)
                
                # --- STRATEGY DELEGATION ---
                handled_by_strategy = False
                strategy_name = trade.get("strategy")
                
                if strategy_name and strategy_name in self.strategy_engine.strategies:
                    strat_instance = self.strategy_engine.strategies[strategy_name]
                    
                    # Manage trade (pass None for df to avoid heavy fetching in loop)
                    custom_updates = strat_instance.manage_trade(trade, current_price, df=None)
                    
                    if custom_updates is not None:
                        handled_by_strategy = True
                        if custom_updates:
                            with self.trade_lock:
                                changed = False
                                t_ref = self.active_trades.get(symbol)
                                if t_ref:
                                    if "sl" in custom_updates:
                                        t_ref["sl"] = custom_updates["sl"]
                                        changed = True
                                        self.add_log(f"🤖 Strategy {strategy_name} updated SL for {symbol} to {custom_updates['sl']}")
                                    if "tp" in custom_updates:
                                        t_ref["tp"] = custom_updates["tp"]
                                        changed = True
                                        self.add_log(f"🤖 Strategy {strategy_name} updated TP for {symbol} to {custom_updates['tp']}")
                                        
                                    if changed:
                                        t_ref["initial_sl_tp_set"] = True
                                        self._verify_and_enforce_sl_tp(symbol, t_ref, bypass_cooldown=True)
                                        StateManager.save_state(self)

                # 2. Default Smart Trailing (Fallback) - Only on actual change
                if not handled_by_strategy:
                    if self._update_trailing_stops(trade, current_price):
                         self.add_log(f"🔄 Trailing Stop Updated for {symbol}. Enforcing...")
                         with self.trade_lock:
                             t_ref = self.active_trades.get(symbol)
                             if t_ref:
                                t_ref["initial_sl_tp_set"] = True
                                self._verify_and_enforce_sl_tp(symbol, t_ref, bypass_cooldown=True)

                # 3. Local Exit Check (Safety)
                self._check_local_exits(trade, symbol, current_price)
                
            except Exception as manage_err:
                self.add_log(f"⚠️ Management Error on {symbol}: {manage_err}")

    def _sync_state(self, silent=True):
        """Unified State Synchronization (Stateless Truth) - Multi-Position aware"""
        try:
            positions = hyperliquid_service.get_positions()
            # Map of symbols currently on exchange
            active_exchange_positions = {p["symbol"]: p for p in positions if float(p.get("size", 0)) != 0}
            
            # 1. Update/Adopt positions from Exchange
            for symbol, pos in active_exchange_positions.items():
                trade = self.active_trades.get(symbol)
                
                if not trade:
                    # New Position Detected (Adoption)
                    if not silent: self.add_log(f"🕵️ SYNC: Deteced ORPHAN {symbol} on exchange. Adopting...")
                    # We switch context to assist adoption if it uses self.active_symbol internally
                    self.switch_active_symbol(symbol)
                    self._adopt_existing_position(pos)
                else:
                    # Update Existing Memory
                    with self.trade_lock:
                        trade["pnl"] = float(pos.get("pnl", 0))
                        trade["size"] = float(pos.get("size", 0))
                        trade["leverage"] = float(pos.get("leverage", 1.0))
            
            # 2. Detect External Closures (Trades tracked but not on exchange)
            tracked_symbols = list(self.active_trades.keys())
            for symbol in tracked_symbols:
                if symbol not in active_exchange_positions:
                    trade = self.active_trades.get(symbol)
                    if not trade: continue
                    
                    # ALWAYS log closure detections (critical state transition)
                    self.add_log(f"🕵️ SYNC: Position {symbol} vanished from exchange. Handling closure...")
                    self._handle_external_closure(symbol, trade, silent)
        except Exception as e:
            # ALWAYS log sync errors (was silent=True before, hiding ghost trade bugs)
            self.add_log(f"⚠️ Sync Error: {e}")

    def _handle_external_closure(self, symbol: str, trade: dict, silent: bool = True):
        """Logic to record and clean up a trade closed externally"""
        self.add_log(f"🔄 EXTERNAL CLOSURE DETECTED: {symbol} — Processing...")
        pnl_usdc = 0
        try:
            # 1. Fetch recent history from Exchange to find REAL exit price
            recent_trades = hyperliquid_service.get_trade_history(limit=50)
            # FIX: get_trade_history returns 'symbol', NOT 'coin'
            closing_trade = next((t for t in recent_trades if t.get('symbol') == symbol), None)
            
            entry_price = float(trade.get("entry", 0))
            size = float(trade.get("size", 0))
            side = trade.get("side")
            
            if closing_trade:
                exit_price = float(closing_trade.get("entry_price", 0)) # in trade history, entry_price is the fill price
                pnl_usdc = float(closing_trade.get("pnl", 0))
                
                if pnl_usdc == 0 and entry_price > 0:
                    pnl_usdc = (float(exit_price) - float(entry_price)) * float(size) if side == "BUY" else (float(entry_price) - float(exit_price)) * float(size)
                
                # ALWAYS log closure details (critical for debugging)
                self.add_log(f"📝 SYNC: Found closure details for {symbol} (Exit: {exit_price}, PnL: ${float(pnl_usdc):.2f})")
            else:
                 # Fallback recording based on current market price
                 exit_price = hyperliquid_service.get_current_price(symbol)
                 pnl_usdc = (exit_price - entry_price) * size if side == "BUY" else (entry_price - exit_price) * size
                 self.add_log(f"⚠️ SYNC: Could not find exact closure in history for {symbol}. Recording estimated PnL: ${pnl_usdc:.2f}")

            # Record
            self.trade_recorder.add_trade({
                  "symbol": symbol,
                  "strategy": trade.get("strategy", "Unknown"),
                  "side": side,
                  "entry_price": entry_price,
                  "exit_price": exit_price,
                  "size": size,
                  "pnl": pnl_usdc,
                  "pnl_usdc": pnl_usdc,
                  "exit_reason": "External/Sync Close",
                  "exit_time": pd.Timestamp.now().isoformat(),
                  "entry_indicators": trade.get("entry_indicators", {})
            })
            
            discord_service.send_alert(
                f"🏁 TRADE CLOSED (Exchange): {symbol}",
                f"Reason: External Close (SL/TP?)\nPnL: ${pnl_usdc:.2f}",
                color="00FF00" if pnl_usdc >= 0 else "FF0000"
            )

        except Exception as e:
            # ALWAYS log errors (was silent before, causing ghost trades)
            self.add_log(f"⚠️ Error in _handle_external_closure for {symbol}: {e}")
        
        finally:
            # CLEAN UP MEMORY NO MATTER WHAT (Avoid Ghost Trades)
            with self.trade_lock:
                if symbol in self.active_trades:
                    self.active_trades.pop(symbol, None)
                    StateManager.save_state(self)
                    self.add_log(f"✅ Ghost trade {symbol} cleaned from state")

    def force_sync(self):
        """Manually trigger synchronization with Exchange."""
        self.add_log("🔄 FORCE SYNC: Initiated by User")
        result = self._sync_state(silent=False)
        return {"status": "success", "message": "Resync initiated"}


    def _enforce_leverage(self):
        """Enforce leverage based on Risk Profile settings"""
        try:
            # Fallback: Use global_settings default_leverage
            default_leverage = self.global_settings.get("risk_defaults", {}).get("default_leverage", 5)
            default_margin_type = self.global_settings.get("risk_defaults", {}).get("default_margin_type", "Cross")
            
            # Read trading params from scanner_settings (centralized source) with fallbacks
            requested_leverage = self.scanner_settings.get("leverage")
            
            # If leverage not explicitly set or set to 1 (likely default), derive from risk profile
            if requested_leverage is None or int(requested_leverage) <= 1:
                risk_profile = self.global_settings.get("risk_defaults", {}).get("risk_profile", "Capital Preservation First")
                if risk_profile == "Capital Preservation First":
                    requested_leverage = 3
                elif risk_profile == "Balanced Growth":
                    requested_leverage = 5
                elif risk_profile == "High Volatility Hunter":
                    requested_leverage = 10
                else:
                    requested_leverage = default_leverage
            else:
                requested_leverage = int(requested_leverage)

            margin_type = self.scanner_settings.get("margin_type", default_margin_type)
            is_cross = (margin_type == "Cross")
            
            target_leverage = requested_leverage
            
            # RISK PROFILE BASED LEVERAGE (Sync with prompts.py)
            risk_profile = self.global_settings.get("risk_defaults", {}).get("risk_profile", "Capital Preservation First")
            
            if risk_profile == "Capital Preservation First":
                target_leverage = 3
            elif risk_profile == "Balanced Growth":
                target_leverage = 5
            elif risk_profile == "High Volatility Hunter":
                target_leverage = 10
            else:
                target_leverage = int(self.scanner_settings.get("leverage", default_leverage))
            
            self.add_log(f"🛡️ RISK PROFILE ({risk_profile}): Using leverage: {target_leverage}x")
            try:
                balance_data = hyperliquid_service.get_account_balance()
                if balance_data.get("status") == "success":
                    self.account_value = float(balance_data.get("total_equity", 0.0))
            except:
                pass
            self.add_log(f"⚙️ SYNC: Enforcing Leverage {target_leverage}x ({margin_type}) on Exchange...")
            hyperliquid_service.update_leverage(self.active_symbol, target_leverage, is_cross)
            self._leverage_synced = True
            
        except Exception as e:
            self.add_log(f"⚠️ LEVERAGE SYNC FAILED: {e}")

    def trading_loop(self):
        """Main trading loop"""
        self.add_log("🚀 Trading loop started")
        self.add_log(f"⚙️ Loop initialized. is_running={self.is_running}")
        
        # STARTUP SYNC
        if not self.startup_sync_done:
            self.add_log("🔄 STARTUP SYNC: Checking Hyperliquid positions...")
            if self.trading_enabled:
                 self._enforce_leverage()
            
            # Initial Synchro
            self._sync_state(silent=False)
            self.startup_sync_done = True
            self.add_log("✅ STARTUP SYNC: Complete")
            self.add_log("🕵️ Starting Position Reconciler...")
            
        while self.is_running:
            try:
                # 1. Reconciliation & State Sync (The Heartbeat)
                # Run reconciler (fixes SL/TP)
                if hasattr(self, 'position_reconciler'):
                    self.position_reconciler.run_tick()
                
                # Check Exchange State (Adopt/Close)
                # Update heartbeat (thread health monitoring)
                self._loop_heartbeat = time.time()
                
                now = time.time()
                if now - self._last_state_sync_time >= self._state_sync_interval:
                    self._sync_state(silent=True)
                    self._last_state_sync_time = now
            except Exception as tick_err:
                self.add_log(f"⚠️ Loop Tick Error: {tick_err}")

            # Dynamic Leverage & Gamification Enforcement
            if self.trading_enabled and not self._leverage_synced:
                self._enforce_leverage()
            elif not self.trading_enabled:
                self._leverage_synced = False

            action = None
            sl = None
            tp = None
            
            # --- CONTINUOUS ADOPTION (Manual Trades) ---
            # Use _sync_state(silent=False) occasionally to detect and notify adoption
            # instead of a restrictive single-symbol check.
            if not self.active_trade and int(time.time()) % 30 == 0:
                self._sync_state(silent=False)
            
            try:
                acc_data = hyperliquid_service.get_account_balance()
                if acc_data.get("status") == "success":
                   self.account_value = float(acc_data.get("total_equity", 0))
            except: pass
            
            # --- PERIODIC MARKET ANALYSIS (For Copilot when flat) ---
            try:
                # Update Daily PnL Snapshot every hour
                if not hasattr(self, "_last_pnl_sync") or (time.time() - self._last_pnl_sync) > 3600:
                    self.add_log("🔄 Triggering Daily PnL Sync Task...")
                    def sync_pnl():
                        try:
                            # 1. Dynamic PnL Log
                            hyperliquid_service.get_daily_pnl()
                            
                            # 2. Daily Snapshot
                            acc = hyperliquid_service.get_account_balance()
                            equity = float(acc.get("total_equity", 0)) if acc.get("status") == "success" else 0
                            
                            if equity > 0:
                                today_str = pd.Timestamp.now(tz='UTC').strftime("%Y-%m-%d")
                                snapshots = storage_service.load_pnl_snapshot()
                                
                                if today_str not in snapshots:
                                    snapshots[today_str] = {
                                        "start_value": equity,
                                        "timestamp": pd.Timestamp.now(tz='UTC').isoformat()
                                    }
                                    storage_service.save_pnl_snapshot(snapshots)
                                    self.add_log(f"📸 Daily Snapshot Saved: ${equity:.2f}")

                        except Exception as e:
                            self.add_log(f"⚠️ PnL Sync Error: {e}")
                    
                    threading.Thread(target=sync_pnl, daemon=True).start()
                    self._last_pnl_sync = time.time()

                # Run market analysis every 15 minutes or if cache is empty
                last_market_time = self.ai_cache.get("last_market_analysis_time")
                if not last_market_time or (pd.Timestamp.now() - last_market_time).total_seconds() > 900:
                    self.add_log("🧠 Triggering Background Market Analysis Refresh...")
                    def refresh_market():
                        try:
                            # Create a new loop for this one-off background task in the thread
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self._update_market_analysis())
                            loop.close()
                        except Exception as e:
                            self.add_log(f"⚠️ refresh_market Error: {e}")
                    
                    threading.Thread(target=refresh_market, daemon=True).start()
                    # Prevent multiple starts before first completion (temporary debounce)
                    self.ai_cache["last_market_analysis_time"] = pd.Timestamp.now() 
            except: pass
            # --------------------------------------------------------
            
            try:
                self._manage_all_trades()
                
                # If we are flat, analyzed current symbol. 
                # If we have trades, cycle through them?
                # For now, let's keep it simple: manage all trades every loop tick.
                
                # Skip NEW ENTRY analysis only if we are at max positions
                # We still analyze for new opportunities even with open trades
                if len(self.active_trades) >= self.max_positions:
                     # Log désactivé pour éviter le spam dans Coolify
                     time.sleep(10)
                     continue
                if self.active_trades.get(self.active_symbol):
                     self.add_log(f"📍 Active trade on {self.active_symbol}. Running analysis for new opportunities...")

                self.add_log("🔄 Entering strategy analysis...")
                df_15m = hyperliquid_service.get_candles(self.active_symbol, interval="15m", limit=300)  # FIX: 200→300 for SMA_200 validity
                df_1m = hyperliquid_service.get_candles(self.active_symbol, interval="1m", limit=100)
                
                if df_15m.empty or df_1m.empty:
                    self.add_log("⚠️ No data received")
                    time.sleep(10)
                    continue

                numeric_cols = ['open', 'high', 'low', 'close', 'volume']
                try:
                    for df_target in [df_15m, df_1m]:
                        for col in numeric_cols:
                            if col in df_target.columns:
                                df_target[col] = df_target[col].astype(float)
                except Exception as e:
                    self.add_log(f"⚠️ Error casting data: {e}")
                    continue
                
                self.latest_data = df_15m
                
                # --- OPEN INTEREST INTEGRATION (Historical Accumulation) ---
                try:
                    current_oi = hyperliquid_service.get_open_interest(self.active_symbol)
                    # FIX: Use UTC timestamp to match candle data
                    current_time = pd.Timestamp.now(tz='UTC')
                    
                    # Store in history
                    self.oi_history.append({"time": current_time, "oi": current_oi})
                    
                    # Create OI DataFrame from history
                    oi_df = pd.DataFrame(list(self.oi_history))
                    oi_df.set_index('time', inplace=True)
                    
                    # Resample to align with 15m candles
                    if not oi_df.empty:
                         # Normalize timezones for reindex stability
                         if df_15m.index.tz is None:
                             # If candles are naive, make OI naive (strip UTC)
                             oi_df.index = oi_df.index.tz_convert(None)
                         else:
                             # If candles are aware, ensure OI is aware (already is UTC)
                             # Convert to target tz just in case
                             oi_df.index = oi_df.index.tz_convert(df_15m.index.tz)

                         # Forward fill to map our sparse observations to the candles
                         oi_aligned = oi_df.reindex(df_15m.index, method='ffill')
                         
                         df_15m['open_interest'] = oi_aligned['oi']
                         
                         # Fill initial NaNs with current if needed (fast start)
                         if df_15m['open_interest'].isnull().all():
                             df_15m['open_interest'] = current_oi
                         else:
                             # FIX: Pandas 3.0+ deprecation of fillna(method=...)
                             df_15m['open_interest'] = df_15m['open_interest'].ffill()
                             df_15m['open_interest'] = df_15m['open_interest'].fillna(current_oi) # Fallback
                         
                         # --- CALCULATE OI INDICATORS (User Requested) ---
                         # 1. % Variation OI
                         df_15m['OI_Change_Pct'] = df_15m['open_interest'].pct_change() * 100
                         
                         # 2. Moyenne Mobile OI (MA20)
                         df_15m['OI_MA20'] = df_15m['open_interest'].rolling(window=20).mean()
                         
                         # 3. Ratio OI actuel / MA
                         df_15m['OI_vs_MA'] = df_15m['open_interest'] / df_15m['OI_MA20']
                         
                         # 4. Divergence Prix vs OI
                         # (Price Chg Prev Candle - OI Chg Current Candle)? 
                         # User formula: (df['close'].pct_change() * 100).shift(1) - df['OI_Change_Pct']
                         # This implies: If price went UP yesterday but OI drops today -> Divergence?
                         # Let's stick to the requested formula strictly.
                         df_15m['OI_Divergence'] = (df_15m['close'].pct_change() * 100).shift(1) - df_15m['OI_Change_Pct']
                         
                except Exception as e:
                    self.add_log(f"⚠️ OI Processing Error: {e}")
                
                result = self.strategy_engine.analyze(df_15m, extra_data={"1m": df_1m, "symbol": self.active_symbol})
                self.active_strategies = result.get('strategies', [])
                self.latest_strategy_result = result
                
                regime = result.get('regime', 'UNKNOWN')
                adx = result.get('adx', 0)
                rsi = result.get('rsi', 0)
                ema_20 = result.get('ema_20', 0)
                ema_50 = result.get('ema_50', 0)
                volume_ratio = result.get('volume_ratio', 100)
                
                # Enhanced regime log with calculations context
                ema_trend = "↗" if ema_20 > ema_50 else "↘" if ema_20 < ema_50 else "→"
                adx_note = ">25=TREND" if adx < 25 else "TRENDING"
                current_price = float(df_15m['close'].iloc[-1])
                
                analysis_metrics = {
                    "regime": regime,
                    "adx": round(adx, 1),
                    "rsi": round(rsi, 1),
                    "volume_ratio": round(volume_ratio, 0),
                    "current_price": current_price
                }
                self.add_log(f"📊 Regime: {regime} | Price: {current_price:.2f} | ADX: {adx:.1f} ({adx_note}) | RSI: {rsi:.1f} | EMA20/50: {ema_trend} | Vol: {volume_ratio:.0f}%", metadata=analysis_metrics)
                
                # Capture full technical context for audit (Approved or Rejected)
                technical_context = {
                    "regime": result.get("regime"),
                    "adx": round(result.get("adx", 0), 2),
                    "adx_slope": round(result.get("adx_slope", 0), 2),
                    "rsi": round(result.get("rsi", 0), 2),
                    "ema_9": round(result.get("ema_9", 0), 4),
                    "ema_20": round(result.get("ema_20", 0), 4),
                    "ema_50": round(result.get("ema_50", 0), 4),
                    "bb_upper": round(result.get("bb_upper", 0), 4),
                    "bb_lower": round(result.get("bb_lower", 0), 4),
                    "bb_width": round(result.get("bb_width", 0), 2),
                    "volume_ratio": round(result.get("volume_ratio", 100), 1),
                    "current_price": result.get("current_price") or current_price
                }
                
                signals = result.get("signals", [])
                if signals:
                    sig = signals[0]
                    if sig.get("signal") and sig.get("price"):
                        
                        # --- COOLDOWN CHECK (BEFORE AI to save tokens) ---
                        cooldown_minutes = self.global_settings.get("risk_defaults", {}).get("cooldown_minutes", 0)
                        if cooldown_minutes > 0 and self._last_trade_info.get("time"):
                            last_symbol = self._last_trade_info.get("symbol")
                            last_direction = self._last_trade_info.get("direction")
                            last_time = self._last_trade_info.get("time")
                            
                            if last_symbol == self.active_symbol and last_direction == sig.get("signal"):
                                elapsed_minutes = (pd.Timestamp.now() - pd.Timestamp(last_time)).total_seconds() / 60
                                if elapsed_minutes < max(1, cooldown_minutes):  # min 1 minute
                                    remaining = max(1, cooldown_minutes) - elapsed_minutes
                                    self.add_log(f"⏳ COOLDOWN: {self.active_symbol} {sig.get('signal')} - Skip (wait {remaining:.1f}min)")
                                    time.sleep(10)
                                    continue
                        
                        market_context = self._prepare_ai_context()
                        # Inject Copilot MTF Sentiment
                        market_context['mtf_sentiment'] = self._fetch_mtf_sentiment(self.active_symbol)
                        strat_name = sig.get('strategy')
                        strat_obj = self.strategy_engine.strategies.get(strat_name)
                        strategy_persona = getattr(strat_obj, 'AI_PERSONA', None)
                        
                        current_time = time.time()
                        time_since_last_call = current_time - self.last_ai_call
                        
                        # Score threshold removed - risk thresholds are already configured in settings
                        # AI validation handles the filtering based on configured risk thresholds
                        
                        if time_since_last_call < 45:  # 45s cooldown to save credits
                            self.add_log(f"⏳ AI COOLDOWN: Skipping (only {time_since_last_call:.0f}s since last)")
                            continue
                        
                        approved = False
                        self.add_log(f"🤖 Validating signal: {sig.get('signal')} from {sig.get('strategy')}")
                        val_res = ia_service.validate_signal(sig, market_context, strategy_persona=strategy_persona)
                        self.last_ai_call = current_time
                        
                        try:
                            import json
                            if val_res and val_res.get("raw_output"):
                                ai_data = json.loads(ia_service.extract_json(val_res["raw_output"]))
                                approved = ai_data.get("approved", False)
                                confidence = ai_data.get("confidence", 0)
                                risk_level_raw = ai_data.get("risk_level")
                                risk_level = str(risk_level_raw).upper() if risk_level_raw else "MEDIUM"
                                
                                if approved:
                                    # HYBRID CONFIDENCE THRESHOLD CHECK
                                    required_conf = config.AI_CONF_THRESHOLD_MEDIUM  # Default
                                    if risk_level == "HIGH":
                                        required_conf = config.AI_CONF_THRESHOLD_HIGH
                                    elif risk_level == "LOW":
                                        required_conf = config.AI_CONF_THRESHOLD_LOW
                                    
                                    if confidence >= required_conf:
                                        reason = ai_data.get('reasoning', 'No reason')
                                        self.add_log(f"✅ AI APPROVED (Conf: {confidence}%): {reason}", metadata=ai_data)
                                        self._record_signal_analysis(sig, ai_data, True, indicators=technical_context)
                                        
                                        # Discord Notification for AI Approval
                                        discord_service.send_alert(
                                            f"✅ AI APPROVED: {sig.get('signal')} {sig.get('symbol')}",
                                            f"Strategy: {sig.get('strategy')}\nConfidence: {confidence}%\nRisk: {risk_level}\n\n{reason}",
                                            color="00FF00"
                                        )
                                        
                                        if ai_data.get("suggested_adjustments"):
                                            adj = ai_data["suggested_adjustments"]
                                            
                                            # Robust parsing for AI suggestions (handle "$0.50" strings)
                                            if adj.get("sl"): 
                                                try:
                                                    val = adj["sl"]
                                                    if isinstance(val, str):
                                                        val = float(val.replace('$', '').replace(',', '').strip())
                                                    sig["sl"] = float(val)
                                                except Exception as e:
                                                    self.add_log(f"⚠️ Failed to parse AI SL adjustment: {adj['sl']} ({e})")
                                                    
                                            if adj.get("tp"): 
                                                try:
                                                    val = adj["tp"]
                                                    if isinstance(val, str):
                                                        val = float(val.replace('$', '').replace(',', '').strip())
                                                    sig["tp"] = float(val)
                                                except Exception as e:
                                                    self.add_log(f"⚠️ Failed to parse AI TP adjustment: {adj['tp']} ({e})")
                                    else:
                                        self.add_log(f"⚠️ AI approved but CONFIDENCE TOO LOW ({confidence}% < {required_conf}% for {risk_level} risk)", metadata=ai_data)
                                        self._record_signal_analysis(sig, ai_data, False, indicators=technical_context)
                                        approved = False
                                else:
                                    reason = ai_data.get('reasoning', 'No reason')
                                    self.add_log(f"❌ AI REJECTED: {reason}", metadata=ai_data)
                                    self._record_signal_analysis(sig, ai_data, False, indicators=technical_context)
                            else:
                                approved = True 
                        except:
                            self.add_log("⚠️ AI Validation JSON Error. Defaulting to REJECT.")
                            approved = False
                            
                        if approved:
                            acc = hyperliquid_service.get_account_balance()
                            equity = float(acc.get("total_equity", 0) if acc.get("status")=="success" else 0)
                            
                            sl_price = sig.get("sl")
                            entry_price = sig.get("price")
                            
                            # --- ATR-BASED SL FLOOR (Prevent unrealistically tight SL) ---
                            try:
                                if sl_price and entry_price and not df_15m.empty:
                                    # Get ATR from the data (already computed by strategy engine)
                                    if 'ATRr_14' in df_15m.columns:
                                        current_atr = float(df_15m['ATRr_14'].iloc[-1])
                                    else:
                                        # Fallback: manual ATR calc
                                        tr = pd.concat([
                                            df_15m['high'] - df_15m['low'],
                                            (df_15m['high'] - df_15m['close'].shift(1)).abs(),
                                            (df_15m['low'] - df_15m['close'].shift(1)).abs()
                                        ], axis=1).max(axis=1)
                                        current_atr = float(tr.rolling(14).mean().iloc[-1])
                                    
                                    min_sl_distance = current_atr * 1.0  # Minimum 1x ATR
                                    actual_sl_distance = abs(entry_price - sl_price)
                                    
                                    if actual_sl_distance < min_sl_distance:
                                        direction = sig.get("signal", "BUY")
                                        if direction == "BUY":
                                            adjusted_sl = entry_price - min_sl_distance
                                        else:
                                            adjusted_sl = entry_price + min_sl_distance
                                        
                                        self.add_log(f"⚠️ SL FLOOR: AI SL too tight ({actual_sl_distance:.4f} < 1x ATR {current_atr:.4f}). Adjusted: {sl_price:.4f} → {adjusted_sl:.4f}")
                                        sl_price = adjusted_sl
                                        sig["sl"] = adjusted_sl  # Update signal too
                            except Exception as atr_err:
                                self.add_log(f"⚠️ ATR SL floor check failed: {atr_err}")
                            
                            # DYNAMIC POSITION SIZING based on RISK PROFILE
                            if not self.scanner_settings.get("gamification_enabled", True):
                                risk_profile = self.global_settings.get("risk_defaults", {}).get("risk_profile", "Capital Preservation First")
                                
                                # Assign risk % constants based on profile
                                risk_pct = 1.5 # Default (Conservative)
                                if risk_profile == "Balanced Growth": risk_pct = 3.5
                                elif risk_profile == "High Volatility Hunter": risk_pct = 7.0
                                
                                self.add_log(f"📏 SIZING: Using dynamic risk mode ({risk_profile}): {risk_pct}% risk")
                                size = self.risk_manager.calculate_position_size(
                                    price=entry_price,
                                    sl_price=sl_price,
                                    equity=equity,
                                    method="risk_pct",
                                    size_value=risk_pct
                                )
                            else:
                                # Standard sizing (Fixed $20 Margin @ Target Leverage)
                                current_leverage = int(self.scanner_settings.get("leverage", 5))
                                size = self.risk_manager.calculate_position_size(
                                    price=entry_price, 
                                    sl_price=sl_price, 
                                    equity=equity,
                                    method="fixed",
                                    size_value=20.0,
                                    leverage=current_leverage
                                )
                            # ---------------------------------------------------
                            # 2. EXECUTION LOGIC (Live)
                            # ---------------------------------------------------
                            if self.trading_enabled:
                                
                                # Sync Positions periodically
                                if int(time.time()) % 60 == 0:
                                     self.force_sync()
                                
                                # Capture full market snapshot for trade analysis
                                # Use pre-calculated technical_context mixed with AI data
                                entry_indicators = technical_context.copy()
                                entry_indicators.update({
                                    "ai_confidence": confidence if 'confidence' in locals() else 0,
                                    "ai_reasoning": (ai_data.get("reasoning", "") if 'ai_data' in locals() else sig.get("reason", "Strategy Signal"))[:200]
                                })
                                
                                self.execute_entry_atomically(
                                    self.active_symbol,
                                    sig.get("signal"),
                                    size,
                                    entry_price,
                                    sl_price,
                                    sig.get("tp"),
                                    sig.get("strategy"),
                                    sig.get("metadata"),
                                    entry_indicators
                                )
                                
                                # Update last trade info for cooldown
                                self._last_trade_info = {
                                    "symbol": self.active_symbol,
                                    "direction": sig.get("signal"),
                                    "time": pd.Timestamp.now().isoformat()
                                }
                            else:
                                self.add_log(f"⚠️ TRADE NOT EXECUTED: trading_enabled=False (Signal approved but bot in observation mode)")
                
                # Optimized Sleep Loop + Anti-Signal Spam
                has_active_trade = len(self.active_trades) > 0
                sleep_duration = 10 if has_active_trade else (15 if signals else 10)
                self.add_log(f"⏸️ Next analysis in {sleep_duration}s... (signals detected: {len(signals)})")
                for _ in range(int(sleep_duration)):
                    if not self.is_running: break
                    time.sleep(1)
                
            except Exception as e:
                import traceback
                self.add_log(f"❌ Error in trading loop: {e}")
                self.add_log(f"🔍 Traceback: {traceback.format_exc()}")
                time.sleep(5)
        
        self.add_log("⏸️ Trading loop stopped")

    def _adopt_existing_position(self, active_pos):
        """Adopt an existing position from the exchange into the bot's memory."""
        try:
            symbol = active_pos['symbol']
            side = active_pos['side']
            size = float(active_pos['size'])
            entry_price = float(active_pos['entry_price'])
            leverage = float(active_pos.get('leverage', 1.0))
            
            with self.trade_lock:
                self.active_trades[symbol] = {
                    "symbol": symbol,
                    "side": side,
                    "entry": entry_price,
                    "size": size,
                    "leverage": leverage,
                    "oid": "external_position",
                    "sl": 0,
                    "tp": 0,
                    "strategy": "Manual (Adopted)",
                    "entry_time": pd.Timestamp.now().isoformat(),
                    "pnl": float(active_pos.get('pnl', 0)),
                    "max_pnl": float(active_pos.get('pnl', 0)),
                    "status": "OPEN",
                    "ai_analysis": None,
                    "metadata": {"stage": "1_raw_adoption"}
                }
                StateManager.save_state(self)
            
            self.add_log(f"🕵️ ADOPTED {symbol}: Size {size} | Entry {entry_price}")
            
            # --- GLOBAL ADOPTION NOTIFICATION ---
            direction_label = "LONG 🟢" if side == "BUY" else "SHORT 🔴"
            try:
                discord_service.send_alert(
                    f"📥 Manual Position Detected: {symbol}",
                    f"Direction: {direction_label}\n"
                    f"Entry: {entry_price}\n"
                    f"Size: {size}\n"
                    f"The bot will now track and protect this position.",
                    color="FFA500"  # Orange — informational
                )
            except Exception as e:
                self.add_log(f"⚠️ Discord notification failed during adoption: {e}")
            
            try:
                self.add_log(f"🔍 Analyzing market context for {symbol}...")
                df_15m = hyperliquid_service.get_candles(symbol, "15m", 200)
                current_price = df_15m['close'].iloc[-1] if not df_15m.empty else entry_price
                
                self.add_log(f"🔎 Checking existing orders for {symbol}...")
                existing_orders = hyperliquid_service.info.open_orders(config.HL_ACCOUNT_ADDRESS)
                symbol_orders = [o for o in existing_orders if o.get("coin") == symbol]
                
                existing_sl = None
                existing_tp = None
                
                for order in symbol_orders:
                    px = float(order.get("triggerPx", 0))
                    if order.get("reduceOnly", False) and px > 0:
                        if side == "BUY":
                            if px < current_price: existing_sl = px
                            else: existing_tp = px
                        else: # SELL
                            if px > current_price: existing_sl = px
                            else: existing_tp = px
                
                pnl_pct = ((current_price - entry_price) / entry_price) * 100 if side == "BUY" else ((entry_price - current_price) / entry_price) * 100
                
                should_set_sl_tp = False
                sl_price = 0
                tp_price = 0
                strategy_name = "Manual (Adopted)"

                if existing_sl or existing_tp:
                    self.add_log(f"✅ Protection orders detected for {symbol}. Validating...")
                    
                    # Use existing values if present, else use placeholders
                    sl_to_use = existing_sl if existing_sl else 0
                    tp_to_use = existing_tp if existing_tp else 0

                    # Smart BE check for adopted trades
                    if pnl_pct >= 1.2:
                         sl_is_be = (sl_to_use >= entry_price * 1.001) if side == "BUY" else (sl_to_use <= entry_price * 0.999) if sl_to_use > 0 else False
                         if not sl_is_be:
                              sl_price = entry_price * 1.002 if side == "BUY" else entry_price * 0.998
                              tp_price = tp_to_use if tp_to_use > 0 else (entry_price * 1.05 if side == "BUY" else entry_price * 0.95)
                              should_set_sl_tp = True
                              self.add_log(f"🛡️ Smart BE: Moving existing SL to break-even for {symbol}")
                         else:
                              sl_price = sl_to_use
                              tp_price = tp_to_use
                    else:
                        sl_price = sl_to_use
                        tp_price = tp_to_use
                else:
                    self.add_log(f"⚠️ No protection orders for {symbol}. Calculating rational ATR-based stops.")
                    should_set_sl_tp = True
                    
                    # 1. Determine ATR multiplier based on profile
                    risk_profile = self.global_settings.get("risk_defaults", {}).get("risk_profile", "Balanced Growth")
                    atr_mult = 1.5
                    if risk_profile == "Capital Preservation First": atr_mult = 1.0
                    elif risk_profile == "High Volatility Hunter": atr_mult = 2.5
                    
                    # 2. Get ATR from data
                    atr_val = 0
                    if not df_15m.empty:
                        try:
                            # Try to find ATR in columns
                            atr_col = next((c for c in df_15m.columns if 'ATR' in c.upper()), None)
                            if atr_col:
                                atr_val = float(df_15m[atr_col].iloc[-1])
                            else:
                                # Quick manual ATR
                                tr = pd.concat([
                                    df_15m['high'] - df_15m['low'],
                                    (df_15m['high'] - df_15m['close'].shift(1)).abs(),
                                    (df_15m['low'] - df_15m['close'].shift(1)).abs()
                                ], axis=1).max(axis=1)
                                atr_val = tr.rolling(14).mean().iloc[-1]
                        except Exception as e:
                            self.add_log(f"⚠️ ATR Calculation failed during adoption: {e}")
                    
                    # 3. Fallback if ATR is 0
                    if not atr_val or pd.isna(atr_val):
                        self.add_log("⚠️ ATR unavailable, falling back to 3% distance")
                        sl_dist = entry_price * 0.03
                    else:
                        sl_dist = atr_val * atr_mult
                        self.add_log(f"📏 Using {atr_mult}x ATR ({atr_val:.4f}) for SL distance: {sl_dist:.4f}")

                    # 4. Calculate proposed SL/TP
                    if side == "BUY":
                        proposed_sl = entry_price - sl_dist
                        proposed_tp = entry_price + (sl_dist * 1.5) # RR 1:1.5
                    else:
                        proposed_sl = entry_price + sl_dist
                        proposed_tp = entry_price - (sl_dist * 1.5)

                    # 5. LIQUIDATION GUARD
                    liq_price = active_pos.get("liquidation_price")
                    if liq_price and liq_price > 0:
                        # Ensure SL is at least 15% distance from liquidation (of the entry-to-liq gap)
                        gap = abs(entry_price - liq_price)
                        buffer = gap * 0.15
                        
                        if side == "BUY":
                            min_sl = liq_price + buffer
                            if proposed_sl <= min_sl:
                                self.add_log(f"🛡️ LIQUIDATION GUARD: Proposed SL ({proposed_sl:.4f}) too close to Liquidation ({liq_price:.4f}). Adjusted to {min_sl:.4f}")
                                proposed_sl = min_sl
                        else:
                            max_sl = liq_price - buffer
                            if proposed_sl >= max_sl:
                                self.add_log(f"🛡️ LIQUIDATION GUARD: Proposed SL ({proposed_sl:.4f}) too close to Liquidation ({liq_price:.4f}). Adjusted to {max_sl:.4f}")
                                proposed_sl = max_sl

                    sl_price = proposed_sl
                    tp_price = proposed_tp

                with self.trade_lock:
                    t_ref = self.active_trades.get(symbol)
                    if t_ref:
                        t_ref["sl"] = sl_price
                        t_ref["tp"] = tp_price
                        t_ref["strategy"] = strategy_name
                        t_ref["status"] = "OPEN (ADOPTED)"
                        t_ref["initial_sl_tp_set"] = True
                        if should_set_sl_tp:
                            self._verify_and_enforce_sl_tp(symbol, t_ref, bypass_cooldown=True)
                        StateManager.save_state(self)
                self.add_log(f"✅ Adoption Complete for {symbol}.")

            except Exception as e:
                self.add_log(f"⚠️ Adoption Analysis Error for {symbol}: {e}")

        except Exception as e:
            self.add_log(f"❌ Critical Adoption Error: {e}")

    def start(self):
        """Start the bot"""
        self.add_log(f"🔧 start() called. Current is_running={self.is_running}")
        thread_alive = self.thread and self.thread.is_alive()
        
        if not self.is_running or not thread_alive:
            if thread_alive:
                self.add_log("⚠️ Thread exists but is_running=False, fixing state...")
            elif self.is_running:
                self.add_log("⚠️ is_running=True but thread dead, restarting...")
            
            self.is_running = True
            self.add_log("🧵 Creating trading thread...")
            self.thread = threading.Thread(target=self.trading_loop, daemon=True)
            self.add_log("🚀 Starting trading thread...")
            self.thread.start()
            self.add_log(f"✅ Thread started. Thread alive={self.thread.is_alive()}")
            
            StateManager.save_state(self)
        else:
            self.add_log("⚠️ Bot already running with active thread, skipping start")

    def is_loop_responsive(self) -> bool:
        """Check if the trading loop is alive and responsive (not frozen)."""
        if not self.is_running or not self.thread or not self.thread.is_alive():
            return False
        if self._loop_heartbeat == 0:
            return True  # Not yet started, give it a chance
        return (time.time() - self._loop_heartbeat) < 120  # 2 min tolerance

    def stop(self):
        """Stop the bot with complete graceful shutdown"""
        if self.is_running:
            self.is_running = False
            self.add_log("🛑 Initiating graceful shutdown...")
            
            # Final sync: clean up ghost trades before stopping
            try:
                self.add_log("🔄 Final sync with exchange before shutdown...")
                self._sync_state(silent=False)
            except Exception as e:
                self.add_log(f"⚠️ Final sync failed: {e}")
            
            # Cancel orders for ALL active trades, not just the current symbol
            for symbol in list(self.active_trades.keys()):
                try:
                    self.add_log(f"🧹 Cancelling pending orders for {symbol}...")
                    hyperliquid_service.cancel_all_orders(symbol)
                    self.add_log(f"✅ Orders cancelled for {symbol}")
                except Exception as e:
                    self.add_log(f"⚠️ Failed to cancel orders for {symbol}: {e}")
            
            try:
                self.add_log("🔌 Stopping WebSocket...")
                hyperliquid_service.stop_websocket()
                self.add_log("✅ WebSocket stopped")
            except Exception as e:
                self.add_log(f"⚠️ Failed to stop WebSocket: {e}")
            
            if self.scanner_job:
                try:
                    self.scanner_settings['enabled'] = False
                    self.scanner_job.stop()
                    self.add_log("✅ Scanner stopped")
                except Exception as e:
                    self.add_log(f"⚠️ Failed to stop scanner: {e}")
            
            if self.thread:
                self.add_log("⏳ Waiting for trading thread...")
                self.thread.join(timeout=10)
                if self.thread.is_alive():
                    self.add_log("⚠️ Trading thread did not stop gracefully")
                else:
                    self.add_log("✅ Trading thread stopped")
            
            try:
                StateManager.save_state(self)
                self.add_log("✅ State saved")
            except Exception as e:
                self.add_log(f"⚠️ Failed to save state: {e}")
            
            self.add_log("⏹️ Bot stopped gracefully")

    def close_active_trade(self, reason="Manual Close"):
        """Close the currently active trade"""
        with self.trade_lock:
            if not self.active_trade:
                return False, "No active trade"
            symbol = self.active_trade["symbol"]
            
        try:
            if self.execution_mode == "Dry Run":
                self.add_log(f"[DRY] Would close {symbol} ({reason})")
                with self.trade_lock:
                    self.active_trade = None
                    StateManager.save_state(self)
                return True, "[DRY] Trade closed (simulated)"
            
            self.add_log(f"📉 MANUAL CLOSE REQUESTED for {symbol} ({reason})")
            success = self.execute_exit_atomically(symbol, reason=reason)
            
            if success:
                return True, "Trade closed successfully"
            else:
                return False, "Failed to close trade (Check logs)"
            
        except Exception as e:
            self.add_log(f"❌ Error in close_active_trade: {e}")
            return False, str(e)

    async def recalibrate_position_stops(self):
        """Manual override to recalculate and update TP/SL."""
        with self.trade_lock:
            if not self.active_trade:
                 return "ERROR", "No active trade to recalibrate."
            symbol = self.active_trade["symbol"]
            
        self.add_log(f"♻️ RECALIBRATE: Auditing stops for {symbol}...")

        try:
            positions = hyperliquid_service.get_positions()
            real_pos = next((p for p in positions if p["symbol"] == symbol and float(p["size"]) != 0), None)
            
            if not real_pos:
                self.add_log(f"⚠️ Recalibration aborted: No position found on exchange for {symbol}")
                with self.trade_lock:
                    self.active_trade = None 
                return "ERROR", "No real position found (Local state cleared)."

            entry_price = float(real_pos["entry_price"])
            side = real_pos["side"]
            size = float(real_pos["size"])
            
            df = self.latest_data
            if df is None or df.empty:
                self.add_log("📡 Recalibrate: Cache empty, fetching fresh 15m data...")
                try:
                    from app.utils.market_data import get_hyperliquid_candles
                    df = await get_hyperliquid_candles(symbol, "15m", 100)
                except:
                    self.add_log("⚠️ Fresh fetch failed.")
            
            atr = 0.0
            try:
                if df is not None and not df.empty:
                    if 'ATRr_14' not in df.columns:
                         high = df['high']; low = df['low']; close = df['close']
                         tr1 = high - low; tr2 = (high - close.shift()).abs(); tr3 = (low - close.shift()).abs()
                         tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                         atr = tr.rolling(14).mean().iloc[-1]
                    else:
                         atr = df['ATRr_14'].iloc[-1]
            except: pass
            
            # Use REAL-TIME price for validation, not candle close
            current_price = hyperliquid_service.get_current_price(symbol)
            if current_price == 0:
                 current_price = df['close'].iloc[-1]
            
            self.add_log(f"🔍 Recalibrate: Current Price for validation: {current_price}")

            # Recalculate based on Entry but ensuring validity vs Current Price
            atr_val = atr if atr > 0 else entry_price * 0.015
            
            # --- SMART CONTEXT AWARENESS ---
            sl_mult = 2.0; tp_mult = 3.0
            
            try:
                # 1. Strategy Intent
                strategy_name = self.active_trade.get("strategy", "Unknown").lower()

                # Get Risk Profile Multiplier Defaults
                if not hasattr(self, 'global_settings'): self.global_settings = {}
                risk_profile = self.global_settings.get("risk_defaults", {}).get("risk_profile", "Capital Preservation First")
                
                if risk_profile == "Capital Preservation First":
                    sl_mult = 1.0; tp_mult = 2.0
                elif risk_profile == "High Volatility Hunter":
                    sl_mult = 3.0; tp_mult = 4.0
                else: # Balanced
                    sl_mult = 2.0; tp_mult = 3.0

                # 2. Market Context (RSI)
                rsi = 50.0
                if df is not None and not df.empty:
                    rsi = Indicators.rsi(df['close'], 14).iloc[-1]
                
                if "scalp" in strategy_name:
                    # Scalping: Tighter stops, quicker targets
                    sl_mult *= 0.6  # Tighter relative to profile
                    tp_mult *= 0.6
                    
                    # Dynamic Trailing based on RSI Extension
                    # If we are winning and RSI is extended, tighten SL significantly
                    if side == "BUY" and rsi > 65:
                         sl_mult = 0.5 # Protect gains
                         self.add_log(f"🧠 AI Context: RSI High ({rsi:.1f}), tightening Scalp SL to 0.5 ATR")
                    elif side == "SELL" and rsi < 35:
                         sl_mult = 0.5
                         self.add_log(f"🧠 AI Context: RSI Low ({rsi:.1f}), tightening Scalp SL to 0.5 ATR")
                         
                elif "trend" in strategy_name:
                     # Trend Following: Give room to breathe
                     sl_mult *= 1.5
                     tp_mult *= 1.6 # Reward risk
            except Exception as e:
                self.add_log(f"⚠️ Context Logic Error: {e}")
                sl_mult = 2.0; tp_mult = 3.0
            
            MIN_DIST_PCT = 0.001 # 0.1% minimal buffer
            
            # --- SAFETY CLAMP (Active Management Sanity Check) ---
            ideal_sl_dist = atr_val * sl_mult
            ideal_tp_dist = atr_val * tp_mult
            
            MAX_SL_DIST_PCT = 0.10 # 10% Max SL
            MAX_TP_DIST_PCT = 0.20 # 20% Max TP (was causing +400% targets)
            
            if ideal_sl_dist > current_price * MAX_SL_DIST_PCT:
                 self.add_log(f"🛡️ Safety Clamp: Limiting SL Calc ({ideal_sl_dist:.4f}) to 10%")
                 ideal_sl_dist = current_price * MAX_SL_DIST_PCT
                 
            if ideal_tp_dist > current_price * MAX_TP_DIST_PCT:
                 self.add_log(f"🛡️ Safety Clamp: Limiting TP Calc ({ideal_tp_dist:.4f}) to 20%")
                 ideal_tp_dist = current_price * MAX_TP_DIST_PCT
            # -----------------------------------------------------
            
            if side == "BUY":
                # LONG: SL below Entry, TP above Entry
                # Use Current Price as base for recalibration logic if intended to trail, 
                # but standard is Entry Based. Let's stick to Entry based for consistency unless trailing.
                
                ideal_sl = entry_price - ideal_sl_dist
                ideal_tp = entry_price + ideal_tp_dist
                
                # Validation: SL must be < Current Price
                if ideal_sl >= current_price * (1 - MIN_DIST_PCT):
                    # self.add_log(f"⚠️ Ideal SL ({ideal_sl:.2f}) above current price ({current_price:.2f}). Adjusting.") # Reduced noise
                    ideal_sl = current_price * (1 - 0.005) # 0.5% below current
                
                # Validation: TP must be > Current Price
                if ideal_tp <= current_price * (1 + MIN_DIST_PCT):
                     ideal_tp = current_price * (1 + 0.005) 

            else:
                # SHORT: SL above Entry, TP below Entry
                ideal_sl = entry_price + ideal_sl_dist
                ideal_tp = entry_price - ideal_tp_dist
                
                # Validation: SL must be > Current Price
                if ideal_sl <= current_price * (1 + MIN_DIST_PCT):
                    # self.add_log(f"⚠️ Ideal SL ({ideal_sl:.2f}) below current price ({current_price:.2f}). Adjusting.")
                    ideal_sl = current_price * (1 + 0.005) 
                    
                # Validation: TP must be < Current Price
                if ideal_tp >= current_price * (1 - MIN_DIST_PCT):
                     ideal_tp = current_price * (1 - 0.005)

            current_sl = float(self.active_trade.get("sl") or 0)
            current_tp = float(self.active_trade.get("tp") or 0)
            
            sl_diff = abs(current_sl - ideal_sl) / current_sl if current_sl else 1.0
            tp_diff = abs(current_tp - ideal_tp) / current_tp if current_tp else 1.0
            
            TP_SL_RECALIBRATION_THRESHOLD_PCT = 0.02 
            is_divergent = (sl_diff > TP_SL_RECALIBRATION_THRESHOLD_PCT) or (tp_diff > TP_SL_RECALIBRATION_THRESHOLD_PCT)
            
            if not is_divergent:
                self.add_log(f"✅ Audit: Orders aligned locally. Verifying exchange...")
                # return "UNCHANGED", "Orders are aligned."  <-- REMOVED to force verification
            else:
                self.add_log(f"⚠️ Audit: Divergence detected (Price: {current_price:.2f}). Updating to SL: {ideal_sl:.2f} | TP: {ideal_tp:.2f}")
            
                with self.trade_lock:
                    self.active_trade["sl"] = ideal_sl
                    self.active_trade["tp"] = ideal_tp
            
            # Force verification immediately to sync with exchange
            self._verify_and_enforce_sl_tp(symbol, self.active_trade, bypass_cooldown=True)
            StateManager.save_state(self)
            
            return "UPDATED", f"Orders recalibrated to SL: {ideal_sl:.2f}, TP: {ideal_tp:.2f}"
            
        except Exception as e:
            self.add_log(f"❌ Recalibrate Error: {e}")
            return "ERROR", str(e)
