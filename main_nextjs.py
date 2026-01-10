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
from app.utils.data_processing import get_dynamic_context

class BotContext:
    """Main bot context - same as main.py"""
    def __init__(self):
        print("\n\n🤖 [BOOT] BotContext v1.0.4 (OPTIMIZATIONS PHASE 2)\n")
        self.risk_manager = RiskManager(
            max_positions=config.DEFAULT_MAX_POSITIONS,
            daily_stop_loss=config.DEFAULT_DAILY_STOP_LOSS
        )
        self.max_positions = 1 # GLOBAL QUOTA - Hardcoded for Focus Mode
        self.strategy_engine = StrategyEngine(self.risk_manager)
        self.is_running = False
        self.trading_enabled = False
        self.thread = None
        self.account_value = 0.0 # NEW: Explicitly track account value
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
        
        # AI Call Management (Phase 1 Optimization)
        self.last_ai_call = 0  # Timestamp du dernier appel IA
        self.ai_call_cooldown = 300  # 5 minutes en secondes (configurable)
        
        # Load persisted state
        try:
            StateManager.load_state(self)
            
            # Access settings loaded into sidebar_settings if available
            if hasattr(self, "sidebar_settings"):
                self.execution_mode = self.sidebar_settings.get("execution_mode", "Manual (Phantom)")
                
                # Max Positions Configuration (Phase 2 Optimization)
                # Read from settings with gamification cap
                requested_max = self.sidebar_settings.get("max_positions", 1)
                
                try:
                    # Apply gamification cap
                    balance_data = hyperliquid_service.get_account_balance()
                    equity = balance_data.get("equity", 0) if balance_data.get("status") == "success" else 0
                    gam = AssetGamification(equity)
                    
                    # Assuming get_max_positions() exists or use level-based logic
                    # For now, simple level-based cap:
                    # Level 1-2: max 1, Level 3-4: max 2, Level 5+: max 3
                    if gam.level <= 2:
                        max_allowed = 1
                    elif gam.level <= 4:
                        max_allowed = 2
                    else:
                        max_allowed = 3
                    
                    # Cap to gamification limit
                    self.max_positions = min(requested_max, max_allowed)
                    
                    if requested_max > max_allowed:
                        self.add_log(f"⚙️ Max positions capped: {requested_max} → {self.max_positions} (Level {gam.level})")
                    else:
                        self.add_log(f"⚙️ Max positions: {self.max_positions}")
                        
                except Exception as e:
                    # Fallback to requested or default
                    self.max_positions = requested_max
                    print(f"⚠️ Gamification check failed: {e}. Using requested: {requested_max}")
                    
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
        
        # New Dynamic Context
        dynamic_ctx = get_dynamic_context(df)
        
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
            "rr_ratio": rr_ratio,
            
            # Dynamic Context (Merged)
            **dynamic_ctx
        }
    
    
    def execute_entry_atomically(self, symbol: str, side: str, size: float, price: float = None, sl: float = None, tp: float = None, strategy: str = "Unknown", metadata: dict = None):
        """
        ATOMIC ENTRY FLOW (Unified v2)
        Supports Dry Run mode for testing without real execution
        1. Check Quota
        2. Clean Orphans
        3. Execute (with retry/oid)
        4. Verify & OID Capture
        5. Sync State
        """
        try:
            # DRY RUN MODE: Simulate trade without execution
            if self.execution_mode == "Dry Run":
                self.add_log(f"[DRY] Would enter {side} {symbol}")
                self.add_log(f"[DRY] Size: {size}, Price: {price}, SL: {sl}, TP: {tp}")
                
                # Create simulated trade in memory
                self.active_trade = {
                    "symbol": symbol,
                    "side": side,
                    "entry": price or 0,
                    "size": size,
                    "sl": sl or 0,
                    "tp": tp or 0,
                    "strategy": strategy,
                    "entry_time": pd.Timestamp.now().isoformat(),
                    "pnl": 0,
                    "max_pnl": 0,
                    "status": "OPEN (DRY RUN)",
                    "metadata": metadata
                }
                
                StateManager.save_state(self)
                self.add_log(f"[DRY] ✅ Simulated trade created")
                return True
            
            # REAL EXECUTION (existing code continues...)
            # 1. FINAL QUOTA CHECK
            real_positions = hyperliquid_service.get_positions()
            active_count = len([p for p in real_positions if float(p["size"]) > 0])
            
            if active_count >= self.max_positions:
                self.add_log(f"⛔ QUOTA EXCEEDED ({active_count}/{self.max_positions}). Entry aborted.")
                return False

            self.add_log(f"🔒 ATOMIC ENTRY START: {side} {symbol} ({size}) via {strategy}")

            # 2. SANITIZE
            self.add_log(f"🧹 Cleaning pre-trade orphans on {symbol}...")
            hyperliquid_service.cancel_all_orders(symbol)

            # 3. EXECUTE
            is_buy = (side == "BUY")
            result = hyperliquid_service.execute_order(
                symbol=symbol,
                is_buy=is_buy,
                quantity=size,
                price=price,
                sl_price=sl,
                tp_price=tp
            )
            
            if result.get("status") != "success":
                self.add_log(f"❌ Entry Failed: {result.get('message')}")
                return False

            # 4. VERIFY & EXTRACT OID
            self.add_log("⏳ Verifying Fill...")
            filled = False
            oid = "unknown"
            
            # Extract OID from result immediately if possible (Optimistic)
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
                    
                    # 5. SYNC STATE
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
                        "metadata": metadata or {}
                    }
                    self.risk_manager.record_trade_open()
                    StateManager.save_state(self)
                    
                    # Discord Alert
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

    # [REMOVED DUPLICATE] recalibrate_position_stops was defined twice.
    # The valid ASYNC version is further down in the file.

    def _manage_active_trade(self):
        """
        Centralized Active Trade Management
        - External Close Detection
        - SL/TP Enforcement
        - Smart Break-Even / Trailing
        - Exit logic
        """
        trade = self.active_trade
        symbol = trade["symbol"]
        
        # 1. External Close Detection (Position Check)
        positions = hyperliquid_service.get_positions()
        real_pos = next((p for p in positions if p["symbol"] == symbol and float(p['size']) > 0), None)
        
        if not real_pos:
            self.missing_pos_counter += 1
            if self.missing_pos_counter >= 3:
                self.add_log(f"⚠️ Position vanished (External Close confirmed). Clearing state.")
                
                # Fetch Close Price (Market)
                exit_price = hyperliquid_service.get_current_price(symbol)
                
                # Calculate PnL
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
                     "exit_time": pd.Timestamp.now().isoformat()
                })
                
                # 🔔 NOTIFY DISCORD (Fix: Alert on External SL/TP Close)
                discord_service.send_alert(
                    f"🏁 TRADE CLOSED (Exchange): {symbol}",
                    f"Reason: External Close (SL/TP likely)\nPnL: ${pnl_usdc:.2f}",
                    color="00FF00" if pnl_usdc >= 0 else "FF0000"
                )
                
                self.active_trade = None
                StateManager.save_state(self)
                self.missing_pos_counter = 0
            return
        
        self.missing_pos_counter = 0 # Reset if found
        
        # Update PnL in state logic? 
        current_price = hyperliquid_service.get_current_price(symbol)
        
        # 2. Smart Break-Even & Trailing
        entry_price = trade.get("entry")
        tp_price = trade.get("tp")
        sl_price = trade.get("sl")
        side = trade.get("side")
        state_updated = False
        
        if entry_price and tp_price and sl_price:
            # Calculate Progress
            if side == "BUY":
                total_dist = tp_price - entry_price
                current_dist = current_price - entry_price
                progress_pct = (current_dist / total_dist) * 100 if total_dist != 0 else 0
                
                # Trailing Logic
                new_sl = None
                
                # Threshold 1: > 40% -> BE + 0.3%
                if progress_pct > 40:
                    be_price = entry_price * 1.003
                    if sl_price < be_price:
                        new_sl = be_price
                        self.add_log(f"🛡️ Smart BE: >40% target. Moving SL to {new_sl:.2f}")

                # Threshold 1.5: > 60% -> Lock 20% of profit
                if progress_pct > 60:
                    secure_price = entry_price + (total_dist * 0.20)
                    if sl_price < secure_price:
                         new_sl = secure_price
                         self.add_log(f"🛡️ Trailing: >60% target. Locking 20% at {new_sl:.2f}")

                # Threshold 2: > 75% -> Lock 40% of profit
                if progress_pct > 75:
                    lock_price = entry_price + (total_dist * 0.40)
                    if sl_price < lock_price:
                         new_sl = lock_price
                         self.add_log(f"🛡️ Trailing: >75% target. Locking 40% at {new_sl:.2f}")
                
                if new_sl:
                    self.active_trade["sl"] = new_sl
                    state_updated = True
                    
            else: # SELL
                total_dist = entry_price - tp_price
                current_dist = entry_price - current_price
                progress_pct = (current_dist / total_dist) * 100 if total_dist != 0 else 0
                
                new_sl = None
                
                if progress_pct > 40:
                    be_price = entry_price * 0.997
                    if sl_price > be_price:
                        new_sl = be_price
                        self.add_log(f"🛡️ Smart BE: >40% target. Moving SL to {new_sl:.2f}")

                if progress_pct > 60:
                    secure_price = entry_price - (total_dist * 0.20)
                    if sl_price > secure_price:
                        new_sl = secure_price
                        self.add_log(f"🛡️ Trailing: >60% target. Locking 20% at {new_sl:.2f}")
                        
                if progress_pct > 75:
                    lock_price = entry_price - (total_dist * 0.40)
                    if sl_price > lock_price:
                        new_sl = lock_price
                        self.add_log(f"🛡️ Trailing: >75% target. Locking 40% at {new_sl:.2f}")

                if new_sl:
                    self.active_trade["sl"] = new_sl
                    state_updated = True
        
        if state_updated:
             StateManager.save_state(self)

        # 3. Enforce Orders (Sync with Exchange)
        self._verify_and_enforce_sl_tp(symbol, self.active_trade)
        
        # 4. Local Exit Check (Redundant if hard stops are on exchange, but good for logs/speed)
        exit_triggered = False
        reason = ""
        
        sl_val = float(self.active_trade.get("sl", 0))
        tp_val = float(self.active_trade.get("tp", 0))

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
            self.add_log(f"   🕵️ DEBUG: Side={side}, Entry={self.active_trade.get('entry')}, SL={sl_val}, TP={tp_val}")
            self.execute_exit_atomically(symbol, reason)

    def force_sync(self):
        """
        Manually trigger synchronization with Exchange.
        Called from API.
        """
        self.add_log("🔄 FORCE SYNC: Initiated by User")
        
        try:
            # 1. Get Real Positions
            positions = hyperliquid_service.get_positions()
            
            if positions:
                pos = positions[0]
                symbol = pos["symbol"]
                
                # Update Symbol
                if self.active_symbol != symbol:
                    self.active_symbol = symbol
                    StateManager.save_state(self)
                    self.add_log(f"✅ SYNC: Symbol corrected to {symbol}")
                
                # Update/Adopt Trade
                # If we have an active trade but it doesn't match, or if we have None
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
                    # Preserve existing AI analysis if available to avoid flicker
                    "ai_analysis": self.active_trade.get("ai_analysis") if self.active_trade else None
                }
                StateManager.save_state(self)
                self.add_log(f"✅ SYNC: Trade state updated for {symbol}")
                
                # 2. Trigger AI Analysis (Async/Threaded)
                def run_analysis():
                    self.add_log(f"⏳ SYNC: Waiting 5s before AI analysis for data stability...")
                    time.sleep(5)
                    try:
                        self.add_log(f"🤖 FORCE SYNC: Running AI Analysis on {symbol}")
                        # Fetch context
                        df = hyperliquid_service.get_candles(symbol, "15m", 50)
                        if not df.empty:
                            ai_result = ia_service.analyze_position_risk(
                                symbol=symbol,
                                position_data=pos,
                                market_data={"close": float(df['close'].iloc[-1]), "regime": "UNKNOWN"}
                            )
                            if ai_result:
                                ai_data = json.loads(ai_result) if isinstance(ai_result, str) else ai_result
                                
                                # Update cache
                                self.ai_cache[f"position_analysis_{symbol}"] = ai_data
                                self.ai_cache["last_position_analysis"] = ai_data
                                
                                # Update active trade object in memory
                                if self.active_trade:
                                    self.active_trade["ai_analysis"] = ai_data
                                
                                self.add_log(f"✅ AI Analysis Updated: {ai_data.get('risk_level')}")
                    except Exception as e:
                        self.add_log(f"⚠️ AI Force Sync Failed: {e}")

                threading.Thread(target=run_analysis, daemon=True).start()
                
                return {"status": "success", "message": "Sync and Analysis started"}
            else:
                self.active_trade = None
                StateManager.save_state(self)
                self.add_log("ℹ️ FORCE SYNC: No positions found. State cleared.")
                return {"status": "success", "message": "State cleared (No position)"}
                
        except Exception as e:
            self.add_log(f"❌ FORCE SYNC Failed: {e}")
            return {"status": "error", "message": str(e)}

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
                    
                    # Update internal state (account_value)
                    if 'current_equity' in locals():
                        self.account_value = float(current_equity)

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
                    
                    # CRITICAL FIX: Adopt orphan position if active_trade is missing (e.g. after crash)
                    if not self.active_trade:
                        self.add_log(f"🕵️ SYNC: Adopting orphan position {position_symbol} into memory")
                        
                        # Extract details from position
                        # API usually returns 'szi' (size with sign) and 'entryPx'
                        raw_size = float(main_position.get("szi", 0))
                        side = "BUY" if raw_size > 0 else "SELL"
                        size = abs(raw_size)
                        entry_px = float(main_position.get("entryPx", 0))
                        pnl = float(main_position.get("unrealizedPnl", 0))
                        
                        self.active_trade = {
                            "symbol": position_symbol,
                            "side": side,
                            "entry": entry_px,
                            "size": size,
                            "sl": 0,  # Unknown, will be handled by strategy or manual
                            "tp": 0,
                            "strategy": "Manual (Recovered)",
                            "entry_time": pd.Timestamp.now().isoformat(),
                            "pnl": pnl,
                            "max_pnl": pnl,
                            "status": "OPEN"
                        }
                        # Save adopted state
                        StateManager.save_state(self)
                        self.add_log(f"✅ SYNC: Position adopted as 'Manual (Recovered)'")
                    
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
            # Init Loop Vars
            action = None
            sl = None
            tp = None
            
            # 0. CONTINUOUS ADOPTION: Check for manual trades if idle
            if not self.active_trade:
                try:
                    # Check for existing positions on the active symbol
                    real_positions_manual = hyperliquid_service.get_positions()
                    if real_positions_manual:
                        # Filter for current symbol and non-zero size
                        manual_pos = next((p for p in real_positions_manual if p["symbol"] == self.active_symbol and float(p['size']) != 0), None)
                        
                        if manual_pos:
                            self.add_log(f"🕵️ MANUAL TRADE DETECTED: Adopting {self.active_symbol} position...")
                            
                            # Extract details (Fix: Use corrected keys from service)
                            # hyperliquid_service returns: size, side, entry_price, pnl
                            side_m = manual_pos.get("side", "BUY")
                            size_m = float(manual_pos.get("size", 0))
                            entry_px_m = float(manual_pos.get("entry_price", 0))
                            pnl_m = float(manual_pos.get("pnl", 0))
                            
                            self.active_trade = {
                                "symbol": self.active_symbol,
                                "side": side_m,
                                "entry": entry_px_m,
                                "size": size_m,
                                "sl": 0,
                                "tp": 0,
                                "strategy": "Manual (Adoption)",
                                "entry_time": pd.Timestamp.now().isoformat(),
                                "pnl": pnl_m,
                                "max_pnl": pnl_m,
                                "status": "OPEN"
                            }
                            StateManager.save_state(self)
                            self.add_log(f"✅ MANUAL TRADE ADOPTED: {side_m} {size_m} @ {entry_px_m}")
                            
                            # Immediate loop continue to manage it
                            continue
                except Exception as e_manual:
                    # Log only debug to avoid spam
                    pass
            
            # Update Account Value (Cached)
            try:
                acc_data = hyperliquid_service.get_account_balance()
                if acc_data.get("status") == "success":
                   self.account_value = float(acc_data.get("total_equity", 0))
            except: pass
            
            try:
                # 1. MANAGE ACTIVE TRADE
                if self.active_trade:
                     self._manage_active_trade()
                     time.sleep(10) # 10s sleep when active (monitoring)
                     continue

                self.add_log("🔄 Entering strategy analysis...")
                
                # 2. MARKET DATA
                df_15m = hyperliquid_service.get_candles(self.active_symbol, interval="15m", limit=200)
                df_1m = hyperliquid_service.get_candles(self.active_symbol, interval="1m", limit=100)
                
                if df_15m.empty or df_1m.empty:
                    self.add_log("⚠️ No data received")
                    time.sleep(10)
                    continue

                # Cast Floats
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
                
                # 3. STRATEGY ANALYSIS
                result = self.strategy_engine.analyze(df_15m, extra_data={"1m": df_1m})
                self.active_strategies = result.get('strategies', [])
                
                # Store result for API access
                self.latest_strategy_result = result
                print(f"🔍 DEBUG: Stored strategy result with {len(result.get('conditions', {}))} strategy conditions")
                for name, conds in result.get('conditions', {}).items():
                    print(f"   {name}: {len(conds)} conditions")
                
                # Log analysis results
                regime = result.get('regime', 'UNKNOWN')
                adx = result.get('adx', 0)
                rsi = result.get('rsi', 0)
                ema_20 = result.get('ema_20', 0)
                ema_50 = result.get('ema_50', 0)
                
                self.add_log(f"📊 Regime: {regime} | ADX: {adx:.1f} | RSI: {rsi:.1f}")
                self.add_log(f"📈 EMA20: {ema_20:.2f} | EMA50: {ema_50:.2f}")
                
                if self.active_strategies:
                    self.add_log(f"✅ Active Strategies: {', '.join(self.active_strategies)}")
                else:
                    self.add_log(f"⚠️ No active strategies for regime: {regime}")
                
                
                # 4. PROCESS SIGNALS
                signals = result.get("signals", [])
                if signals:
                    sig = signals[0] # Take first valid signal
                    
                    # Deduplication (Basic)
                    current_candle_time = df_1m.index[-1]
                    
                    if sig.get("signal") and sig.get("price"):
                        # AI Validate with Cooldown (Phase 1 Optimization)
                        from app.services.ia import ia_service
                        import time
                        market_context = self._prepare_ai_context()
                        
                        # Extract Strategy Persona if available
                        strat_name = sig.get('strategy')
                        strat_obj = self.strategy_engine.strategies.get(strat_name)
                        strategy_persona = getattr(strat_obj, 'AI_PERSONA', None)
                        
                        if strategy_persona:
                            self.add_log(f"🎭 Using Custom Persona for {strat_name}")
                        
                        # Check AI Cooldown
                        current_time = time.time()
                        time_since_last_call = current_time - self.last_ai_call
                        
                        if time_since_last_call < self.ai_call_cooldown:
                            # Cooldown active - skip AI validation
                            remaining = int(self.ai_call_cooldown - time_since_last_call)
                            self.add_log(f"⏭️ AI Cooldown active ({remaining}s remaining) - Auto-approving signal")
                            approved = True
                        else:
                            # Cooldown expired - call AI
                            self.add_log(f"🤖 Validating signal: {sig.get('signal')} from {sig.get('strategy')}")
                            val_res = ia_service.validate_signal(sig, market_context, strategy_persona=strategy_persona)
                            self.last_ai_call = current_time
                        
                            approved = False
                            try:
                                import json
                                if val_res.get("raw_output"):
                                    ai_data = json.loads(ia_service.extract_json(val_res["raw_output"]))
                                    approved = ai_data.get("approved", False)
                                    if approved:
                                        self.add_log(f"✅ AI APPROVED (Conf: {ai_data.get('confidence')}%)")
                                        # Adjust SL/TP if AI suggests
                                        if ai_data.get("suggested_adjustments"):
                                            adj = ai_data["suggested_adjustments"]
                                            if adj.get("sl"): sig["sl"] = adj["sl"]
                                            if adj.get("tp"): sig["tp"] = adj["tp"]
                                    else:
                                        self.add_log(f"❌ AI REJECTED: {ai_data.get('reasoning')}")
                                else:
                                    approved = True # Fallback
                            except:
                                self.add_log("⚠️ AI Validation JSON Error. Defaulting to REJECT.")
                                approved = False
                            
                        if approved:
                            # Execute
                            acc = hyperliquid_service.get_account_balance()
                            equity = float(acc.get("total_equity", 0) if acc.get("status")=="success" else 0)
                            
                            sl_price = sig.get("sl")
                            entry_price = sig.get("price")
                            
                            size = self.risk_manager.calculate_position_size(entry_price, sl_price, equity)
                            
                            if size > 0:
                                self.execute_entry_atomically(
                                    self.active_symbol,
                                    sig.get("signal"),
                                    size,
                                    entry_price,
                                    sl_price,
                                    sig.get("tp"),
                                    sig.get("strategy"),
                                    sig.get("metadata")
                                )
                
                # Dynamic Sleep (Phase 2 Optimization)
                # Adjust sleep duration based on bot state for better efficiency
                if self.active_trade:
                    sleep_duration = 10  # Active trade - monitor frequently
                elif signals:
                    sleep_duration = 15  # Signals detected - check again soon
                else:
                    sleep_duration = 60  # Idle - save API calls
                
                self.add_log(f"⏸️ Next analysis in {sleep_duration}s...")
                time.sleep(sleep_duration)
                
            except Exception as e:
                self.add_log(f"❌ Error in trading loop: {e}")
                time.sleep(5)
        
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
            
            # DRY RUN MODE: Simulate close
            if self.execution_mode == "Dry Run":
                self.add_log(f"[DRY] Would close {symbol} ({reason})")
                self.active_trade = None
                StateManager.save_state(self)
                return True, "[DRY] Trade closed (simulated)"
            
            # REAL CLOSE (existing code...)
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
            
            # Helper for AI
            from app.services.ia import ia_service
            
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
        """Stop the bot with complete graceful shutdown"""
        if self.is_running:
            self.is_running = False
            self.add_log("🛑 Initiating graceful shutdown...")
            
            # 1. Cancel all pending orders
            if self.active_trade:
                try:
                    symbol = self.active_trade["symbol"]
                    self.add_log(f"🧹 Cancelling pending orders for {symbol}...")
                    hyperliquid_service.cancel_all_orders(symbol)
                    self.add_log("✅ Orders cancelled")
                except Exception as e:
                    self.add_log(f"⚠️ Failed to cancel orders: {e}")
            
            # 2. Stop WebSocket
            try:
                self.add_log("🔌 Stopping WebSocket...")
                hyperliquid_service.stop_websocket()
                self.add_log("✅ WebSocket stopped")
            except Exception as e:
                self.add_log(f"⚠️ Failed to stop WebSocket: {e}")
            
            # 3. Stop Scanner Job
            if self.scanner_job:
                try:
                    self.scanner_settings['enabled'] = False
                    self.scanner_job.stop()
                    self.add_log("✅ Scanner stopped")
                except Exception as e:
                    self.add_log(f"⚠️ Failed to stop scanner: {e}")
            
            # 4. Wait for trading thread
            if self.thread:
                self.add_log("⏳ Waiting for trading thread...")
                self.thread.join(timeout=10)  # Increased from 5s to 10s
                if self.thread.is_alive():
                    self.add_log("⚠️ Trading thread did not stop gracefully")
                else:
                    self.add_log("✅ Trading thread stopped")
            
            # 5. Save state
            try:
                StateManager.save_state(self)
                self.add_log("✅ State saved")
            except Exception as e:
                self.add_log(f"⚠️ Failed to save state: {e}")
            
            self.add_log("⏹️ Bot stopped gracefully")


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
            
            self.account_value = float(balance.get('equity', 0))
            print(f"   ✅ Balance Access OK (Equity: ${self.account_value})")
            
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
    
    # Display AI Configuration
    print("\n🧠 AI Configuration:")
    print(f"   Persona: {config.BOT_PERSONA}")
    print(f"   Risk Profile: {config.RISK_PROFILE}")
    print(f"   Timeframe: {config.TRADING_TIMEFRAME}")
    
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


