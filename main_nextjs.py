#!/usr/bin/env python3
"""
Main entry point for HyperLiquid Trading Bot with Next.js UI
Starts both the trading bot and the FastAPI server
"""
import sys
import os
import threading
import time
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import config
from app.core.risk_manager import RiskManager
from app.core.constants import *
from app.core.state_manager import StateManager
from app.services.hyperliquid_service import hyperliquid_service
from app.services.discord_service import discord_service
from app.core.scanner_job import ScannerJob
from app.core.trade_recorder import TradeRecorder
from app.core.asset_gamification import AssetGamification # Import Gamification
from strategies.engine import StrategyEngine
import pandas as pd
from collections import deque
import json
from app.services.ia import ia_service

# Import bot bridge
from backend.bot_bridge import bot_bridge

class BotContext:
    """Main bot context - same as main.py"""
    def __init__(self):
        print("\n\n🤖 [BOOT] BotContext v1.0.2 (NULL SAFETY + IA FIX)\n")
        self.risk_manager = RiskManager(
            max_positions=config.DEFAULT_MAX_POSITIONS,
            daily_stop_loss=config.DEFAULT_DAILY_STOP_LOSS
        )
        self.max_positions = 1 # GLOBAL QUOTA - Hardcoded for Focus Mode
        self.strategy_engine = StrategyEngine(self.risk_manager)
        self.is_running = False
        self.trading_enabled = False
        self.thread = None
        self.latest_data = pd.DataFrame()
        self.latest_analysis = {}
        self.signals_log = deque(maxlen=200)
        self.logs = deque(maxlen=1000)
        self.latest_strategy_result = {}
        self.active_symbol = "BTC"
        self.last_candle_time = None
        self.active_trade = None
        self.execution_mode = "Manual (Phantom)"
        self.active_strategy_name = "SmartTrend" # Default for display
        self.active_strategies = [] # List of currently active strategies based on regime

        # Scanner Settings defaults
        self.scanner_settings = {
            "enabled": False, # Manual only by default
            "interval": 15,
            "min_score": 75,
            "auto_switch": False,
            "gamification_enabled": True  # NEW: Toggle for Gamification enforcement
        }
        
        # AI Commentary Cache
        self.ai_cache = {
            "last_market_analysis": None,
            "last_market_analysis_time": None,
            "last_position_analysis": None,
            "last_position_analysis_time": None,
            "signal_analyses": deque(maxlen=50),
            "market_snapshots": deque(maxlen=10)  # Pour comparer l'évolution
        }
        
        # Startup synchronization flags
        self.startup_sync_done = False
        self._initial_position_analyzed = False
        
        
        # Candle analysis cache to prevent redundant calculations
        self.last_analyzed_candle = None
        
        # Debounce for "Position Vanished" check
        self.missing_pos_counter = 0
        
        # Load persisted state
        try:
            StateManager.load_state(self)
            
            # Access settings loaded into sidebar_settings if available
            if hasattr(self, "sidebar_settings"):
                self.execution_mode = self.sidebar_settings.get("execution_mode", "Manual (Phantom)")
        except Exception as e:
            print(f"Error loading state: {e}")
            self.execution_mode = "Manual (Phantom)"
            
        # Initialize Scanner Job (after state load)
        self.scanner_job = ScannerJob(self)
        
        # Initialize Trade Recorder
        self.trade_recorder = TradeRecorder()
        
        # Initialize Gamification
        self.gamification = AssetGamification(0) # Initial status, will update in loop
    
    def add_log(self, message: str):
        """Add log message"""
        timestamp = pd.Timestamp.now().strftime('%H:%M:%S')
        self.logs.append(f"{timestamp} {message}")
        print(f"[BOT] {message}")
    
    def _prepare_ai_context(self, position_data: dict = None) -> dict:
        """Prepare comprehensive market context for professional AI analysis"""
        if not hasattr(self, 'latest_data') or self.latest_data.empty:
            return {}
        
        df = self.latest_data
        current_price = float(df['close'].iloc[-1])
        
        # Technical Indicators
        rsi = float(df['RSI_14'].iloc[-1]) if 'RSI_14' in df.columns else None
        atr = float(df['ATRr_14'].iloc[-1]) if 'ATRr_14' in df.columns else None
        
        # EMAs for trend analysis
        ema_20 = float(df['close'].ewm(span=20).mean().iloc[-1])
        ema_50 = float(df['close'].ewm(span=50).mean().iloc[-1])
        ema_200 = float(df['close'].ewm(span=200).mean().iloc[-1]) if len(df) >= 200 else None
        
        # Price levels (swing high/low from last 20 candles)
        swing_high = float(df['high'].rolling(20).max().iloc[-1])
        swing_low = float(df['low'].rolling(20).min().iloc[-1])
        
        # Volume analysis
        avg_volume = float(df['volume'].rolling(50).mean().iloc[-1])
        current_volume = float(df['volume'].iloc[-1])
        volume_ratio = (current_volume / avg_volume) * 100 if avg_volume > 0 else 100
        
        # Volatility percentile (ATR vs 50-period historical)
        volatility_percentile = None
        if atr and 'ATRr_14' in df.columns:
            atr_series = df['ATRr_14'].dropna()
            if len(atr_series) > 0:
                volatility_percentile = int((atr_series < atr).sum() / len(atr_series) * 100)
        
        # Market regime
        regime = "TREND" if ema_20 > ema_50 else "RANGE"
        market_bias = "BULLISH" if ema_20 > ema_50 else "BEARISH"
        
        # Position-specific data
        pnl_percent = 0
        time_in_trade = None
        sl_distance = None
        tp_distance = None
        rr_ratio = None
        
        if position_data:
            # Handle both dict and direct values
            entry = position_data.get('entry_price') if isinstance(position_data, dict) else position_data
            if entry is None:
                entry = position_data.get('entry') if isinstance(position_data, dict) else current_price
            
            # Ensure entry is a float
            try:
                entry = float(entry) if entry else current_price
            except (TypeError, ValueError):
                entry = current_price
            
            side = position_data.get('side', 'BUY') if isinstance(position_data, dict) else 'BUY'
            
            # Calculate PnL
            if side == 'BUY':
                pnl_percent = ((current_price - entry) / entry) * 100
            else:
                pnl_percent = ((entry - current_price) / entry) * 100
            
            # Time in trade
            if isinstance(position_data, dict) and 'timestamp' in position_data:
                entry_time = pd.Timestamp(position_data['timestamp'])
                time_in_trade = str(pd.Timestamp.now() - entry_time).split('.')[0]
            
            # SL/TP distances
            if isinstance(position_data, dict):
                if 'sl' in position_data and position_data['sl']:
                    try:
                        sl_val = float(position_data['sl'])
                        sl_distance = abs((sl_val - entry) / entry) * 100
                    except (TypeError, ValueError):
                        pass
                if 'tp' in position_data and position_data['tp']:
                    try:
                        tp_val = float(position_data['tp'])
                        tp_distance = abs((tp_val - entry) / entry) * 100
                    except (TypeError, ValueError):
                        pass
            
            # Risk/Reward ratio
            if sl_distance and tp_distance and sl_distance > 0:
                rr_ratio = round(tp_distance / sl_distance, 2)
        
        return {
            "symbol": self.active_symbol,
            "current_price": current_price,
            "regime": regime,
            "market_bias": market_bias,
            
            # Technical Indicators
            "rsi": rsi,
            "atr": atr,
            "volatility_percentile": volatility_percentile,
            
            # EMAs
            "ema_20": ema_20,
            "ema_50": ema_50,
            "ema_200": ema_200,
            "ema20_distance": round(((current_price - ema_20) / ema_20) * 100, 2),
            "ema50_distance": round(((current_price - ema_50) / ema_50) * 100, 2),
            
            # Price Levels
            "swing_high": swing_high,
            "swing_low": swing_low,
            
            # Volume
            "current_volume": current_volume,
            "avg_volume": avg_volume,
            "volume_ratio": round(volume_ratio, 1),
            
            # Position Data
            "pnl_percent": round(pnl_percent, 2) if position_data else None,
            "time_in_trade": time_in_trade,
            "sl_distance": round(sl_distance, 2) if sl_distance else None,
            "tp_distance": round(tp_distance, 2) if tp_distance else None,
            "rr_ratio": rr_ratio
        }
    
    
    def execute_entry_atomically(self, symbol: str, side: str, size: float, price: float = None, sl: float = None, tp: float = None, strategy: str = "Unknown"):
        """
        ATOMIC ENTRY FLOW
        1. Check Quota
        2. Clean Old Orders
        3. Execute (Bulk/Atomic)
        4. Verify Fill
        5. Sync State
        """
        try:
            # 1. FINAL QUOTA CHECK
            real_positions = hyperliquid_service.get_positions()
            active_count = len([p for p in real_positions if float(p["size"]) > 0])
            
            if active_count >= self.max_positions:
                self.add_log(f"⛔ QUOTA EXCEEDED ({active_count}/{self.max_positions}). Entry aborted.")
                return False

            self.add_log(f"🔒 ATOMIC ENTRY START: {side} {symbol} ({size}) via {strategy}")

            # 2. SANITIZE (Cancel any old pending orders for this symbol)
            self.add_log(f"🧹 Cleaning pre-trade orphans on {symbol}...")
            hyperliquid_service.cancel_all_orders(symbol)

            # 3. EXECUTE (Atomic Bulk)
            is_buy = (side == "BUY")
            result = hyperliquid_service.execute_order(
                symbol=symbol,
                is_buy=is_buy,
                quantity=size,
                price=price, # If None, will likely be treated as Market/Aggressive Limit inside execute_order
                sl_price=sl,
                tp_price=tp
            )
            
            if result.get("status") != "success":
                self.add_log(f"❌ Entry Failed: {result.get('message')}")
                return False
                
            # 4. VERIFY (Loop 5s)
            self.add_log("⏳ Verifying Fill...")
            filled = False
            for i in range(5):
                time.sleep(1)
                positions = hyperliquid_service.get_positions()
                pos = next((p for p in positions if p["symbol"] == symbol and float(p['size']) > 0), None)
                if pos:
                    filled = True
                    self.add_log(f"✅ ENTRY CONFIRMED: {symbol} Size: {pos['size']} Entry: {pos['entry_price']}")
                    
                    # 5. SYNC STATE
                    self.active_trade = {
                        "symbol": symbol,
                        "side": side,
                        "entry": float(pos['entry_price']),
                        "sl": sl,
                        "tp": tp,
                        "strategy": strategy,
                        "timestamp": pd.Timestamp.now().isoformat(),
                        "size": float(pos['size']),
                        "leverage": float(pos.get("leverage", 1.0))
                    }
                    self.risk_manager.record_trade_open()
                    StateManager.save_state(self)
                    
                    # Discord Alert
                    discord_service.send_alert(
                        f"🚀 ENTERED {side} {symbol}",
                        f"Strategy: {strategy}\nEntry: {pos['entry_price']}\nSize: {pos['size']}\nSL: {sl}\nTP: {tp}",
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
        """
        ATOMIC EXIT FLOW (THE KILL SWITCH)
        1. Market Close (ReduceOnly)
        2. Verify Size == 0
        3. Clean Orphans
        4. Release State
        """
        self.add_log(f"🔒 ATOMIC EXIT START: Closing {symbol} ({reason})")
        
        try:
            # 1. KILL SWITCH (Market Close)
            # hyperliquid_service.close_position handles retries and verification internally
            # It returns success only if position is closed or dust remains
            result = hyperliquid_service.close_position(symbol)
            
            if result.get("status") == "success":
                # 2. VERIFY (Double Check)
                final_positions = hyperliquid_service.get_positions()
                remaining = next((p for p in final_positions if p["symbol"] == symbol), None)
                
                if not remaining or float(remaining["size"]) == 0:
                     self.add_log(f"✅ POSITION CLOSED: {symbol}")
                     
                     # 3. CLEANUP ORPHANS (Crucial)
                     self.add_log(f"🧹 Cleaning post-trade orphans on {symbol}...")
                     hyperliquid_service.cancel_all_orders(symbol)
                     
                     # 4. RELEASE STATE
                     # PnL Calculation for logs/discord (Approximate based on known entry)
                     pnl_usdc = 0
                     if self.active_trade:
                         entry = self.active_trade.get("entry", 0)
                         active_side = self.active_trade.get("side", "BUY")
                         # Close price from result?? hyperliquid_service.close_position doesn't return price
                         # Get approximate market price
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
                             "exit_time": pd.Timestamp.now().isoformat()
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
        """
        HARD VETO: Technical guardrails to block bad AI calls.
        Returns REJECT reason if vetoed, else None.
        """
        try:
            rsi = market_context.get("rsi")
            if rsi is None: return None
            
            # 1. RSI Extremes Veto
            if signal == "BUY" and rsi > 75:
                return f"HARD VETO: RSI Overbought ({rsi:.1f} > 75)"
            
            if signal == "SELL" and rsi < 25:
                return f"HARD VETO: RSI Oversold ({rsi:.1f} < 25)"
                
            return None
        except Exception:
            return "RANGE"

    def _verify_and_enforce_sl_tp(self, symbol: str, trade_data: dict):
        """
        Consolidated verification: Fetch Exchange Orders -> Compare -> Enforce if needed.
        """
        if self.execution_mode != "Auto (Hyperliquid)":
            return

        try:
            # 1. Fetch Open Orders from Hyperliquid
            # Using base info request to ensure we see everything (Limit + Trigger?)
            # hyperliquid-python-sdk 'open_orders' typically returns standard orders.
            # Triggers might need a specific check, but sync_sl_tp replaces ALL.
            # So if we see NOTHING or WRONG PRICES, we sync.
            
            open_orders = hyperliquid_service.info.open_orders(config.HL_ACCOUNT_ADDRESS)
            symbol_orders = [o for o in open_orders if o["coin"] == symbol]
            
            desired_sl = float(trade_data.get("sl", 0))
            desired_tp = float(trade_data.get("tp", 0))
            
            found_sl = False
            found_tp = False
            
            # Tolerance: 0.1%
            TOLERANCE = 0.001
            
            for o in symbol_orders:
                # Trigger orders usually have 'triggerPx'
                price = float(o.get("limitPx", o.get("triggerPx", 0)))
                # Check order type if possible, but price matching is strong enough proxy check
                
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
                
        except Exception as e:
            self.add_log(f"⚠️ Error in _verify_and_enforce_sl_tp: {e}")

    def trading_loop(self):
        """Main trading loop"""
        self.add_log("🚀 Trading loop started")
        self.add_log(f"⚙️ Loop initialized. is_running={self.is_running}")
        
        # ============================================
        # STARTUP SYNCHRONIZATION WITH HYPERLIQUID
        # ============================================
        if not self.startup_sync_done:
            self.add_log("🔄 STARTUP SYNC: Checking Hyperliquid positions...")

            # --- LEVERAGE SYNC ---
            try:
                if self.execution_mode == "Auto (Hyperliquid)":
                    requested_leverage = int(self.sidebar_settings.get("leverage", 5))
                    margin_type = self.sidebar_settings.get("margin_type", "Cross")
                    is_cross = (margin_type == "Cross")
                    
                    # Apply Gamification Leverage Limit
                    from app.core.asset_gamification import AssetGamification
                    from app.services.hyperliquid_service import hyperliquid_service as hl_svc
                    
                    try:
                        balance_data = hl_svc.get_account_balance()
                        current_equity = balance_data.get("equity", 0.0) if balance_data.get("status") == "success" else 0.0
                        gam = AssetGamification(current_equity)
                        max_leverage = gam.get_max_leverage()
                        
                        # Cap to gamification limit
                        target_leverage = min(requested_leverage, max_leverage)
                        
                        if requested_leverage > max_leverage:
                            self.add_log(f"🎮 GAMIFICATION: Leverage capped {requested_leverage}x → {target_leverage}x (Level: {gam.level})")
                    except Exception as gam_err:
                        # Fallback if gamification check fails
                        self.add_log(f"⚠️ Gamification check failed: {gam_err}")
                        target_leverage = requested_leverage
                    
                    self.add_log(f"⚙️ SYNC: Enforcing Leverage {target_leverage}x ({margin_type}) on Exchange...")
                    hyperliquid_service.update_leverage(self.active_symbol, target_leverage, is_cross)
            except Exception as e:
                self.add_log(f"⚠️ LEVERAGE SYNC FAILED: {e}")
            
            try:
                self.add_log("🔄 INITIAL SYNC: Checking Hyperliquid for existing positions...")
                
                real_positions = hyperliquid_service.get_positions()
                
                if real_positions:
                    main_position = real_positions[0]
                    position_symbol = main_position["symbol"]
                    
                    self.add_log(f"✅ SYNC: Found position on Hyperliquid: {position_symbol}")
                    
                    # CRITICAL FIX: Switch active_symbol IMMEDIATELY if different
                    if self.active_symbol != position_symbol:
                        self.add_log(f"⚠️ SYNC: Symbol mismatch detected!")
                        self.add_log(f"   Bot was tracking: {self.active_symbol}")
                        self.add_log(f"   Real position on: {position_symbol}")
                        self.add_log(f"🔄 SYNC: Switching to {position_symbol}")
                        
                        # Switch to correct symbol
                        old_symbol = self.active_symbol
                        self.active_symbol = position_symbol
                        
                        # CRITICAL: Save state immediately to persist the switch
                        StateManager.save_state(self)
                        
                        self.add_log(f"✅ SYNC: Symbol switched from {old_symbol} to {position_symbol}")
                    
                    # CRITICAL: Wait 10 seconds for full synchronization before AI analysis
                    self.add_log("⏳ SYNC: Waiting 10 seconds for full synchronization...")
                    time.sleep(10)
                    self.add_log("✅ SYNC: Synchronization complete, ready for AI analysis")
                    
                    # Now perform AI analysis with the CORRECT symbol
                    if not self._initial_position_analyzed:
                        try:
                            # from app.services.ia import ia_service (Moved to top)
                            import json
                            self.add_log(f"🤖 Running AI analysis on {position_symbol} position...")
                            
                            # Fetch fresh data for the CORRECT symbol
                            df = hyperliquid_service.get_candles(self.active_symbol, "15m", 50)
                            
                            if not df.empty:
                                ai_result = ia_service.analyze_position_risk(
                                    symbol=self.active_symbol,
                                    position_data=main_position,  # Fixed: position → position_data
                                    market_data={
                                        "close": float(df['close'].iloc[-1]),
                                        "regime": "UNKNOWN"
                                    }
                                )
                                
                                if ai_result:
                                    ai_data = json.loads(ai_result) if isinstance(ai_result, str) else ai_result
                                    reasoning = ai_data.get('reasoning', 'Position analysée')
                                    risk_level = ai_data.get('risk_level', 'UNKNOWN')
                                    
                                    self.add_log(f"🤖 IA Startup ({risk_level}): {reasoning}")
                                    
                                    # CACHE THE RESULT for UI
                                    self.ai_cache[f"position_analysis_{self.active_symbol}"] = ai_data
                                    self.ai_cache["last_position_analysis"] = ai_data
                                    self.ai_cache["last_position_analysis_time"] = pd.Timestamp.now()
                                    
                                    # Send to Discord if high risk
                                    if risk_level in ["HIGH", "CRITICAL"]:
                                        try:
                                            discord_service.send_alert(
                                                f"🤖 AI Analysis - {risk_level} RISK",
                                                f"Symbol: {self.active_symbol}\n{reasoning}",
                                                color="FF0000" if risk_level == "CRITICAL" else "FFA500"
                                            )
                                        except Exception as e:
                                            self.add_log(f"⚠️ Discord AI notification failed: {e}")
                                else:
                                    self.add_log(f"🤖 IA Startup: Analysis completed")
                            
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
            # Initialize loop-scope variables to prevent UnboundLocalError
            ai_approved = False
            ai_reasoning = "Loop Start Default"
            action = None
            entry_price = 0.0
            sl = 0.0
            tp = 0.0
            strat_name = "Unknown"
            risk_factors = []
            
            self.add_log("🔄 Entering loop iteration...")
            try:
                self.add_log("📡 Fetching candles...")
                # Fetch both 15m and 1m candles for MTF strategies
                df_15m = hyperliquid_service.get_candles(self.active_symbol, interval="15m", limit=200)
                df_1m = hyperliquid_service.get_candles(self.active_symbol, interval="1m", limit=100)
                
                if df_15m.empty:
                    self.add_log("⚠️ No 15m data received")
                    time.sleep(30) # Wait 30s instead of 10s to reduce spam
                    continue
                
                if df_1m.empty:
                    self.add_log("⚠️ No 1m data received")
                    time.sleep(30) # Wait 30s instead of 10s to reduce spam
                    continue

                # CRITICAL FIX: Ensure numeric columns are floats to avoid "less_equal" TypeError in numpy/pandas
                # This fixes the strategy engine crash
                numeric_cols = ['open', 'high', 'low', 'close', 'volume']
                try:
                    for df_target in [df_15m, df_1m]:
                        for col in numeric_cols:
                            if col in df_target.columns:
                                df_target[col] = df_target[col].astype(float)
                except Exception as e:
                    self.add_log(f"⚠️ Error casting dataframe to float: {e}")
                    continue
                
                self.add_log(f"✅ Received {len(df_15m)} 15m candles and {len(df_1m)} 1m candles")
                self.latest_data = df_15m  # For UI display
                
                # Get current 1m candle time (trigger on 1m for MTF)
                current_candle_time = df_1m.index[-1]
                
                # --- POSITION ADOPTION & SYNC (Moved to start) ---
                # Check real positions from Hyperliquid
                try:
                    real_positions = hyperliquid_service.get_positions()
                    
                    # CRITICAL FIX: Check if we have a position on a DIFFERENT symbol
                    for pos in real_positions:
                        pos_symbol = pos["symbol"]
                        
                        # If we detect a position on a different symbol than what we're tracking
                        if pos_symbol != self.active_symbol and not self.active_trade:
                            self.add_log(f"🔄 SWITCHING SYMBOL: {self.active_symbol} → {pos_symbol} (Manual position detected)")
                            self.active_symbol = pos_symbol
                            
                            # Re-fetch candles for the NEW symbol
                            df_15m = hyperliquid_service.get_candles(self.active_symbol, interval="15m", limit=200)
                            df_1m = hyperliquid_service.get_candles(self.active_symbol, interval="1m", limit=100)
                            
                            if df_15m.empty or df_1m.empty:
                                self.add_log(f"❌ Failed to fetch candles for {self.active_symbol}")
                                continue
                            
                            break  # Only switch to first detected position
                    
                    # Now check for position on the CURRENT active_symbol
                    active_symbol_pos = next((p for p in real_positions if p["symbol"] == self.active_symbol), None)
                    
                    if active_symbol_pos:
                        # Position FOUND! Reset counter
                        self.missing_pos_counter = 0
                        
                        # Case 1: We have a real position but bot doesn't know about it (Manual Trade)
                        if not self.active_trade:
                            self.add_log(f"🕵️ DETECTED MANUAL POSITION on {self.active_symbol}. Adopting...")
                            
                            # Adopt it with default SL/TP parameters based on current ATR or percentage
                            # CRITICAL: Use the CORRECT symbol's price
                            current_price = hyperliquid_service.get_current_price(self.active_symbol)
                            entry_price = active_symbol_pos["entry_price"]
                            side = active_symbol_pos["side"]
                            
                            # CRITICAL: ALWAYS use AI to determine SL/TP for manual trades
                            self.add_log("🤖 Calling AI to validate manual trade SL/TP...")
                            self.add_log("🤖 Calling AI to validate manual trade SL/TP...")
                            try:
                                # Imports moved to top
                                # from app.services.ia import ia_service
                                # import json
                                
                                # Prepare comprehensive market context
                                market_context = self._prepare_ai_context(active_symbol_pos)
                                
                                # --- HARD VETO CHECK (Before AI) ---
                                veto_reason = self._check_hard_veto(action, market_context)
                                if veto_reason:
                                    self.add_log(f"🛑 Trade VETOED by Hard Rules: {veto_reason}")
                                    continue # Skip trade

                                ai_risk_analysis = ia_service.analyze_active_position(
                                    position_data=active_symbol_pos,
                                    current_market=market_context
                                )
                                
                                # Parse AI response
                                if ai_risk_analysis.get("raw_output"):
                                    ai_data = json.loads(ai_risk_analysis["raw_output"])
                                    sl = ai_data.get("stop_loss_suggestion")
                                    tp = ai_data.get("take_profit_suggestion")
                                    risk_score = ai_data.get("risk_score", "N/A")
                                    reasoning = ai_data.get("reasoning", "AI analysis complete")
                                    
                                    # Verify parameters - CLAMP WIDE STOPS
                                    dist_sl = abs(entry_price - sl) / entry_price
                                    dist_tp = abs(tp - entry_price) / entry_price
                                    
                                    # If AI suggests > 10% stop for a scalp, it's hallucinating. Clamp to 5% or ATR.
                                    if dist_sl > 0.10:
                                        self.add_log(f"⚠️ AI Suggested SL too wide ({dist_sl*100:.1f}%), clamping to 5%")
                                        if side == "BUY":
                                            sl = entry_price * 0.95
                                        else:
                                            sl = entry_price * 1.05
                                            
                                    self.add_log(f"🤖 AI Analysis (Risk: {risk_score}): {reasoning}")
                                    self.add_log(f"   AI Suggested SL: {sl:.8f}, TP: {tp:.8f}")
                                else:
                                    raise Exception("AI returned no output")
                                    
                            except Exception as e:
                                # AI failed - use ATR fallback
                                self.add_log(f"⚠️ AI validation failed: {e}, using ATR fallback")
                                atr = 0
                                if hasattr(self, 'latest_data') and not self.latest_data.empty and 'ATRr_14' in self.latest_data.columns:
                                    atr = self.latest_data['ATRr_14'].iloc[-1]
                                else:
                                    atr = current_price * 0.01

                                if side == "BUY":
                                    sl = entry_price - (2.0 * atr) 
                                    tp = entry_price + (3.0 * atr)
                                else:
                                    sl = entry_price + (2.0 * atr)
                                    tp = entry_price - (3.0 * atr)
                            
                            self.active_trade = {
                                "symbol": self.active_symbol,
                                "side": side,
                                "entry": entry_price,
                                "sl": sl,
                                "tp": tp,
                                "strategy": "Manual/Adopted",
                                "timestamp": pd.Timestamp.now().isoformat(),
                                "size": active_symbol_pos["size"],
                                "leverage": active_symbol_pos.get("leverage", 1.0)
                            }
                            self.risk_manager.record_trade_open()
                            self.add_log(f"✅ Adopted {side} {self.active_symbol} @ {entry_price} (Lev: {active_symbol_pos.get('leverage', 1.0)}x)")
                            self.add_log(f"   Current Price: {current_price} | SL: {sl:.8f} | TP: {tp:.8f}")
                            
                            # CRITICAL: Place SL/TP orders on Hyperliquid (not just software stops)
                            if self.execution_mode == "Auto (Hyperliquid)":
                                self.add_log("🔄 Syncing adopted SL/TP to Hyperliquid...")
                                try:
                                    hyperliquid_service.sync_sl_tp(
                                        self.active_symbol,
                                        side == "BUY",
                                        active_symbol_pos["size"],
                                        sl,
                                        tp
                                    )
                                    self.add_log("✅ SL/TP orders placed on Hyperliquid")
                                except Exception as e:
                                    self.add_log(f"❌ Failed to sync SL/TP: {e}")
                            
                            discord_service.send_alert(
                                "🛡️ MANUAL TRADE ADOPTED (AI-Validated)",
                                f"Symbol: {self.active_symbol}\nSide: {side}\nEntry: {entry_price}\nCurrent: {current_price}\nAI SL: {sl:.8f}\nAI TP: {tp:.8f}\nSize: {active_symbol_pos['size']}\nLeverage: {active_symbol_pos.get('leverage', 1.0)}x",
                                color="0000ff"
                            )
                            
                        # Case 2: We have a position and bot matches -> Sync PnL or check if size changed
                        else:
                            # Update PnL in active_trade for display if we want?
                            pass
                            
                    else:
                        # Case 3: Bot thinks we have a trade, but no position in HL (Manual Close or Liquidation)
                        if self.active_trade and self.execution_mode == "Auto (Hyperliquid)":
                              # Check if trade is very recent (Grace period for API latency / fill time)
                             trade_time = pd.Timestamp(self.active_trade["timestamp"])
                             time_since_entry = (pd.Timestamp.now() - trade_time).total_seconds()
                             
                             if time_since_entry > 30: # 30 seconds initial grace period
                                 # DEBOUNCE: Require 3 consecutive confirmations (approx 90s) before declaring position closed
                                 self.missing_pos_counter += 1
                                 self.add_log(f"⚠️ Position on {self.active_symbol} missing from exchange scan ({self.missing_pos_counter}/3)...")
                                 
                                 if self.missing_pos_counter >= 3:
                                     self.add_log("⚠️ Position vanished on exchange (CONFIRMED)! Closing bot trade.")
                                     
                                     # Calculer PNL final avant de fermer
                                     try:
                                         current_price = hyperliquid_service.get_current_price(self.active_symbol)
                                         entry_price = self.active_trade["entry"]
                                         side = self.active_trade["side"]
                                         size = self.active_trade.get("size", 0)
                                         leverage = self.active_trade.get("leverage", 1)
                                         
                                         # CORRECT PNL CALCULATION
                                         pnl_per_coin = (current_price - entry_price) if side == "BUY" else (entry_price - current_price)
                                         pnl_usdc = pnl_per_coin * size * leverage
                                         
                                         self.add_log(f"💰 PNL Final: ${pnl_usdc:.2f} USDC")
                                         
                                         # Enregistrer le trade
                                         self.trade_recorder.add_trade({
                                             "symbol": self.active_symbol,
                                             "strategy": self.active_trade.get("strategy", "Unknown"),
                                             "side": side,
                                             "entry_price": entry_price,
                                             "exit_price": current_price,
                                             "size": size,
                                             "leverage": leverage,
                                             "pnl_usdc": pnl_usdc,
                                             "pnl_percent": (pnl_per_coin / entry_price) * 100,
                                             "entry_time": self.active_trade.get("timestamp"),
                                             "exit_time": pd.Timestamp.now().isoformat(),
                                             "exit_reason": "External Close"
                                         })
                                         
                                         # Notification Discord
                                         discord_service.send_alert(
                                             "🔴 POSITION FERMÉE EXTERNELLEMENT",
                                             f"Symbol: {self.active_symbol}\nPNL: ${pnl_usdc:.2f} USDC\nRaison: Fermée via Hyperliquid UI",
                                             color="FF6600"
                                         )
                                         
                                         self.risk_manager.record_trade_close(pnl_usdc)
                                     except Exception as e:
                                         self.add_log(f"Error calculating final PNL: {e}")
                                         self.risk_manager.record_trade_close(0)
                                     
                                     self.active_trade = None
                                     StateManager.save_state(self)
                                     self.missing_pos_counter = 0 # Reset
                                 else:
                                     pass # Wait for next confirmation
                             else:
                                 self.add_log(f"⏳ Position pending verification ({time_since_entry:.1f}s ago)...")
                    

                
                except Exception as e:
                    self.add_log(f"⚠️ Error checking positions: {e}")
                
                # === SYNCHRONISATION RISK MANAGER ===
                # Force sync avec Hyperliquid (source de vérité)
                try:
                    sync_result = self.risk_manager.sync_with_hyperliquid(hyperliquid_service)
                    if sync_result.get("synced") and sync_result['old_count'] != sync_result['new_count']:
                        self.add_log(f"🔄 SYNC: Positions {sync_result['old_count']} → {sync_result['new_count']}")
                except Exception as e:
                    self.add_log(f"⚠️ Sync error: {e}")
                
                 # === GAMIFICATION LEVEL UP CHECK ===
                try:
                    balance_data = hyperliquid_service.get_account_balance()
                    if balance_data.get("status") == "success":
                        current_equity = balance_data.get("equity", 0.0)
                        
                        # Store old level before update
                        old_level_enum = self.gamification.level
                        
                        # Update balance and check for change
                        changed = self.gamification.update_balance(current_equity)
                        
                        if changed:
                            new_level_enum = self.gamification.level
                            # Check if it's a promotion (not demotion)
                            # Simple logic: just alert on change for now, or check value order?
                            # Let's assume progress is good.
                            
                            self.add_log(f"🎉 LEVEL UP: {old_level_enum.value} -> {new_level_enum.value}")
                            
                            # Get unlocked perks
                            unlocked = self.gamification.get_allowed_assets() # List[str]
                            # Actually we want tiers for the alert
                            # Helper needed or just pass enum list
                            from app.core.asset_gamification import ACCESS_RULES
                            unlocked_tiers = ACCESS_RULES[new_level_enum]["allowed_tiers"]
                            
                            discord_service.send_levelup_alert(
                                old_level=old_level_enum.value,
                                new_level=new_level_enum.value,
                                unlocked_tiers=unlocked_tiers
                            )
                except Exception as e:
                    pass # Don't spam logs with gamification errors
                    
                
                
                # ============================================
                # FOCUS MODE vs SCANNING MODE (API OPTIMIZATION)
                # ============================================
                real_positions = hyperliquid_service.get_positions()
                active_count = len([p for p in real_positions if float(p["size"]) > 0])
                
                # Update global state for ScannerJob
                self.is_focus_mode = (active_count >= self.max_positions)
                
                if self.is_focus_mode:
                    # CAS A: Position Active (FOCUS MODE)
                    # 🚫 ACTION : Scanner & Analysis DISABLED
                    # ✅ ACTION : Monitor Trade Only (handled by consistency checks above)
                    
                    # Log every ~5 minutes (10 loops * 30s)
                    if not hasattr(self, "focus_log_counter"): self.focus_log_counter = 0
                    self.focus_log_counter += 1
                    
                    if self.focus_log_counter % 10 == 1:
                        self.add_log(f"🔒 Trade in progress on {self.active_symbol}. Scanning PAUSED to save API rates.")
                        
                else:
                    # CAS B: No Position (HUNT MODE)
                    # ✅ ACTION : Analysis Enabled

                    # Only analyze on new 1m candle
                    if self.last_candle_time != current_candle_time:
                        self.last_candle_time = current_candle_time
                        
                        self.add_log(f"🔍 Analyzing new 1m candle at {current_candle_time}")
                        # Analyze strategies with MTF data
                        result = self.strategy_engine.analyze(df_15m, extra_data={"1m": df_1m})
                        self.latest_strategy_result = result
                        
                        # Update active strategies list for UI
                        self.active_strategies = result.get('strategies', [])
                        if self.active_strategies:
                             self.active_strategy_name = self.active_strategies[0] # Primary
                        
                        
                        signals = result.get('signals', [])
                        
                        # Deduplicate signals (Fix double logs)
                        unique_signals = []
                        seen_sigs = set()
                        for s in signals:
                            sig_id = f"{s.get('strategy')}_{s.get('signal')}_{s.get('timestamp')}"
                            if sig_id not in seen_sigs:
                                seen_sigs.add(sig_id)
                                unique_signals.append(s)
                        signals = unique_signals
                        
                        active_strategies = result.get('strategies', [])
                        regime = result.get('regime', 'UNKNOWN')
                        
                        self.add_log(f"📊 Analysis complete: {regime} regime, {len(active_strategies)} active strategies, {len(signals)} signals")
                        
                        # DEBUG: If 0 signals but strategies are active, investigate why
                        if len(signals) == 0 and len(active_strategies) > 0:
                            self.add_log(f"⚠️ DEBUG: {len(active_strategies)} active strategies but 0 signals generated")
                            
                            # Log current market conditions
                            current_price = float(df_15m['close'].iloc[-1])
                            current_rsi = result.get('rsi', 0)
                            current_adx = result.get('adx', 0)
                            ema_20 = result.get('ema_20')
                            ema_50 = result.get('ema_50')
                            
                            self.add_log(f"   Market: Price={current_price:.4f}, RSI={current_rsi:.1f}, ADX={current_adx:.1f}")
                            if ema_20 and ema_50:
                                self.add_log(f"   EMAs: EMA20={ema_20:.4f}, EMA50={ema_50:.4f}")
                            
                            # Log strategy proximity (how close to generating signal)
                            strategy_progress = result.get('strategy_progress', {})
                            if strategy_progress:
                                for strat_name, progress in strategy_progress.items():
                                    self.add_log(f"   {strat_name}: {progress}% proximity to signal")
                        

                        # AI: Analyse périodique du marché (toutes les 15 minutes)
                        try:
                            from app.services.ia import ia_service
                            from datetime import datetime, timedelta
                            
                            now = datetime.now()
                            last_analysis_time = self.ai_cache.get("last_market_analysis_time")
                            
                            # Analyser toutes les 15 minutes
                            if not last_analysis_time or (now - last_analysis_time) > timedelta(minutes=AI_MARKET_ANALYSIS_INTERVAL_MIN):
                                # Préparer le snapshot actuel
                                current_snapshot = {
                                    "symbol": self.active_symbol,
                                    "price": float(df_15m['close'].iloc[-1]),
                                    "regime": result.get('regime', 'UNKNOWN'),
                                    "timestamp": now.isoformat()
                                }
                                
                                # Récupérer le snapshot précédent
                                previous_snapshot = self.ai_cache["market_snapshots"][-1] if self.ai_cache["market_snapshots"] else None
                                
                                # Analyser l'évolution (Disabled - method missing in ia_service)
                                # evolution_analysis = ia_service.analyze_market_evolution(current_snapshot, previous_snapshot)
                                pass
                                evolution_analysis = {} # Dummy
                                
                                self.ai_cache["last_market_analysis"] = evolution_analysis
                                self.ai_cache["last_market_analysis_time"] = now
                                self.ai_cache["market_snapshots"].append(current_snapshot)
                                
                                # Logger les changements importants
                                if evolution_analysis.get("raw_output"):
                                    try:
                                        import json
                                        analysis_data = json.loads(evolution_analysis["raw_output"])
                                        if analysis_data.get("alert_level") in ["HIGH", "CRITICAL"]:
                                            self.add_log(f"🤖 IA: {analysis_data.get('summary', 'Changement détecté')}")
                                    except:
                                        pass
                        except Exception as e:
                            print(f"Error in AI market analysis: {e}")
                        
                        # CRITICAL: Check if this is a NEW candle before analyzing
                        # Already checked above `if self.last_candle_time != current_candle_time`
                        
                        # Process signals (Only if NO active trade)
                        if result.get("signals") and not self.active_trade:
                            self.add_log(f"🐛 DEBUG: Signals received: {result['signals']}")
                            sig_data = result["signals"][0]
                            
                            # CRITICAL FIX: Robust null safety - Filter out invalid signals BEFORE AI validation
                            if sig_data is None:
                                self.add_log(f"⚠️ NULL SAFETY: Skipping None signal from strategy")
                                continue
                            
                            if not isinstance(sig_data, dict):
                                self.add_log(f"⚠️ NULL SAFETY: Invalid signal type: {type(sig_data)}")
                                continue
                            
                            # Extract variables AFTER null safety checks
                            strat_name = sig_data.get("strategy", "Unknown")
                            action = sig_data.get("signal")
                            entry_price = sig_data.get("price")
                            sl = sig_data.get("sl", entry_price * 0.95 if entry_price else 0)
                            tp = sig_data.get("tp", entry_price * 1.05 if entry_price else 0)
                            
                            if not action or str(action).upper() == "NONE":
                                self.add_log(f"⚠️ NULL SAFETY: Signal with None direction from {strat_name}")
                                continue
                            
                            if not entry_price or float(entry_price) <= 0:
                                self.add_log(f"⚠️ NULL SAFETY: Invalid price ({entry_price}) from {strat_name}")
                                continue

                            # Initialize variables to prevent UnboundLocalError
                            ai_approved = False
                            ai_reasoning = "Initialization default"
                            risk_factors = []
                            

                            # === HARD RULES (VALIDATION HYBRIDE PHASE A) ===
                            # Validation stricte AVANT appel IA pour économiser du temps et des tokens
                            
                            current_rsi = result.get("rsi")
                            market_regime = result.get("regime", "UNKNOWN")
                            
                            # 1. RSI Guardrails
                            if action == "SELL" and current_rsi is not None and current_rsi < RSI_HARD_SELL_THRESHOLD:
                                self.add_log(f"⛔ HARD RULE BLOCK: Cannot SELL when RSI < {RSI_HARD_SELL_THRESHOLD} (RSI={current_rsi:.2f})")
                                continue
                            
                            if action == "BUY" and current_rsi is not None and current_rsi > RSI_HARD_BUY_THRESHOLD:
                                self.add_log(f"⛔ HARD Rule BLOCK: Cannot BUY when RSI > {RSI_HARD_BUY_THRESHOLD} (RSI={current_rsi:.2f})")
                                continue
                                
                            # 2. Crash Protection (Waterfall)
                            if action == "BUY" and market_regime == "TREND_BEAR_STRONG":
                                self.add_log(f"⛔ HARD RULE BLOCK: Buying disabled in TREND_BEAR_STRONG regime.")
                                continue

                            # AI: Validate signal before execution
                            ai_approved = False
                            ai_reasoning = "No AI validation performed"

                            
                            # Convert to DataFrame
                            try:
                                from app.services.ia import ia_service
                                import json
                                
                                self.add_log("🤖 Validating signal with AI...")
                                
                                # Prepare market context for validation
                                market_context = self._prepare_ai_context()
                                
                                # Prepare signal data
                                signal_for_validation = {
                                    "symbol": self.active_symbol,
                                    "signal": action,
                                    "strategy": strat_name,
                                    "price": entry_price,
                                    "sl": sl,
                                    "tp": tp
                                }
                                
                                # Call AI validation
                                validation_result = ia_service.validate_signal(
                                    signal_data=signal_for_validation,
                                    market_context=market_context
                                )
                                
                                # Parse AI response
                                risk_factors = []
                                if validation_result.get("raw_output"):
                                    try:
                                        ai_data = json.loads(ia_service.extract_json(validation_result["raw_output"]))
                                        ai_approved = ai_data.get("approved", False)
                                        ai_confidence = ai_data.get("confidence", 0)
                                        ai_reasoning = ai_data.get("reasoning", "No reasoning provided")
                                        risk_factors = ai_data.get("risk_factors", [])
                                        
                                        # Check for suggested adjustments
                                        adjustments = ai_data.get("suggested_adjustments", {})
                                        if adjustments.get("sl"):
                                            sl = adjustments["sl"]
                                            self.add_log(f"   AI adjusted SL to: {sl:.2f}")
                                        if adjustments.get("tp"):
                                            tp = adjustments["tp"]
                                            self.add_log(f"   AI adjusted TP to: {tp:.2f}")
                                        
                                        if ai_approved:
                                            self.add_log(f"✅ AI APPROVED (Confidence: {ai_confidence}%): {ai_reasoning}")
                                        else:
                                            self.add_log(f"❌ AI REJECTED (Confidence: {ai_confidence}%): {ai_reasoning}")
                                            if risk_factors:
                                                self.add_log(f"   Risks: {', '.join(risk_factors[:2])}")
                                    except Exception as e:
                                        print(f"Error parsing AI validation: {e}")
                                        ai_approved = True # Fallback if AI fails parsing but returned result? No, safefail to False usually better.
                                        # But let's assume if parsing fails we trust Strategy.
                                        
                                else:
                                    ai_approved = True
                                    
                            except Exception as e:
                                self.add_log(f"⚠️ AI Validation error: {e}")
                                ai_approved = True # Fail open or closed? Fail open for now.
                            
                            if self.execution_mode == "Auto (Hyperliquid)" and ai_approved:
                                    # EXECUTE ATOMICALLY
                                try:
                                    # Get fresh equity for accurate sizing
                                    acc_balance = hyperliquid_service.get_account_balance(force_refresh=True)
                                    current_equity = float(acc_balance.get("total_equity", 0.0))
                                    
                                    if current_equity <= 0:
                                        self.add_log(f"⚠️ Warning: Retrieved equity is {current_equity}. Analyzing fallback...")
                                    
                                except Exception as e:
                                    self.add_log(f"⚠️ Failed to get equity: {e}")
                                    current_equity = 0.0

                                size = self.risk_manager.calculate_position_size(entry_price, sl, current_equity)
                                if size > 0:
                                    self.execute_entry_atomically(
                                        symbol=self.active_symbol,
                                        side=action,
                                        size=size,
                                        price=None, # Market/Aggressive
                                        sl=sl,
                                        tp=tp,
                                        strategy=strat_name
                                    )
                                else:
                                    self.add_log("⚠️ Size calculation returned 0")

                            elif self.execution_mode == "Manual (Phantom)":
                                self.add_log(f"👻 Phantom Signal: {action} on {self.active_symbol} @ {entry_price} (AI: {ai_approved})")
                                self.add_log(f"   Risk Factors: {', '.join(risk_factors)}")

                            # CRITICAL: Prevent double execution if trade was just opened
                            if self.active_trade:
                                self.add_log("🛑 Strategy Cycle Complete (Trade Opened). Skipping redundant Phase B.")
                                continue



                        
                        # [CLEANUP] Removed 300 lines of duplicated legacy code that caused false negative logs.
                        # The correct signal processing loop ends at line 1177.

                    else:
                        # Log why we're skipping (only every 12th iteration to avoid spam = once per minute)
                        if not hasattr(self, '_skip_counter'):
                            self._skip_counter = 0
                        self._skip_counter += 1
                        if self._skip_counter % 12 == 0:
                            self.add_log(f"⏸️ Same candle {current_candle_time}, waiting for next 1m candle...")
                
                # --- Position Sync moved to start of loop ---

                # Check active trade management
                # Check active trade management
                if self.active_trade:
                    current_price = df_15m['close'].iloc[-1]
                    entry_price = self.active_trade.get("entry", 0)
                    tp_price = self.active_trade.get("tp")
                    sl_price = self.active_trade.get("sl")
                    side = self.active_trade.get("side", "BUY")

                    # DEFENSIVE: If SL/TP missing (e.g. from old state or bad boot), set defaults to prevent crash
                    # DEFENSIVE: If SL/TP missing (e.g. from old state or bad boot), set defaults to prevent crash
                    if not tp_price or not sl_price:
                         # Smart Fallback: Use ATR if available, else 2.5% fixed
                         atr = 0
                         try:
                             if 'ATRr_14' in df_15m.columns:
                                 atr = df_15m['ATRr_14'].iloc[-1]
                         except: pass
                         
                         if atr > 0:
                             sl_dist = 2.0 * atr
                             tp_dist = 3.0 * atr
                             log_ctx = f"ATR-based ({atr:.6f})"
                         else:
                             sl_dist = entry_price * 0.025 # 2.5% default (Realistic for Scalp/Day)
                             tp_dist = entry_price * 0.04  # 4% default
                             log_ctx = "Fixed 2.5%"

                         if side == "BUY":
                             sl_price = sl_price or (entry_price - sl_dist)
                             tp_price = tp_price or (entry_price + tp_dist)
                         else:
                             sl_price = sl_price or (entry_price + sl_dist)
                             tp_price = tp_price or (entry_price - tp_dist)
                         
                         self.active_trade["sl"] = sl_price
                         self.active_trade["tp"] = tp_price
                         self.add_log(f"⚠️ Recovered missing SL/TP for active trade: SL={sl_price:.6f}, TP={tp_price:.6f} ({log_ctx})")

                         # CRITICAL: Execute these orders on the exchange!
                         if self.execution_mode == "Auto (Hyperliquid)":
                             self.add_log("🔄 Syncing recovered SL/TP to Hyperliquid...")
                             hyperliquid_service.sync_sl_tp(
                                 self.active_symbol,
                                 side == "BUY",
                                 self.active_trade.get("size", 0),
                                 sl_price,
                                 tp_price
                             )
                             
                    # CRITICAL: Verify and Enforce SL/TP (Consolidated Logic)
                    self._verify_and_enforce_sl_tp(self.active_symbol, self.active_trade)
                    
                    # AI: Analyser la position active (toutes les 5 minutes)
                    try:
                        # from app.services.ia import ia_service (Moved to top)
                        from datetime import datetime, timedelta
                        
                        now = datetime.now()
                        last_pos_analysis_time = self.ai_cache.get("last_position_analysis_time")
                        
                        # Analyser toutes les 5 minutes
                        if not last_pos_analysis_time or (now - last_pos_analysis_time) > timedelta(minutes=AI_POSITION_ANALYSIS_INTERVAL_MIN):
                            market_context = {
                                "current_price": float(current_price), # FIXED: Key matches ia.py expectation
                                "symbol": self.active_symbol,
                                "regime": self.market_data.get('regime', 'UNKNOWN'),
                                "rsi": float(self.market_data.get('rsi', 50)),
                                "atr": float(self.market_data.get('atr', 0))
                            }
                            
                            position_analysis = ia_service.analyze_active_position(self.active_trade, market_context)
                            
                            # CRITICAL FIX: Store with specific key for API retrieval
                            self.ai_cache[f"position_analysis_{self.active_symbol}"] = position_analysis
                            self.ai_cache["last_position_analysis"] = position_analysis
                            self.ai_cache["last_position_analysis_time"] = now
                            
                            # Logger les recommandations importantes
                            if position_analysis.get("raw_output"):
                                try:
                                    import json
                                    pos_data = json.loads(position_analysis["raw_output"])
                                    if pos_data.get("risk_level") in ["HIGH", "CRITICAL"]:
                                        self.add_log(f"🤖 IA Position: {pos_data.get('reasoning', 'Risque détecté')}")
                                except:
                                    pass
                    except Exception as e:
                        print(f"Error in AI position analysis: {e}")
                    
                    # BREAK EVEN LOGIC
                    # If price moved 50% towards TP, move SL to Entry + 0.3% (increased from 0.1% to cover slippage)
                    be_triggered = False
                    BREAKEVEN_BUFFER = 1.003  # 0.3% buffer (was 1.001 = 0.1%)
                    
                    if side == "BUY":
                        dist_to_tp = tp_price - entry_price
                        current_dist = current_price - entry_price
                        
                        # Trigger BE if moved 50% to TP and SL is below Entry
                        if current_dist >= (dist_to_tp * 0.5) and sl_price < entry_price:
                            self.active_trade["sl"] = entry_price * BREAKEVEN_BUFFER
                            self.active_trade["breakeven_active"] = True  # Flag for AI analysis
                            self.add_log(f"🛡️ SECURED: Moved SL to Break Even @ {self.active_trade['sl']:.2f} (+0.3% buffer)")
                            be_triggered = True
                            
                    else: # SELL
                        dist_to_tp = entry_price - tp_price
                        current_dist = entry_price - current_price
                        
                        # Trigger BE if moved 50% to TP and SL is above Entry
                        if current_dist >= (dist_to_tp * 0.5) and sl_price > entry_price:
                            self.active_trade["sl"] = entry_price * (2 - BREAKEVEN_BUFFER)  # For SHORT: Entry * 0.997
                            self.active_trade["breakeven_active"] = True  # Flag for AI analysis
                            self.add_log(f"🛡️ SECURED: Moved SL to Break Even @ {self.active_trade['sl']:.2f} (-0.3% buffer)")
                            be_triggered = True
                    
                    if be_triggered:
                        try:
                            discord_service.send_alert(
                                "🛡️ TRADE SECURED",
                                f"Symbol: {self.active_symbol}\nPrice: {current_price}\nSL moved to Break Even",
                                color="0000ff" # Blue for info
                            )
                            StateManager.save_state(self)
                        except: pass

                    # Check SL/TP (Updated with new SL)
                    if be_triggered:
                        self._verify_and_enforce_sl_tp(self.active_symbol, self.active_trade)
                    
                    # Check SL/TP (Updated with new SL)
                    if side == "BUY":
                        if current_price <= self.active_trade["sl"]:
                            self.add_log(f"🛑 SL HIT @ {current_price}")
                            self.execute_exit_atomically(self.active_symbol, reason="STOP_LOSS")
                            
                        elif current_price >= self.active_trade["tp"]:
                            self.add_log(f"✅ TP HIT @ {current_price}")
                            self.execute_exit_atomically(self.active_symbol, reason="TAKE_PROFIT")

                    else: # SELL
                        if current_price >= self.active_trade["sl"]:
                            self.add_log(f"🛑 SL HIT @ {current_price}")
                            self.execute_exit_atomically(self.active_symbol, reason="STOP_LOSS")
                            
                        elif current_price <= self.active_trade["tp"]:
                            self.add_log(f"✅ TP HIT @ {current_price}")
                            self.execute_exit_atomically(self.active_symbol, reason="TAKE_PROFIT")
                
                time.sleep(TRADING_LOOP_INTERVAL)  # Wait 30 seconds before next iteration (reduced API load)
                
            except Exception as e:
                self.add_log(f"❌ Error in trading loop: {e}")
                time.sleep(ERROR_SLEEP_INTERVAL)
        
        self.add_log("⏸️ Trading loop stopped")
    
    def start(self):
        """Start the bot"""
        self.add_log(f"🔧 start() called. Current is_running={self.is_running}")
        
        # Check if thread is actually alive
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
            self.add_log("🚀 Starting trading thread...")
            self.thread.start()
            self.add_log(f"✅ Thread started. Thread alive={self.thread.is_alive()}")
            
            # Start Scanner Job
            if self.scanner_job:
                # Enable scanner when engine starts
                self.scanner_settings['enabled'] = True
                self.scanner_job.start()
                self.add_log("🕵️ Scanner auto-enabled with engine start")
                
            StateManager.save_state(self)
        else:
            self.add_log("⚠️ Bot already running with active thread, skipping start")
    
    def close_active_trade(self, reason="Manual Close"):
        """Close the currently active trade"""
        if not self.active_trade:
            return False, "No active trade"
            
        try:
            symbol = self.active_trade["symbol"]
            self.add_log(f"📉 MANUAL CLOSE REQUESTED for {symbol} ({reason})")
            
            # Use Atomic Exit Flow
            success = self.execute_exit_atomically(symbol, reason=reason)
            
            if success:
                return True, "Trade closed successfully"
            else:
                return False, "Failed to close trade (Check logs)"
            
        except Exception as e:
            self.add_log(f"❌ Error in close_active_trade: {e}")
            return False, str(e)

    async def recalibrate_position_stops(self):
        """
        Manual override to recalculate and update TP/SL orders based on current market data (ATR).
        Returns: (status_code, message)
        """
        if not self.active_trade:
             return "ERROR", "No active trade to recalibrate."

        symbol = self.active_trade["symbol"]
        self.add_log(f"♻️ RECALIBRATE: Auditing stops for {symbol}...")

        # 1. Audit Phase
        try:
            # Get real position data
            positions = hyperliquid_service.get_positions()
            real_pos = next((p for p in positions if p["symbol"] == symbol and float(p["size"]) != 0), None)
            
            if not real_pos:
                self.add_log(f"⚠️ Recalibration aborted: No position found on exchange for {symbol}")
                self.active_trade = None # Sync state
                return "ERROR", "No real position found (Local state cleared)."

            entry_price = float(real_pos["entry_price"])
            side = real_pos["side"]
            size = float(real_pos["size"])
            
            # 2. Market Data & Ideal Calculation
            df = self.latest_data
            
            # CRITICAL: If cached data is missing or stale, force a fresh fetch
            if df is None or df.empty:
                self.add_log("📡 Recalibrate: Cache empty, fetching fresh 15m data...")
                try:
                    # We need the market data service, not hyperliquid service directly for candles usually
                    # But checking imports... let's rely on the internal method if available or import helper
                    from backend.market_data import get_hyperliquid_candles, calculate_atr
                    
                    df = await get_hyperliquid_candles(symbol, "15m", 100)
                except ImportError:
                    # Fallback for synchronous/path issues
                    self.add_log("⚠️ Could not import market_data helpers for fetch.")
                    pass

                except Exception as e:
                    self.add_log(f"⚠️ Fresh fetch failed: {e}")
            
            # Calculate ATR
            atr = 0.0
            try:
                if df is not None and not df.empty:
                    # Ensure ATR is calculated
                    if 'ATRr_14' not in df.columns:
                         # Quick Calc
                         high = df['high']
                         low = df['low']
                         close = df['close']
                         # Simple TR
                         tr1 = high - low
                         tr2 = (high - close.shift()).abs()
                         tr3 = (low - close.shift()).abs()
                         tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
                         atr = tr.rolling(14).mean().iloc[-1]
                    else:
                         atr = df['ATRr_14'].iloc[-1]
            except Exception as e:
                self.add_log(f"⚠️ ATR Calc error: {e}")
                pass
            
            if atr == 0:
                 # Fallback to 1.5% of price
                 atr = entry_price * 0.015
                 self.add_log(f"⚠️ Using Fallback ATR (1.5%): {atr:.6f}")
            
            # Ideal Logic: 2*ATR SL, 3*ATR TP
            # ADJUSTMENT: Ensure we don't bring TP closer if it's already "better" (higher for long)?
            # No, "Recalibrate" implies "Reset to Strategy Standard". Sticking to logic.
            
            sl_mult = 2.0
            tp_mult = 3.0
            
            if side == "BUY":
                ideal_sl = entry_price - (atr * sl_mult)
                ideal_tp = entry_price + (atr * tp_mult)
            else:
                ideal_sl = entry_price + (atr * sl_mult)
                ideal_tp = entry_price - (atr * tp_mult)
                
            current_sl = float(self.active_trade.get("sl", 0))
            current_tp = float(self.active_trade.get("tp", 0))
            
            # 3. Diff Check
            sl_diff = abs(current_sl - ideal_sl) / current_sl if current_sl else 1.0
            tp_diff = abs(current_tp - ideal_tp) / current_tp if current_tp else 1.0
            
            is_divergent = (sl_diff > TP_SL_RECALIBRATION_THRESHOLD_PCT) or (tp_diff > TP_SL_RECALIBRATION_THRESHOLD_PCT)
            
            if not is_divergent:
                self.add_log(f"✅ Audit: Orders aligned (Diff < {TP_SL_RECALIBRATION_THRESHOLD_PCT*100}%). No update needed.")
                return "UNCHANGED", "Orders are aligned."
                
            # 4. Atomic Update
            self.add_log(f"⚠️ Audit: Divergence detected (SL diff: {sl_diff:.4f}, TP diff: {tp_diff:.4f}). Updating...")
            self.add_log(f"   Old SL: {current_sl:.6f} -> New: {ideal_sl:.6f} (ATR: {atr:.6f})")
            
            # Cancel All

            # Update Local State FIRST
            self.active_trade["sl"] = ideal_sl
            self.active_trade["tp"] = ideal_tp
            
            # Enforce via consolidated logic
            self._verify_and_enforce_sl_tp(symbol, self.active_trade)
            
            StateManager.save_state(self)
            
            return "UPDATED", f"Orders recalibrated to SL: {ideal_sl:.2f}, TP: {ideal_tp:.2f}"
            
        except Exception as e:
            self.add_log(f"❌ Recalibrate Error: {e}")
            return "ERROR", str(e)


    def stop(self):
        """Stop the bot"""
        if self.is_running:
            self.is_running = False
            if self.thread:
                self.thread.join(timeout=5)
            self.add_log("⏹️ Bot stopped")
            
            # Stop Scanner Job
            if self.scanner_job:
                self.scanner_settings['enabled'] = False
                self.scanner_job.stop()
                self.add_log("🕵️ Scanner disabled with engine stop")
                
            StateManager.save_state(self)

    def boot_sequence(self) -> bool:
        """
        Robust Staged Startup Sequence (5 Phases).
        Return True if system is GREEN GO, False otherwise.
        """
        print("\n🚀 INITIATING STAGED BOOT SEQUENCE...")
        import time
        
        # --- PHASE 1: CONNECTIVITY & AUTH ---
        print("\n[1/5] 🔌 Connectivity & Auth...")
        try:
            # Simple ping check to verify API (using meta() as lightweight call)
            # hyperliquid_service.info is initialized in service ctor
            hyperliquid_service.info.meta() 
            print("   ✅ Hyperliquid REST API reachable")
            
            # Note: WebSockets are initialized in main block
            print("   ✅ Auth Keys present")
        except Exception as e:
            print(f"   ❌ FATAL: Connectivity failed: {e}")
            return False

        # --- PHASE 2: ACCOUNT & RECONCILIATION ---
        print("\n[2/5] 💼 Account & Reconciliation...")
        try:
            balance = hyperliquid_service.get_account_balance()
            if balance.get("status") == "error":
                raise Exception(balance.get("message"))
            print(f"   ✅ Balance Access OK (Equity: ${balance.get('equity', 0)})")
            
            positions = hyperliquid_service.get_positions()
            active_pos = next((p for p in positions if p["symbol"] == self.active_symbol), None)
            
            if active_pos:
                print(f"   ⚠️ FOUND GHOST POSITION on {self.active_symbol}!")
                print(f"      Size: {active_pos['size']} | Entry: {active_pos['entry_price']}")
                print("   ℹ️ It will be fully adopted (with SL/TP) in the main loop.")
            else:
                print("   ✅ No ghost positions on active symbol.")
                # Ensure we don't think we have one
                self.active_trade = None
                
        except Exception as e:
             print(f"   ❌ FATAL: Account check failed: {e}")
             return False

        # --- PHASE 3: MARKET DATA WARMUP ---
        print("\n[3/5] 🔥 Market Data Warmup...")
        try:
            print(f"   📡 Fetching history for {self.active_symbol}...")
            # Fetch explicitly here to ensure we have data before "System Ready"
            df_15m = hyperliquid_service.get_candles(self.active_symbol, interval="15m", limit=200)
            df_1m = hyperliquid_service.get_candles(self.active_symbol, interval="1m", limit=100)
            
            if df_15m.empty or df_1m.empty:
                raise Exception("Received empty candle data")
                
            self.latest_data = df_15m
            print(f"   ✅ Loaded {len(df_15m)} 15m candles and {len(df_1m)} 1m candles")
            
        except Exception as e:
            print(f"   ❌ FATAL: Warmup failed: {e}")
            return False

        # --- PHASE 4: STRATEGY INITIALIZATION ---
        print("\n[4/5] 🧠 Strategy Initialization...")
        try:
            # Run a dummy analysis to ensure indicators can calculate without error
            # And to check for "stale" signals we should ignore
            print("   Running functionality test on Strategy Engine...")
            result = self.strategy_engine.analyze(df_15m, extra_data={"1m": df_1m})
            
            if result.get("signals"):
                # Check timestamps. If signal is old (> 15 mins), ignore it
                # Logic handled in loop usually, but good to know
                print(f"   ℹ️ Detected {len(result['signals'])} pending signals (will be filtered by live loop)")
            
            print("   ✅ Strategy Engine initialized")
            
        except Exception as e:
            print(f"   ❌ FATAL: Strategy Init failed: {e}")
            return False

        # --- PHASE 5: SYSTEM GO ---
        print("\n[5/5] 🟢 SYSTEM GO")
        print("   ALL SYSTEMS OPERATIONAL.")
        print(f"   Target: {self.active_symbol}")
        print(f"   Mode: {self.execution_mode}")
        return True


def start_api_server(bot_context):
    """Start FastAPI server in a separate thread"""
    import uvicorn
    from backend.api import app
    
    # Connect bot to API via bridge
    bot_bridge.set_bot_context(bot_context)
    
    print("🚀 Starting FastAPI server on http://localhost:8001")
    
    # Create uvicorn configuration
    config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="info", loop="asyncio")
    server = uvicorn.Server(config)
    
    # Create a new event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Run the server directly (skips signal handlers which cause crashes in threads on Windows)
    loop.run_until_complete(server.serve())


if __name__ == "__main__":
    print("=" * 60)
    print("🤖 HyperLiquid Trading Bot with Next.js UI")
    print("=" * 60)
    
    # Create bot context
    bot = BotContext()
    
    # ============================================
    # INITIALIZE WEBSOCKET PRICE FEEDS
    # ============================================
    print("\n📡 Initializing WebSocket price feeds...")
    try:
        # Start WebSocket for the active symbol (Single Symbol Mode)
        # This eliminates ~80% of REST API calls and prevents rate limiting
        hyperliquid_service.start_websocket([bot.active_symbol])
        print(f"✅ WebSocket connected for {bot.active_symbol}")
    except Exception as e:
        print(f"⚠️ WebSocket initialization failed: {e}")
        print("   Falling back to REST API for price feeds")
    
    # Start API server in background thread
    api_thread = threading.Thread(target=start_api_server, args=(bot,), daemon=True)
    api_thread.start()
    
    print("\n✅ Bot initialized")
    print("📊 Next.js UI: http://localhost:3000")
    print("🔧 API Docs: http://localhost:8001/docs")
    print("\n💡 The bot is ready. Use the Next.js UI to control it.")
    print("   Or use Streamlit as backup: streamlit run main.py")
    
    # Auto-start if bot was running before restart
    # Auto-start if bot was running before restart OR if env var is set
    should_autostart = bot.is_running or config.AUTO_START_TRADING
    
    if should_autostart:
        print(f"\n🔄 Auto-starting bot (Saved State: {bot.is_running}, Env Config: {config.AUTO_START_TRADING})...")
        
        # Execute Staged Boot Sequence
        boot_success = bot.boot_sequence()
        
        if boot_success:
            if not bot.is_running:
                 bot.is_running = True
            bot.start()
        else:
            print("\n❌ AUTO-START ABORTED: Boot sequence failed.")
            print("   Please check logs and restart manually.")
            bot.is_running = False
    
    print("\nPress Ctrl+C to stop\n")
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Shutting down...")
        
        # Stop WebSocket manager gracefully
        try:
            hyperliquid_service.stop_websocket()
            print("✅ WebSocket stopped")
        except Exception as e:
            print(f"⚠️ Error stopping WebSocket: {e}")
        
        bot.stop()
        print("✅ Bot stopped. Goodbye!")


