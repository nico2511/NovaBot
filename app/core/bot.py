
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

from app.core.config import config
from app.core.risk_manager import RiskManager
from app.core.constants import *
from app.core.state_manager import StateManager
from app.services.hyperliquid_service import hyperliquid_service
from app.services.discord_service import discord_service
from app.core.scanner_job import ScannerJob
from app.core.trade_recorder import TradeRecorder
from app.core.asset_gamification import AssetGamification, AccountLevel
from strategies.engine import StrategyEngine
from app.services.ia import ia_service
from app.services.indicators import Indicators
from app.utils.data_processing import get_dynamic_context

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
        self.max_positions = 1 # GLOBAL QUOTA
        self.strategy_engine = StrategyEngine(self.risk_manager)
        self.is_running = False
        self.trading_enabled = False
        self.thread = None
        self.account_value = 0.0
        self.latest_data = pd.DataFrame()
        self.latest_analysis = {}
        self.signals_log = deque(maxlen=200)
        self.logs = deque(maxlen=1000)
        self.latest_strategy_result = {}
        self.active_symbol = "BTC"
        self.last_candle_time = None
        self.active_trade = None
        self.trading_enabled = False # Master Switch
        self.is_running = False      # Loop Switch
        self.active_strategy_name = "SmartTrend"
        self.active_strategies = []

        # Scanner Settings defaults
        # Scanner Settings defaults (Seeded from user_settings API via config)
        self.scanner_settings = {
            "enabled": config.SCANNER_ENABLED,
            "interval": config.SCANNER_INTERVAL,
            "min_score": config.SCANNER_MIN_SCORE,
            "auto_switch": config.SCANNER_AUTO_SWITCH,
            "gamification_enabled": config.SCANNER_GAMIFICATION
        }

        # Global Settings Defaults (Ensures fields exist even if file is missing)
        # Global Settings Defaults (Seeded from user_settings API via config)
        self.global_settings = {
            "max_positions": config.DEFAULT_MAX_POSITIONS,
            "daily_stop_loss": config.DEFAULT_DAILY_STOP_LOSS,
            "trading_timeframe": config.TRADING_TIMEFRAME,
            "bot_persona": config.BOT_PERSONA,
            "risk_profile": config.RISK_PROFILE,
            "ai_thresholds": {
                "high": config.AI_CONF_THRESHOLD_HIGH,
                "medium": config.AI_CONF_THRESHOLD_MEDIUM,
                "low": config.AI_CONF_THRESHOLD_LOW
            },
            "available_personas": ["Conservative Scalper", "Aggressive Day Trader", "Sniper"],
            "available_risk_profiles": ["Capital Preservation First", "Balanced Growth", "High Volatility Hunter"],
            "default_leverage": config.DEFAULT_LEVERAGE,
            "default_margin_type": "ISOLATED"
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
        self._initial_position_analyzed = False
        
        # Candle analysis cache
        self.last_analyzed_candle = None
        
        # Debounce for "Position Vanished" check
        self.missing_pos_counter = 0
        
        # SL/TP Sync Cooldown (prevent infinite loop)
        self._last_sltp_sync_time = None
        self._sltp_sync_cooldown = 60  # Wait 60s after sync before re-verifying
        
        # AI Call Management
        self.last_ai_call = 0 
        self.ai_call_cooldown = config.AI_CALL_COOLDOWN 
        
        # Leverage state
        self._leverage_synced = False 
        
        # Cooldown tracking (anti-overtrading)
        self._last_trade_info = {"symbol": None, "direction": None, "time": None}
        
        # Load persisted state
        try:
            state = StateManager.load_state(self)
            
            # Load trading params from scanner_settings (centralized source)
            requested_max = self.scanner_settings.get("max_positions", 1)
            
            try:
                balance_data = hyperliquid_service.get_account_balance()
                equity = balance_data.get("equity", 0) if balance_data.get("status") == "success" else 0
                gam = AssetGamification(equity)
                
                if gam.level == AccountLevel.GOBLIN:
                    max_allowed = 1
                elif gam.level == AccountLevel.MERCENARY:
                    max_allowed = 2
                else:
                    max_allowed = 3
                
                self.max_positions = min(requested_max, max_allowed)
                
                if requested_max > max_allowed:
                    self.add_log(f"⚙️ Max positions capped: {requested_max} → {self.max_positions} (Level {gam.level.value})")
                else:
                    self.add_log(f"⚙️ Max positions: {self.max_positions}")
                    
            except Exception as e:
                self.max_positions = requested_max
                print(f"⚠️ Gamification check failed: {e}. Using requested: {requested_max}")
                    
        except Exception as e:
            print(f"Error loading state: {e}")
            
        # Initialize Services
        self.scanner_job = ScannerJob(self)
        self.trade_recorder = TradeRecorder()
        self.gamification = AssetGamification(0)
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
        
        # SAFETY CHECK: Ensure we don't carry over ghost positions
        with self.trade_lock:
            if self.active_trade and self.active_trade.get('symbol') != new_symbol:
                self.add_log(f"⚠️ Warning: Switching context while active trade exists on {self.active_trade['symbol']}. State cleared.")
                self.active_trade = None
        
        self.active_symbol = new_symbol
        
        try:
            if hyperliquid_service.ws_manager:
                hyperliquid_service.ws_manager.add_symbol(new_symbol)
        except Exception as e:
            self.add_log(f"⚠️ Failed to update WebSocket subscription: {e}")
        
        StateManager.save_state(self)

    def _prepare_ai_context(self, position_data: dict = None) -> dict:
        """Prepare comprehensive market context for professional AI analysis"""
        if not hasattr(self, 'latest_data') or self.latest_data.empty:
            return {}
        
        df = self.latest_data
        current_price = float(df['close'].iloc[-1])
        
        # Technical Indicators
        rsi = float(df['RSI_14'].iloc[-1]) if 'RSI_14' in df.columns else None
        atr = float(df['ATRr_14'].iloc[-1]) if 'ATRr_14' in df.columns else None
        
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

        # FIX: Regime definition aligned with Architecture (ADX > 25 = TREND)
        regime = "TREND" if adx_value > 25 else "RANGE"
        
        # Market Bias maintained via EMA alignment
        market_bias = "BULLISH" if ema_20 > ema_50 else "BEARISH"
        
        # Add ADX to dynamic context
        dynamic_ctx = get_dynamic_context(df)
        dynamic_ctx['adx'] = round(adx_value, 2)
        
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
            
            dynamic_ctx['bb_upper'] = round(bb_upper, 4)
            dynamic_ctx['bb_middle'] = round(bb_middle, 4)
            dynamic_ctx['bb_lower'] = round(bb_lower, 4)
            dynamic_ctx['bb_position'] = bb_position
            dynamic_ctx['bb_width'] = round(bb_width, 2)
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
            **dynamic_ctx
        }

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
        # CRITICAL SAFETY: Verify symbol context
        if symbol != self.active_symbol:
             self.add_log(f"🚨 CRITICAL: Attempted to close {symbol} while active symbol is {self.active_symbol}. EXIT ABORTED.")
             return False
             
        self.add_log(f"🔒 ATOMIC EXIT START: Closing {symbol} ({reason})")
        
        try:
            result = hyperliquid_service.close_position(symbol)
            
            if result.get("status") == "success":
                final_positions = hyperliquid_service.get_positions()
                remaining = next((p for p in final_positions if p["symbol"] == symbol), None)
                
                if not remaining or float(remaining["size"]) == 0:
                     self.add_log(f"✅ POSITION CLOSED: {symbol}")
                     self.add_log(f"🧹 Cleaning post-trade orphans on {symbol}...")
                     hyperliquid_service.cancel_all_orders(symbol)
                     
                     pnl_usdc = 0
                     with self.trade_lock:
                         if self.active_trade:
                             entry = self.active_trade.get("entry", 0)
                             active_side = self.active_trade.get("side", "BUY")
                             exit_px = hyperliquid_service.get_current_price(symbol)
                             size = self.active_trade.get("size", 0)
                             
                             if active_side == "BUY":
                                 pnl_usdc = (exit_px - entry) * size
                             else:
                                 pnl_usdc = (entry - exit_px) * size
                                 
                             self.trade_recorder.add_trade({
                                 "symbol": symbol,
                                 "strategy": self.active_trade.get("strategy", "Unknown"),
                                 "side": active_side,
                                 "entry_price": entry,
                                 "exit_price": exit_px,
                                 "size": size,
                                 "pnl_usdc": pnl_usdc,
                                 "exit_reason": reason,
                                 "exit_time": pd.Timestamp.now().isoformat(),
                                 "entry_indicators": self.active_trade.get("entry_indicators", {})
                             })
                             
                             discord_service.send_alert(
                                 f"🏁 TRADE CLOSED: {symbol}",
                                 f"Reason: {reason}\nPnL: ${pnl_usdc:.2f}",
                                 color="FFFF00"
                             )
                             self.risk_manager.record_trade_close(pnl_usdc)
                             self.active_trade = None
                             StateManager.save_state(self)
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
            
            # 1. RSI Veto (Tightened: 42 for SELL, 72 for BUY)
            rsi = market_context.get("rsi")
            if rsi is not None:
                if signal == "BUY" and rsi > 72:
                    return f"HARD VETO: RSI Overbought ({rsi:.1f} > 72) @ {price:.2f}"
                if signal == "SELL" and rsi < 42:
                    return f"HARD VETO: RSI Oversold ({rsi:.1f} < 42) @ {price:.2f}"

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
            return None
        except Exception as e:
            print(f"⚠️ Veto Check Error: {e}")
            return None
    def _verify_and_enforce_sl_tp(self, symbol: str, trade_data: dict, bypass_cooldown: bool = False):
        """Consolidated verification: Fetch Exchange Orders -> Compare -> Enforce if needed."""
        # GUARD: Only enforce if trading is ENABLED (Real Trading)
        if not self.trading_enabled:
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

    def _check_external_close(self, symbol: str, trade: dict) -> bool:
        """Detect if position was closed externally (by user or exchange)"""
        positions = hyperliquid_service.get_positions()
        real_pos = next((p for p in positions if p["symbol"] == symbol and float(p['size']) > 0), None)
        
        if not real_pos:
            self.missing_pos_counter += 1
            if self.missing_pos_counter >= 3:
                self.add_log(f"⚠️ Position vanished (External Close confirmed). Clearing state.")
                
                exit_price = hyperliquid_service.get_current_price(symbol)
                entry = trade.get("entry", 0)
                size = trade.get("size", 0)
                side = trade.get("side", "BUY")
                pnl_usdc = (exit_price - entry) * size if side == "BUY" else (entry - exit_price) * size
                
                self.trade_recorder.add_trade({
                      "symbol": symbol,
                      "strategy": trade.get("strategy", "Unknown"),
                      "side": side,
                      "entry_price": entry,
                      "exit_price": exit_price,
                      "size": size,
                      "pnl_usdc": pnl_usdc,
                      "exit_reason": "External Close",
                      "exit_time": pd.Timestamp.now().isoformat(),
                      "entry_indicators": trade.get("entry_indicators", {})
                })
                
                discord_service.send_alert(
                    f"🏁 TRADE CLOSED (Exchange): {symbol}",
                    f"Reason: External Close (SL/TP likely)\nPnL: ${pnl_usdc:.2f}",
                    color="00FF00" if pnl_usdc >= 0 else "FF0000"
                )
                
                with self.trade_lock:
                    self.active_trade = None
                    StateManager.save_state(self)
                self.missing_pos_counter = 0
                return True
        else:
            self.missing_pos_counter = 0
            
        return False

    def _update_trailing_stops(self, trade: dict, current_price: float) -> bool:
        """Check and update Smart Break-Even and Trailing Stops"""
        entry_price = trade.get("entry")
        tp_price = trade.get("tp")
        sl_price = trade.get("sl")
        side = trade.get("side")
        new_sl = None
        
        if entry_price and tp_price and sl_price:
            if side == "BUY":
                total_dist = tp_price - entry_price
                current_dist = current_price - entry_price
                progress_pct = (current_dist / total_dist) * 100 if total_dist != 0 else 0
                
                # 1. Smart BE (Moved to 60% progress, locks 0.2% profit with 0.3% buffer)
                if progress_pct > 60:
                    be_price = entry_price * 1.002 # 0.2% profit (covers fees + buffer)
                    # Safety: Ensure current price is at least 0.3% away from new SL
                    if sl_price < be_price and current_price > (be_price * 1.003):
                        new_sl = be_price
                        self.add_log(f"🛡️ Smart BE: >60% target. Moving SL to {new_sl:.2f} (Price: {current_price:.2f})")

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
                    self.active_trade["sl"] = new_sl
                    StateManager.save_state(self)
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

    def _manage_active_trade(self):
        """Centralized Active Trade Management (Refactored)"""
        with self.trade_lock:
            trade = self.active_trade
            if not trade: return
            
        symbol = trade["symbol"]
        
        # 1. External Close Check
        if self._check_external_close(symbol, trade):
            return

        current_price = hyperliquid_service.get_current_price(symbol)
        
        # --- STRATEGY DELEGATION (Override) ---
        # Ask the strategy if it wants to handle this trade's management
        handled_by_strategy = False
        strategy_name = trade.get("strategy")
        
        if strategy_name and strategy_name in self.strategy_engine.strategies:
            strat_instance = self.strategy_engine.strategies[strategy_name]
            
            # Check if strategy overrides management
            custom_updates = strat_instance.manage_trade(
                trade, 
                current_price, 
                # Pass latest dataframe if available (optional but good for context)
                df=self.latest_data if hasattr(self, 'latest_data') else None
            )
            
            if custom_updates is not None:
                handled_by_strategy = True
                
                # Apply strategy updates (e.g. SL modification)
                if custom_updates:
                    with self.trade_lock:
                        changed = False
                        if "sl" in custom_updates:
                             self.active_trade["sl"] = custom_updates["sl"]
                             changed = True
                             self.add_log(f"🤖 Strategy {strategy_name} updated SL to {custom_updates['sl']}")
                        
                        if "tp" in custom_updates:
                             self.active_trade["tp"] = custom_updates["tp"]
                             changed = True
                             self.add_log(f"🤖 Strategy {strategy_name} updated TP to {custom_updates['tp']}")
                             
                        if changed:
                            self._verify_and_enforce_sl_tp(symbol, self.active_trade, bypass_cooldown=True) # FORCE SYNC
                            StateManager.save_state(self)

        # 2. Default Smart Trailing (Fallback)
        # Only run default logic if strategy didn't handle it
        if not handled_by_strategy:
            if self._update_trailing_stops(trade, current_price):
                 self.add_log(f"🔄 Trailing Stop Updated. Enforcing on Exchange...")
                 self._verify_and_enforce_sl_tp(symbol, self.active_trade, bypass_cooldown=True) # FORCE SYNC

        # 3. Local Local Exit Check (Universal safety net)
        # Even if strategy handled logic, we still respect the committed SL/TP triggers here
        self._check_local_exits(trade, symbol, current_price)

    def force_sync(self):
        """Manually trigger synchronization with Exchange."""
        self.add_log("🔄 FORCE SYNC: Initiated by User")
        
        try:
            positions = hyperliquid_service.get_positions()
            
            if positions:
                pos = positions[0]
                symbol = pos["symbol"]
                
                if self.active_symbol != symbol:
                    self.active_symbol = symbol
                    StateManager.save_state(self)
                    self.add_log(f"✅ SYNC: Symbol corrected to {symbol}")
                
                with self.trade_lock:
                    self.active_trade = {
                        "symbol": symbol,
                        "side": "BUY" if float(pos["szi"]) > 0 else "SELL",
                        "entry": float(pos["entryPx"]),
                        "size": abs(float(pos["szi"])),
                        "sl": self.active_trade.get("sl", 0) if self.active_trade else 0,
                        "tp": self.active_trade.get("tp", 0) if self.active_trade else 0,
                        "strategy": self.active_trade.get("strategy", "Manual/Sync") if self.active_trade else "Manual (Sync)",
                        "timestamp": self.active_trade.get("timestamp", pd.Timestamp.now().isoformat()) if self.active_trade else pd.Timestamp.now().isoformat(),
                        "pnl": float(pos["unrealizedPnl"]),
                        "max_pnl": float(pos["unrealizedPnl"]),
                        "status": "OPEN",
                        "ai_analysis": self.active_trade.get("ai_analysis") if self.active_trade else None
                    }
                    StateManager.save_state(self)
                self.add_log(f"✅ SYNC: Trade state updated for {symbol}")
                
                def run_analysis():
                    self.add_log(f"⏳ SYNC: Waiting 5s before AI analysis for data stability...")
                    time.sleep(5)
                    try:
                        self.add_log(f"🤖 FORCE SYNC: Running AI Analysis on {symbol}")
                        df = hyperliquid_service.get_candles(symbol, "15m", 50)
                        if not df.empty:
                            ai_result = ia_service.analyze_position_risk(
                                symbol=symbol,
                                position_data=pos,
                                market_data={"close": float(df['close'].iloc[-1]), "regime": "UNKNOWN"}
                            )
                            if ai_result:
                                ai_data = json.loads(ai_result) if isinstance(ai_result, str) else ai_result
                                
                                self.ai_cache[f"position_analysis_{symbol}"] = ai_data
                                self.ai_cache["last_position_analysis"] = ai_data
                                
                                with self.trade_lock:
                                    if self.active_trade:
                                        self.active_trade["ai_analysis"] = ai_data
                                
                                self.add_log(f"✅ AI Analysis Updated: {ai_data.get('risk_level')}")
                    except Exception as e:
                        self.add_log(f"⚠️ AI Force Sync Failed: {e}")

                threading.Thread(target=run_analysis, daemon=True).start()
                return {"status": "success", "message": "Sync and Analysis started"}
            else:
                with self.trade_lock:
                    self.active_trade = None
                    StateManager.save_state(self)
                self.add_log("ℹ️ FORCE SYNC: No positions found. State cleared.")
                return {"status": "success", "message": "State cleared (No position)"}
                
        except Exception as e:
            self.add_log(f"❌ FORCE SYNC Failed: {e}")
            return {"status": "error", "message": str(e)}

    def _enforce_leverage(self):
        """Enforce leverage based on Gamification and Settings"""
        try:
            # Check if Gamification is explicitly disabled in settings
            gamification_active = self.scanner_settings.get("gamification_enabled", True)
            
            # Fallback: Use global_settings default_leverage when gamification disabled
            default_leverage = self.global_settings.get("default_leverage", 5)
            default_margin_type = self.global_settings.get("default_margin_type", "Cross")
            
            # Read trading params from scanner_settings (centralized source) with fallbacks
            requested_leverage = int(self.scanner_settings.get("leverage", default_leverage))
            margin_type = self.scanner_settings.get("margin_type", default_margin_type)
            is_cross = (margin_type == "Cross")
            
            target_leverage = requested_leverage
            
            if gamification_active:
                try:
                    balance_data = hyperliquid_service.get_account_balance()
                    current_equity = balance_data.get("equity", 0.0) if balance_data.get("status") == "success" else 0.0
                    gam = AssetGamification(current_equity)
                    max_leverage = gam.get_max_leverage()
                    
                    target_leverage = min(requested_leverage, max_leverage)
                    
                    if requested_leverage > max_leverage:
                        self.add_log(f"🎮 GAMIFICATION: Leverage capped {requested_leverage}x → {target_leverage}x (Level: {gam.level.value})")
                except Exception as gam_err:
                    self.add_log(f"⚠️ Gamification check failed: {gam_err}")
            else:
                target_leverage = int(self.scanner_settings.get("leverage", default_leverage))
                self.add_log(f"ℹ️ Gamification disabled. Using leverage: {target_leverage}x (default: {default_leverage}x)")
            
            if 'current_equity' in locals():
                self.account_value = float(current_equity)

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
            
            try:
                self.add_log("🔄 INITIAL SYNC: Checking Hyperliquid for existing positions...")
                real_positions = hyperliquid_service.get_positions()
                
                if real_positions:
                    main_position = real_positions[0]
                    position_symbol = main_position["symbol"]
                    
                    self.add_log(f"✅ SYNC: Found position on Hyperliquid: {position_symbol}")
                    
                    if self.active_symbol != position_symbol:
                        self.add_log(f"⚠️ SYNC: Symbol mismatch detected!")
                        old_symbol = self.active_symbol
                        self.switch_active_symbol(position_symbol)
                        self.add_log(f"✅ SYNC: Symbol switched from {old_symbol} to {position_symbol}")
                    
                    if not self.active_trade:
                        self.add_log(f"🕵️ SYNC: Adopting orphan position {position_symbol} into memory")
                        self._adopt_existing_position(main_position)
                    
                    self.add_log("⏳ SYNC: Waiting 20 seconds for full synchronization...")
                    time.sleep(20)
                    self.add_log("✅ SYNC: Synchronization complete, ready for AI analysis")
                    
                    try:
                        self.add_log(f"📊 Fetching market data for {self.active_symbol}...")
                        df_sync = hyperliquid_service.get_candles(self.active_symbol, interval="15m", limit=200)
                        
                        if not df_sync.empty:
                            numeric_cols = ['open', 'high', 'low', 'close', 'volume']
                            for col in numeric_cols:
                                if col in df_sync.columns:
                                    df_sync[col] = df_sync[col].astype(float)
                            
                            self.strategy_engine.analyze(df_sync)
                            self.latest_data = df_sync
                            self.add_log("✅ Market data & indicators ready for AI")
                        else:
                            self.add_log("⚠️ Sync Warning: No candles received")
                    except Exception as e_data:
                        self.add_log(f"⚠️ Sync Data Error: {e_data}")
                    
                    if not self._initial_position_analyzed:
                        try:
                            import json
                            self.add_log(f"🤖 Running AI analysis on {position_symbol} position...")
                            market_context = self._prepare_ai_context(position_data=main_position)
                            ai_result = ia_service.analyze_position_risk(
                                symbol=self.active_symbol,
                                position_data=main_position,
                                market_data=market_context
                            )
                            if ai_result:
                                ai_data = json.loads(ai_result) if isinstance(ai_result, str) else ai_result
                                reasoning = ai_data.get('reasoning', 'Position analysée')
                                risk_level = ai_data.get('risk_level', 'UNKNOWN')
                                self.add_log(f"🤖 IA Startup ({risk_level}): {reasoning}")
                                self.ai_cache[f"position_analysis_{self.active_symbol}"] = ai_data
                                self.ai_cache["last_position_analysis"] = ai_data
                                self.ai_cache["last_position_analysis_time"] = pd.Timestamp.now()
                                
                                if risk_level in ["HIGH", "CRITICAL"]:
                                    discord_service.send_alert(
                                        f"🤖 AI Analysis - {risk_level} RISK",
                                        f"Symbol: {self.active_symbol}\n{reasoning}",
                                        color="FF0000" if risk_level == "CRITICAL" else "FFA500"
                                    )
                            self._initial_position_analyzed = True
                        except Exception as e:
                            self.add_log(f"⚠️ Error in startup AI analysis: {e}")
                else:
                    self.add_log("ℹ️ SYNC: No positions found on Hyperliquid")
                    
            except Exception as e:
                self.add_log(f"⚠️ SYNC Error: {e}")
            
            self.startup_sync_done = True
            self.add_log("✅ STARTUP SYNC: Complete")
        
        while self.is_running:
            # Dynamic Leverage & Gamification Enforcement
            if self.trading_enabled and not self._leverage_synced:
                self._enforce_leverage()
            elif not self.trading_enabled:
                self._leverage_synced = False

            action = None
            sl = None
            tp = None
            
            # Continuous Adoption
            if not self.active_trade:
                try:
                    real_positions_manual = hyperliquid_service.get_positions()
                    if real_positions_manual:
                        manual_pos = next((p for p in real_positions_manual if p["symbol"] == self.active_symbol and float(p['size']) != 0), None)
                        if manual_pos:
                            self.add_log(f"🕵️ MANUAL TRADE DETECTED: Adopting {self.active_symbol} position...")
                            self._adopt_existing_position(manual_pos)
                            continue
                except Exception: pass
            
            try:
                acc_data = hyperliquid_service.get_account_balance()
                if acc_data.get("status") == "success":
                   self.account_value = float(acc_data.get("total_equity", 0))
            except: pass
            
            try:
                if self.active_trade:
                     self._manage_active_trade()
                     time.sleep(10)
                     continue

                self.add_log("🔄 Entering strategy analysis...")
                df_15m = hyperliquid_service.get_candles(self.active_symbol, interval="15m", limit=200)
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
                
                signals = result.get("signals", [])
                if signals:
                    sig = signals[0]
                    if sig.get("signal") and sig.get("price"):
                        
                        # --- COOLDOWN CHECK (BEFORE AI to save tokens) ---
                        cooldown_minutes = self.global_settings.get("cooldown_minutes", 0)
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
                        strat_name = sig.get('strategy')
                        strat_obj = self.strategy_engine.strategies.get(strat_name)
                        strategy_persona = getattr(strat_obj, 'AI_PERSONA', None)
                        
                        current_time = time.time()
                        time_since_last_call = current_time - self.last_ai_call
                        
                        approved = False
                        # REMOVED: Auto-approval during cooldown (security risk)
                        # Always validate with AI for safety
                        self.add_log(f"🤖 Validating signal: {sig.get('signal')} from {sig.get('strategy')}")
                        val_res = ia_service.validate_signal(sig, market_context, strategy_persona=strategy_persona)
                        self.last_ai_call = current_time
                        
                        try:
                            import json
                            if val_res.get("raw_output"):
                                ai_data = json.loads(ia_service.extract_json(val_res["raw_output"]))
                                approved = ai_data.get("approved", False)
                                confidence = ai_data.get("confidence", 0)
                                risk_level = ai_data.get("risk_level", "MEDIUM").upper()
                                
                                if approved:
                                    # HYBRID CONFIDENCE THRESHOLD CHECK
                                    required_conf = config.AI_CONF_THRESHOLD_MEDIUM  # Default
                                    if risk_level == "HIGH":
                                        required_conf = config.AI_CONF_THRESHOLD_HIGH
                                    elif risk_level == "LOW":
                                        required_conf = config.AI_CONF_THRESHOLD_LOW
                                    
                                    if confidence >= required_conf:
                                        self.add_log(f"✅ AI APPROVED (Conf: {confidence}% >= {required_conf}% for {risk_level} risk)", metadata=ai_data)
                                        if ai_data.get("suggested_adjustments"):
                                            adj = ai_data["suggested_adjustments"]
                                            if adj.get("sl"): sig["sl"] = adj["sl"]
                                            if adj.get("tp"): sig["tp"] = adj["tp"]
                                    else:
                                        self.add_log(f"⚠️ AI approved but CONFIDENCE TOO LOW ({confidence}% < {required_conf}% for {risk_level} risk)", metadata=ai_data)
                                        approved = False
                                else:
                                    self.add_log(f"❌ AI REJECTED: {ai_data.get('reasoning')}", metadata=ai_data)
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
                            
                            size = self.risk_manager.calculate_position_size(entry_price, sl_price, equity)
                            # ---------------------------------------------------
                            # 2. EXECUTION LOGIC (Live)
                            # ---------------------------------------------------
                            if self.trading_enabled:
                                
                                # Sync Positions periodically
                                if int(time.time()) % 60 == 0:
                                     self.force_sync()
                                
                                # Capture full market snapshot for trade analysis
                                entry_indicators = {
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
                                    "current_price": result.get("current_price"),
                                    "ai_confidence": confidence if 'confidence' in locals() else 0,
                                    "ai_reasoning": (ai_data.get("reasoning", "") if 'ai_data' in locals() else sig.get("reason", "Strategy Signal"))[:200]
                                }
                                
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
                
                # Optimized Sleep Loop (Non-blocking)
                sleep_duration = 10 if self.active_trade else (15 if signals else 60)
                self.add_log(f"⏸️ Next analysis in {sleep_duration}s...")
                for _ in range(int(sleep_duration)):
                    if not self.is_running: break
                    time.sleep(1)
                
            except Exception as e:
                self.add_log(f"❌ Error in trading loop: {e}")
                time.sleep(5)
        
        self.add_log("⏸️ Trading loop stopped")

    def _adopt_existing_position(self, active_pos):
        """Adopt an existing position from the exchange into the bot's memory."""
        try:
            print(f"      Size: {active_pos['size']} | Entry: {active_pos['entry_price']}")
            
            side = active_pos['side']
            size = float(active_pos['size'])
            entry_price = float(active_pos['entry_price'])
            leverage = float(active_pos.get('leverage', 1.0))
            
            with self.trade_lock:
                self.active_trade = {
                    "symbol": self.active_symbol,
                    "side": side,
                    "entry": entry_price,
                    "size": size,
                    "leverage": leverage,
                    "oid": "external_position",
                    "sl": 0,
                    "tp": 0,
                    "strategy": "Manual (Adopting...)",
                    "entry_time": pd.Timestamp.now().isoformat(),
                    "pnl": float(active_pos.get('pnl', 0)),
                    "max_pnl": float(active_pos.get('pnl', 0)),
                    "status": "OPEN",
                    "ai_analysis": None,
                    "metadata": {"stage": "1_raw_adoption"}
                }
                StateManager.save_state(self)
            print("   🔒 STAGE 1: Position locked in memory (Adopting...)")
            
            print("   🔍 STAGE 2: Analyzing market context & existing orders...")
            try:
                df_15m = hyperliquid_service.get_candles(self.active_symbol, "15m", 200)
                current_price = df_15m['close'].iloc[-1]
                
                print("      🔎 Checking for existing SL/TP orders...")
                existing_orders = hyperliquid_service.info.open_orders(config.HL_ACCOUNT_ADDRESS)
                symbol_orders = [o for o in existing_orders if o.get("coin") == self.active_symbol]
                
                existing_sl = None
                existing_tp = None
                
                for order in symbol_orders:
                    trigger_px = float(order.get("triggerPx", 0))
                    is_reduce = order.get("reduceOnly", False)
                    
                    if is_reduce and trigger_px > 0:
                        if side == "BUY":
                            if trigger_px < current_price: existing_sl = trigger_px
                            else: existing_tp = trigger_px
                        else: # SELL
                            if trigger_px > current_price: existing_sl = trigger_px
                            else: existing_tp = trigger_px
                
                pnl_pct = ((current_price - entry_price) / entry_price) * 100 if side == "BUY" else ((entry_price - current_price) / entry_price) * 100
                print(f"      💰 Position PnL: {pnl_pct:+.2f}%")
                
                should_modify = False
                modification_reason = ""
                sl_price = 0
                tp_price = 0
                strategy_name = "Manual (Adopted)"
                adoption_metadata = {}

                if existing_sl and existing_tp:
                    BE_THRESHOLD = 1.5
                    if pnl_pct >= BE_THRESHOLD:
                        sl_is_be = (existing_sl >= entry_price * 1.001) if side == "BUY" else (existing_sl <= entry_price * 0.999)
                        if not sl_is_be:
                            should_modify = True
                            modification_reason = f"Break Even (Position +{pnl_pct:.1f}%)"
                            sl_price = entry_price * 1.002 if side == "BUY" else entry_price * 0.998
                            tp_price = existing_tp
                        else:
                            print("      ✅ Orders valid (BE active)")
                    else:
                        print("      ✅ Orders valid")
                    
                    if not should_modify:
                        sl_price = existing_sl
                        tp_price = existing_tp
                        strategy_name = "Manual (Existing - Adopted)"
                        adoption_metadata = {"adopted_at_boot": True, "method": "existing"}
                else:
                    should_modify = True
                    modification_reason = "No protection detected"
                    
                    # Regime Detection
                    adx = 0
                    if 'ADX_14' in df_15m.columns: adx = float(df_15m['ADX_14'].iloc[-1])
                    else: 
                        adx_df = Indicators.adx(df_15m['high'], df_15m['low'], df_15m['close'], 14)
                        adx = float(adx_df['ADX'].iloc[-1])
                    
                    regime = "TREND" if adx > 25 else "RANGE"
                    
                    atr = 0
                    if 'ATRr_14' in df_15m.columns: atr = df_15m['ATRr_14'].iloc[-1]
                    else: atr = float(Indicators.atr(df_15m['high'], df_15m['low'], df_15m['close'], 14).iloc[-1])
                    
                    sl_mult = 2.0 if regime == "TREND" else 1.2
                    tp_rr = 2.5 if regime == "TREND" else 1.5
                    sl_dist = atr * sl_mult
                    
                    if side == "BUY":
                        sl_price = current_price - sl_dist
                        tp_price = current_price + (sl_dist * tp_rr)
                    else:
                        sl_price = current_price + sl_dist
                        tp_price = current_price - (sl_dist * tp_rr)
                        
                    strategy_name = f"Manual ({regime} - Adopted)"
                    adoption_metadata = {"adopted_at_boot": True, "method": "smart_calc", "regime": regime}

            except Exception as e:
                print(f"   ⚠️ Analysis Failed: {e}. Using Fallback.")
                should_modify = True
                modification_reason = "Analysis error"
                current_price = entry_price
                if side == "BUY":
                    sl_price = current_price * 0.98
                    tp_price = current_price * 1.05
                else:
                    sl_price = current_price * 1.02
                    tp_price = current_price * 0.95
                strategy_name = "Manual (Safety - Adopted)"
                adoption_metadata = {"adopted_at_boot": True, "method": "fallback"}

            print("   🛡️ STAGE 3: Protection Management...")
            with self.trade_lock:
                self.active_trade["sl"] = sl_price
                self.active_trade["tp"] = tp_price
                self.active_trade["strategy"] = strategy_name
                self.active_trade["metadata"] = adoption_metadata
                self.active_trade["status"] = "OPEN (ADOPTED)"
            
            if should_modify:
                print(f"      🔄 Reason: {modification_reason}")
                try:
                    is_long = (side == "BUY")
                    if is_long:
                        sl_p_api = 1 - (sl_price / entry_price)
                        tp_p_api = (tp_price / entry_price) - 1
                    else:
                        sl_p_api = (sl_price / entry_price) - 1
                        tp_p_api = 1 - (tp_price / entry_price)
                    
                    sl_p_api = max(0.001, sl_p_api)
                    tp_p_api = max(0.001, tp_p_api)

                    hyperliquid_service.set_sl_tp(
                        symbol=self.active_symbol,
                        entry_price=entry_price,
                        sl_percent=sl_p_api * 100,
                        tp_percent=tp_p_api * 100,
                        is_long=is_long,
                        quantity=size
                    )
                    print(f"      ✅ SL/TP Orders Updated: SL {sl_price:.4f} | TP {tp_price:.4f}")
                except Exception as e:
                    print(f"      ⚠️ API Order Failed: {e}")
            else:
                print(f"      ✅ Existing orders preserved")
            
            StateManager.save_state(self)
            print("   ✅ Adoption Complete.")

        except Exception as e:
            print(f"   ❌ Adoption Critical Failure: {e}")
            with self.trade_lock:
                self.active_trade = None

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
            
            if self.scanner_job:
                self.scanner_settings['enabled'] = True
                self.scanner_job.start()
                self.add_log("🕵️ Scanner auto-enabled with engine start")
                
            StateManager.save_state(self)
        else:
            self.add_log("⚠️ Bot already running with active thread, skipping start")

    def stop(self):
        """Stop the bot with complete graceful shutdown"""
        if self.is_running:
            self.is_running = False
            self.add_log("🛑 Initiating graceful shutdown...")
            
            if self.active_trade:
                try:
                    symbol = self.active_trade["symbol"]
                    self.add_log(f"🧹 Cancelling pending orders for {symbol}...")
                    hyperliquid_service.cancel_all_orders(symbol)
                    self.add_log("✅ Orders cancelled")
                except Exception as e:
                    self.add_log(f"⚠️ Failed to cancel orders: {e}")
            
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
                    from backend.market_data import get_hyperliquid_candles
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
                
                # 2. Market Context (RSI)
                rsi = 50.0
                if df is not None and not df.empty:
                    rsi = Indicators.rsi(df['close'], 14).iloc[-1]
                
                if "scalp" in strategy_name:
                    # Scalping: Tighter stops, quicker targets
                    sl_mult = 1.2
                    tp_mult = 1.8
                    
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
                     sl_mult = 3.0
                     tp_mult = 5.0
            except Exception as e:
                self.add_log(f"⚠️ Context Logic Error: {e}")
                sl_mult = 2.0; tp_mult = 3.0
            
            MIN_DIST_PCT = 0.001 # 0.1% minimal buffer for scalping support
            
            if side == "BUY":
                # LONG: SL below Entry, TP above Entry
                ideal_sl = entry_price - (atr_val * sl_mult)
                ideal_tp = entry_price + (atr_val * tp_mult)
                
                # Validation: SL must be < Current Price
                if ideal_sl >= current_price * (1 - MIN_DIST_PCT):
                    self.add_log(f"⚠️ Ideal SL ({ideal_sl:.2f}) above current price ({current_price:.2f}). Adjusting.")
                    ideal_sl = current_price * (1 - 0.002) # 0.2% below current
                
                # Validation: TP must be > Current Price
                if ideal_tp <= current_price * (1 + MIN_DIST_PCT):
                     ideal_tp = current_price * (1 + 0.002) # 0.2% above current

            else:
                # SHORT: SL above Entry, TP below Entry
                ideal_sl = entry_price + (atr_val * sl_mult)
                ideal_tp = entry_price - (atr_val * tp_mult)
                
                # Validation: SL must be > Current Price
                if ideal_sl <= current_price * (1 + MIN_DIST_PCT):
                    self.add_log(f"⚠️ Ideal SL ({ideal_sl:.2f}) below current price ({current_price:.2f}). Adjusting.")
                    ideal_sl = current_price * (1 + 0.002) # 0.2% above current
                    
                # Validation: TP must be < Current Price
                if ideal_tp >= current_price * (1 - MIN_DIST_PCT):
                     ideal_tp = current_price * (1 - 0.002) # 0.2% below current

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
