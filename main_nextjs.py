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
from app.core.state_manager import StateManager
from app.services.hyperliquid_service import hyperliquid_service
from app.services.discord_service import discord_service
from app.core.scanner_job import ScannerJob
from app.core.trade_recorder import TradeRecorder
from strategies.engine import StrategyEngine
import pandas as pd
from collections import deque

# Import bot bridge
from backend.bot_bridge import bot_bridge

class BotContext:
    """Main bot context - same as main.py"""
    def __init__(self):
        self.risk_manager = RiskManager(
            max_positions=config.DEFAULT_MAX_POSITIONS,
            daily_stop_loss=config.DEFAULT_DAILY_STOP_LOSS
        )
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
            "auto_switch": False
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
            entry = position_data.get('entry_price', current_price)
            side = position_data.get('side', 'BUY')
            
            # Calculate PnL
            if side == 'BUY':
                pnl_percent = ((current_price - entry) / entry) * 100
            else:
                pnl_percent = ((entry - current_price) / entry) * 100
            
            # Time in trade
            if 'timestamp' in position_data:
                entry_time = pd.Timestamp(position_data['timestamp'])
                time_in_trade = str(pd.Timestamp.now() - entry_time).split('.')[0]
            
            # SL/TP distances
            if 'sl' in position_data and position_data['sl']:
                sl_distance = abs((position_data['sl'] - entry) / entry) * 100
            if 'tp' in position_data and position_data['tp']:
                tp_distance = abs((position_data['tp'] - entry) / entry) * 100
            
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
                    target_leverage = int(self.sidebar_settings.get("leverage", 5))
                    margin_type = self.sidebar_settings.get("margin_type", "Cross")
                    is_cross = (margin_type == "Cross")
                    
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
                            from app.services.gemini_service import gemini_service
                            import json
                            self.add_log(f"🤖 Running AI analysis on {position_symbol} position...")
                            
                            # Fetch fresh data for the CORRECT symbol
                            df = hyperliquid_service.get_candles(self.active_symbol, "15m", 50)
                            
                            if not df.empty:
                                ai_result = gemini_service.analyze_position_risk(
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
            self.add_log("🔄 Entering loop iteration...")
            try:
                self.add_log("📡 Fetching candles...")
                # Fetch both 15m and 1m candles for MTF strategies
                df_15m = hyperliquid_service.get_candles(self.active_symbol, interval="15m", limit=200)
                df_1m = hyperliquid_service.get_candles(self.active_symbol, interval="1m", limit=100)
                
                if df_15m.empty:
                    self.add_log("⚠️ No 15m data received")
                    time.sleep(10)
                    continue
                
                if df_1m.empty:
                    self.add_log("⚠️ No 1m data received")
                    time.sleep(10)
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
                            try:
                                from app.services.gemini_service import gemini_service
                                import json
                                
                                # Prepare comprehensive market context
                                market_context = self._prepare_ai_context(active_symbol_pos)
                                
                                # Call AI for position risk analysis with full context
                                ai_risk_analysis = gemini_service.analyze_position_risk(
                                    symbol=self.active_symbol,
                                    position_data=active_symbol_pos,
                                    market_data=market_context
                                )
                                
                                # Parse AI response
                                if ai_risk_analysis.get("raw_output"):
                                    ai_data = json.loads(ai_risk_analysis["raw_output"])
                                    sl = ai_data.get("stop_loss_suggestion")
                                    tp = ai_data.get("take_profit_suggestion")
                                    risk_score = ai_data.get("risk_score", "N/A")
                                    reasoning = ai_data.get("reasoning", "AI analysis complete")
                                    
                                    # Fallback to ATR if AI doesn't provide suggestions
                                    if not sl or not tp:
                                        self.add_log("⚠️ AI didn't provide SL/TP, using ATR fallback")
                                        atr = 0
                                        if hasattr(self, 'latest_data') and not self.latest_data.empty and 'ATRr_14' in self.latest_data.columns:
                                            atr = self.latest_data['ATRr_14'].iloc[-1]
                                        else:
                                            atr = current_price * 0.01
                                        
                                        if side == "BUY":
                                            sl = sl or (entry_price - (2.0 * atr))
                                            tp = tp or (entry_price + (3.0 * atr))
                                        else:
                                            sl = sl or (entry_price + (2.0 * atr))
                                            tp = tp or (entry_price - (3.0 * atr))
                                    
                                    self.add_log(f"🤖 AI Analysis (Risk: {risk_score}): {reasoning}")
                                    self.add_log(f"   AI Suggested SL: {sl:.4f}, TP: {tp:.4f}")
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
                            self.add_log(f"   Current Price: {current_price} | SL: {sl:.4f} | TP: {tp:.4f}")
                            discord_service.send_alert(
                                "🛡️ MANUAL TRADE ADOPTED (AI-Validated)",
                                f"Symbol: {self.active_symbol}\nSide: {side}\nEntry: {entry_price}\nCurrent: {current_price}\nAI SL: {sl:.4f}\nAI TP: {tp:.4f}\nSize: {active_symbol_pos['size']}\nLeverage: {active_symbol_pos.get('leverage', 1.0)}x",
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
                             
                             if time_since_entry > 30: # 30 seconds grace period
                                 self.add_log(f"⚠️ Position vanished on exchange! Closing bot trade.")
                                 
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
                             else:
                                 self.add_log(f"⏳ Position pending verification ({time_since_entry:.1f}s ago)...")
                
                except Exception as e:
                    self.add_log(f"⚠️ Error checking positions: {e}")
                
                # === SYNCHRONISATION RISK MANAGER ===
                # Force sync avec Hyperliquid (source de vérité)
                try:
                    sync_result = self.risk_manager.sync_with_hyperliquid(hyperliquid_service)
                    if sync_result.get("synced"):
                        self.add_log(f"🔄 SYNC: Positions {sync_result['old_count']} → {sync_result['new_count']}")
                except Exception as e:
                    self.add_log(f"⚠️ Sync error: {e}")
                
                
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
                    
                    self.add_log(f"📊 Analysis complete: {result.get('regime', 'UNKNOWN')} regime, {len(result.get('signals', []))} signals")
                    
                    # AI: Analyse périodique du marché (toutes les 15 minutes)
                    try:
                        from app.services.gemini_service import gemini_service
                        from datetime import datetime, timedelta
                        
                        now = datetime.now()
                        last_analysis_time = self.ai_cache.get("last_market_analysis_time")
                        
                        # Analyser toutes les 15 minutes
                        if not last_analysis_time or (now - last_analysis_time) > timedelta(minutes=15):
                            # Préparer le snapshot actuel
                            current_snapshot = {
                                "symbol": self.active_symbol,
                                "price": float(df_15m['close'].iloc[-1]),
                                "regime": result.get('regime', 'UNKNOWN'),
                                "timestamp": now.isoformat()
                            }
                            
                            # Récupérer le snapshot précédent
                            previous_snapshot = self.ai_cache["market_snapshots"][-1] if self.ai_cache["market_snapshots"] else None
                            
                            # Analyser l'évolution
                            evolution_analysis = gemini_service.analyze_market_evolution(current_snapshot, previous_snapshot)
                            
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
                    last_candle_time = df_1m.index[-1]
                    if last_candle_time == self.last_analyzed_candle:
                        self.add_log(f"⏸️ Same candle {last_candle_time}, waiting for next 1m candle...")
                        time.sleep(30)  # Wait for next candle
                        continue
                    
                    # NEW CANDLE - Run analysis
                    self.add_log(f"🔍 Analyzing new 1m candle at {last_candle_time}")
                    self.last_analyzed_candle = last_candle_time
                    
                    # Process signals (Only if NO active trade)
                    if result.get("signals") and not self.active_trade:
                        sig_data = result["signals"][0]
                        strat_name = sig_data.get("strategy", "Unknown")
                        action = sig_data.get("signal")
                        entry_price = sig_data.get("price")
                        sl = sig_data.get("sl", entry_price * 0.95)
                        tp = sig_data.get("tp", entry_price * 1.05)
                        
                        # AI: Validate signal before execution
                        ai_approved = False
                        ai_reasoning = "No AI validation performed"
                        
                        try:
                            from app.services.gemini_service import gemini_service
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
                            validation_result = gemini_service.validate_signal(
                                signal_data=signal_for_validation,
                                market_context=market_context
                            )
                            
                            # Parse AI response
                            if validation_result.get("raw_output"):
                                ai_data = json.loads(validation_result["raw_output"])
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
                                        self.add_log(f"   Risk Factors: {', '.join(risk_factors)}")
                            else:
                                # AI failed, use conservative approach
                                self.add_log("⚠️ AI validation failed, proceeding with caution")
                                ai_approved = True  # Allow trade but log the failure
                                
                        except Exception as e:
                            self.add_log(f"⚠️ AI validation error: {e}, proceeding with trade")
                            ai_approved = True  # Fallback to allowing trade
                        
                        # Only execute if AI approved OR if user wants manual approval
                        if not ai_approved:
                            self.add_log(f"🚫 Signal REJECTED by AI: {action} {self.active_symbol} @ {entry_price}")
                            # Log rejected signal for analysis
                            log_entry = {
                                "time": pd.Timestamp.now(),
                                "symbol": self.active_symbol,
                                "strategy": strat_name,
                                "type": action,
                                "price": entry_price,
                                "action": "AI_REJECTED",
                                "ai_reasoning": ai_reasoning
                            }
                            self.signals_log.append(log_entry)
                            continue  # Skip this signal
                        
                        # Signal approved by AI, proceed with execution
                        try:
                            from app.services.gemini_service import gemini_service
                            
                            signal_for_ai = {
                                "signal": action,
                                "price": entry_price,
                                "sl": sl,
                                "tp": tp,
                                "strategy": strat_name,
                                "comment": sig_data.get("comment", "")
                            }
                            
                            market_context = {
                                "symbol": self.active_symbol,
                                "regime": result.get('regime', 'UNKNOWN'),
                                "price": entry_price
                            }
                            
                            # CRITICAL: Déduplication - créer hash unique du signal
                            import hashlib
                            signal_hash = hashlib.md5(
                                f"{strat_name}_{self.active_symbol}_{action}_{int(pd.Timestamp.now().timestamp() / 300)}".encode()
                            ).hexdigest()
                            
                            # Vérifier si ce signal a déjà été analysé (dans les 5 dernières minutes)
                            recent_hashes = [
                                item.get("signal_hash") 
                                for item in list(self.ai_cache["signal_analyses"])[-10:]
                            ]
                            
                            if signal_hash not in recent_hashes:
                                # Nouveau signal unique - analyser avec IA
                                ai_analysis = gemini_service.analyze_trade_signal(signal_for_ai, market_context)
                                
                                # Stocker l'analyse avec hash
                                self.ai_cache["signal_analyses"].append({
                                    "signal": signal_for_ai,
                                    "analysis": ai_analysis,
                                    "timestamp": pd.Timestamp.now().isoformat(),
                                    "signal_hash": signal_hash  # Pour déduplication
                                })
                                
                                # Logger l'explication IA
                                if ai_analysis.get("raw_output"):
                                    try:
                                        import json
                                        ai_data = json.loads(ai_analysis["raw_output"])
                                        self.add_log(f"🤖 IA: {ai_data.get('explanation', 'Signal analysé')}")
                                    except:
                                        pass
                            else:
                                # Signal déjà analysé récemment - skip pour économiser tokens
                                self.add_log(f"⏭️ Signal {strat_name} déjà analysé récemment (cache)")
                        except Exception as e:
                            print(f"Error in AI signal analysis: {e}")
                        
                        # CRITICAL: Check if trading is enabled
                        if not self.trading_enabled:
                            self.add_log(f"⚠️ Signal detected but trading is DISABLED: {action} {strat_name}")
                            continue  # Skip execution completely - don't create phantom positions
                        elif sig_data.get("manual_approval"):
                            # MANUEL - SIGNATURE REQUISE
                            # On ne trade pas, on prévient juste, SAUF si le trade existe déjà (Just-In-Time adoption)
                            
                            # CRITICAL: Double check against exchange before spamming
                            jit_positions = hyperliquid_service.get_positions()
                            existing_pos = next((p for p in jit_positions if p["symbol"] == self.active_symbol), None)
                            
                            if existing_pos:
                                self.add_log(f"🕵️ JIT: Found existing position on {self.active_symbol} just before alert. Adopting instead.")
                                
                                # CRITICAL FIX: Use AI to suggest appropriate SL/TP instead of hardcoded ±5%
                                try:
                                    from app.services.gemini_service import gemini_service
                                    
                                    # Get AI suggestion for SL/TP
                                    ai_risk_analysis = gemini_service.analyze_position_risk(
                                        symbol=self.active_symbol,
                                        position_data=existing_pos,
                                        market_data={"price": existing_pos["entry_price"], "regime": result.get("regime", "UNKNOWN")}
                                    )
                                    
                                    # Parse AI suggestions
                                    import json
                                    if ai_risk_analysis.get("raw_output"):
                                        ai_data = json.loads(ai_risk_analysis["raw_output"])
                                        suggested_sl = ai_data.get("stop_loss_suggestion")
                                        suggested_tp = ai_data.get("take_profit_suggestion")
                                        
                                        # Fallback to ±5% if AI doesn't provide suggestions
                                        if not suggested_sl:
                                            suggested_sl = existing_pos["entry_price"] * 0.95 if existing_pos["side"] == "BUY" else existing_pos["entry_price"] * 1.05
                                        if not suggested_tp:
                                            suggested_tp = existing_pos["entry_price"] * 1.05 if existing_pos["side"] == "BUY" else existing_pos["entry_price"] * 0.95
                                        
                                        self.add_log(f"🤖 AI Suggested SL: {suggested_sl:.2f}, TP: {suggested_tp:.2f}")
                                    else:
                                        # AI failed, use conservative defaults
                                        suggested_sl = existing_pos["entry_price"] * 0.95 if existing_pos["side"] == "BUY" else existing_pos["entry_price"] * 1.05
                                        suggested_tp = existing_pos["entry_price"] * 1.05 if existing_pos["side"] == "BUY" else existing_pos["entry_price"] * 0.95
                                        self.add_log(f"⚠️ AI unavailable, using default SL/TP")
                                except Exception as e:
                                    # AI failed, use conservative defaults
                                    self.add_log(f"⚠️ AI validation failed: {e}, using default SL/TP")
                                    suggested_sl = existing_pos["entry_price"] * 0.95 if existing_pos["side"] == "BUY" else existing_pos["entry_price"] * 1.05
                                    suggested_tp = existing_pos["entry_price"] * 1.05 if existing_pos["side"] == "BUY" else existing_pos["entry_price"] * 0.95
                                
                                self.active_trade = {
                                    "symbol": self.active_symbol,
                                    "side": existing_pos["side"],
                                    "entry": existing_pos["entry_price"],
                                    "sl": suggested_sl,
                                    "tp": suggested_tp,
                                    "strategy": strat_name, # Associate the signal's strategy!
                                    "timestamp": pd.Timestamp.now().isoformat(),
                                    "size": existing_pos["size"],
                                    "leverage": existing_pos.get("leverage", 1.0)
                                }
                                self.risk_manager.record_trade_open()
                                continue # Skip alert, we are now managing it
                            
                            msg = f"📝 MANUAL OPPORTUNITY: {action} {self.active_symbol} @ {entry_price} (SL: {sl:.2f}, TP: {tp:.2f}) [{strat_name}]"
                            self.add_log(msg)
                            
                            try:
                                discord_service.send_alert(
                                    f"🔎 VALIDATION REQUISE : {strat_name}",
                                    f"Symbol: {self.active_symbol}\nPrice: {entry_price}\nAction: {action}\nSL: {sl} | TP: {tp}\n\n👉 Vérifiez le graphique et prenez le trade manuellement.",
                                    color="00AAFF" # Bleu
                                )
                            except:
                                pass
                            
                            # LOG TO SIGNALS FOR UI
                            log_entry = {
                                "time": pd.Timestamp.now(),
                                "symbol": self.active_symbol,
                                "strategy": strat_name,
                                "type": action,
                                "price": entry_price,
                                "action": "MANUAL_REQ",
                                "manual_approval": True
                            }
                            self.signals_log.append(log_entry)
                        else:
                            can_trade, reason = self.risk_manager.check_can_trade()
                            if can_trade:
                                # Open trade
                                # 1. Calculate Position Size
                                size = 0.0
                                try:
                                    size_type = self.sidebar_settings.get("size_type", "Fixed (USDC)")
                                    size_value = float(self.sidebar_settings.get("size_value", 15.0)) # Default usually 15-20$ min on HL
                                    leverage = int(self.sidebar_settings.get("leverage", 5))
                                    
                                    if size_type == "Fixed (USDC)":
                                        # Size in coins = (USDC Value * Leverage) / Price
                                        if entry_price > 0:
                                            # Example: $100 margin * 5x = $500 position / $50000 BTC = 0.01 BTC
                                            # Wait, usually "Fixed (USDC)" implies Margin Amount.
                                            # Let's assume size_value is the MARGIN amount.
                                            position_value = size_value * leverage
                                            size = position_value / entry_price
                                    elif size_type == "% Balance":
                                         # Balance based calculation (needs balance fetch, skipped for safety/simplicity now, fallback to Fixed)
                                         # Fallback to $20 margin * leverage
                                         position_value = 20.0 * leverage
                                         size = position_value / entry_price
                                         
                                except Exception as e:
                                    self.add_log(f"⚠️ Error calculating size: {e}. Using min default.")
                                    size = (20.0 * 5) / entry_price if entry_price else 0

                                self.active_trade = {
                                    "symbol": self.active_symbol,
                                    "side": action,
                                    "entry": entry_price,
                                    "sl": sl,
                                    "tp": tp,
                                    "strategy": strat_name,
                                    "timestamp": pd.Timestamp.now().isoformat(),
                                    "size": size,
                                    "leverage": self.sidebar_settings.get("leverage", 5)
                                }
                                self.risk_manager.record_trade_open()
                                
                                # 2. EXECUTE ORDER ON HYPERLIQUID
                                if self.execution_mode == "Auto (Hyperliquid)":
                                    self.add_log(f"🚀 EXECUTING {action} {size:.5f} {self.active_symbol} (Market)")
                                    is_buy = (action == "BUY")
                                    # Execute Market Order
                                    # Execute Market Order with Hard Stops
                                    hyperliquid_service.execute_order(
                                        self.active_symbol,
                                        is_buy,
                                        size,
                                        price=None,
                                        sl_price=sl,
                                        tp_price=tp
                                    )
                                
                                msg = f"🚨 ENTRY: {action} {self.active_symbol} @ {entry_price} (SL: {sl:.2f}, TP: {tp:.2f}) [{strat_name}]"
                                self.add_log(msg)
                                
                                log_entry = {
                                    "time": pd.Timestamp.now(),
                                    "symbol": self.active_symbol,
                                    "strategy": strat_name,
                                    "type": action,
                                    "price": entry_price,
                                    "action": "OPENED"
                                }
                                self.signals_log.append(log_entry)
                                
                                # Send Discord notification with AI analysis
                                try:
                                    discord_msg = f"Strategy: {strat_name}\nSL: {sl}\nTP: {tp}"
                                    
                                    # Ajouter l'analyse IA si disponible
                                    if ai_analysis.get("raw_output"):
                                        try:
                                            import json
                                            ai_data = json.loads(ai_analysis["raw_output"])
                                            discord_msg += f"\n\n🤖 IA: {ai_data.get('explanation', '')}"
                                            discord_msg += f"\nConfiance: {ai_data.get('confidence', 'N/A')}"
                                        except:
                                            pass
                                    
                                    discord_service.send_trade_signal(
                                        self.active_symbol, 
                                        action, 
                                        entry_price, 
                                        discord_msg
                                    )
                                except Exception as e:
                                    print(f"Failed to send Discord signal: {e}")
                                
                                # Save state
                                StateManager.save_state(self)
                            else:
                                # LOG THE REASON FOR REJECTION
                                self.add_log(f"⚠️ Trade rejected by Risk Manager: {reason}")
                else:
                    # Log why we're skipping (only every 12th iteration to avoid spam = once per minute)
                    if not hasattr(self, '_skip_counter'):
                        self._skip_counter = 0
                    self._skip_counter += 1
                    if self._skip_counter % 12 == 0:
                        self.add_log(f"⏸️ Same candle {current_candle_time}, waiting for next 1m candle...")
                
                # --- Position Sync moved to start of loop ---

                # Check active trade management
                if self.active_trade:
                    current_price = df_15m['close'].iloc[-1]
                    entry_price = self.active_trade["entry"]
                    tp_price = self.active_trade["tp"]
                    sl_price = self.active_trade["sl"]
                    side = self.active_trade["side"]
                    
                    # AI: Analyser la position active (toutes les 5 minutes)
                    try:
                        from app.services.gemini_service import gemini_service
                        from datetime import datetime, timedelta
                        
                        now = datetime.now()
                        last_pos_analysis_time = self.ai_cache.get("last_position_analysis_time")
                        
                        # Analyser toutes les 5 minutes
                        if not last_pos_analysis_time or (now - last_pos_analysis_time) > timedelta(minutes=5):
                            market_context = {
                                "price": float(current_price),
                                "symbol": self.active_symbol
                            }
                            
                            position_analysis = gemini_service.analyze_active_position(self.active_trade, market_context)
                            
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
                    # If price moved 50% towards TP, move SL to Entry
                    be_triggered = False
                    
                    if side == "BUY":
                        dist_to_tp = tp_price - entry_price
                        current_dist = current_price - entry_price
                        
                        # Trigger BE if moved 50% to TP and SL is below Entry
                        if current_dist >= (dist_to_tp * 0.5) and sl_price < entry_price:
                            self.active_trade["sl"] = entry_price * 1.001 # Variable BE (slight profit)
                            self.add_log(f"🛡️ SECURED: Moved SL to Break Even @ {self.active_trade['sl']:.2f}")
                            be_triggered = True
                            
                    else: # SELL
                        dist_to_tp = entry_price - tp_price
                        current_dist = entry_price - current_price
                        
                        # Trigger BE if moved 50% to TP and SL is above Entry
                        if current_dist >= (dist_to_tp * 0.5) and sl_price > entry_price:
                            self.active_trade["sl"] = entry_price * 0.999 # Variable BE
                            self.add_log(f"🛡️ SECURED: Moved SL to Break Even @ {self.active_trade['sl']:.2f}")
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
                    if side == "BUY":
                        if current_price <= self.active_trade["sl"]:
                            self.add_log(f"🛑 SL HIT @ {current_price}")
                            
                            # Execute Close
                            if self.execution_mode == "Auto (Hyperliquid)":
                                try:
                                    self.add_log(f"📉 CLOSING LONG {self.active_trade['symbol']} (SL)")
                                    hyperliquid_service.execute_order(
                                        self.active_trade['symbol'], 
                                        False, # SELL
                                        self.active_trade['size']
                                    )
                                except Exception as e:
                                    self.add_log(f"❌ Failed to execution SL close: {e}")

                            try:
                                # CORRECT PNL CALCULATION
                                size = self.active_trade.get("size", 0)
                                leverage = self.active_trade.get("leverage", 1)
                                pnl_per_coin = current_price - entry_price  # Long PnL
                                pnl_usdc = pnl_per_coin * size * leverage
                                
                                discord_service.send_alert(
                                    "🛑 STOP LOSS HIT",
                                    f"Symbol: {self.active_symbol}\nPrice: {current_price}\nPnL: ${pnl_usdc:.2f} USDC",
                                    color="ff0000" if pnl_usdc < 0 else "ffff00"
                                )
                                # Record Trade
                                self.trade_recorder.add_trade({
                                    "symbol": self.active_symbol,
                                    "strategy": self.active_trade.get("strategy", "Unknown"),
                                    "side": "BUY",
                                    "entry_price": entry_price,
                                    "exit_price": current_price,
                                    "size": size,
                                    "leverage": leverage,
                                    "pnl_usdc": pnl_usdc,
                                    "pnl_percent": (pnl_per_coin / entry_price) * 100,
                                    "entry_time": self.active_trade.get("timestamp"),
                                    "exit_time": pd.Timestamp.now().isoformat(),
                                    "exit_reason": "SL"
                                })
                            except Exception as e:
                                print(f"Error recording trade: {e}")
                            
                            self.active_trade = None
                        elif current_price >= self.active_trade["tp"]:
                            self.add_log(f"✅ TP HIT @ {current_price}")
                            
                            # Execute Close
                            if self.execution_mode == "Auto (Hyperliquid)":
                                try:
                                    self.add_log(f"📈 CLOSING LONG {self.active_trade['symbol']} (TP)")
                                    hyperliquid_service.execute_order(
                                        self.active_trade['symbol'], 
                                        False, # SELL
                                        self.active_trade['size']
                                    )
                                except Exception as e:
                                    self.add_log(f"❌ Failed to execute TP close: {e}")

                            try:
                                # CORRECT PNL CALCULATION
                                size = self.active_trade.get("size", 0)
                                leverage = self.active_trade.get("leverage", 1)
                                pnl_per_coin = current_price - entry_price  # Long PnL
                                pnl_usdc = pnl_per_coin * size * leverage
                                
                                discord_service.send_alert(
                                    "✅ TAKE PROFIT HIT",
                                    f"Symbol: {self.active_symbol}\nPrice: {current_price}\nPnL: ${pnl_usdc:.2f} USDC",
                                    color="00ff00"
                                )
                                # Record Trade
                                self.trade_recorder.add_trade({
                                    "symbol": self.active_symbol,
                                    "strategy": self.active_trade.get("strategy", "Unknown"),
                                    "side": "BUY",
                                    "entry_price": entry_price,
                                    "exit_price": current_price,
                                    "size": size,
                                    "leverage": leverage,
                                    "pnl_usdc": pnl_usdc,
                                    "pnl_percent": (pnl_per_coin / entry_price) * 100,
                                    "entry_time": self.active_trade.get("timestamp"),
                                    "exit_time": pd.Timestamp.now().isoformat(),
                                    "exit_reason": "TP"
                                })
                            except Exception as e:
                                print(f"Error recording trade: {e}")
                            
                            self.active_trade = None
                    else:  # SELL
                        if current_price >= self.active_trade["sl"]:
                            self.add_log(f"🛑 SL HIT @ {current_price}")
                            
                            # Execute Close
                            if self.execution_mode == "Auto (Hyperliquid)":
                                try:
                                    self.add_log(f"📈 CLOSING SHORT {self.active_trade['symbol']} (SL)")
                                    hyperliquid_service.execute_order(
                                        self.active_trade['symbol'], 
                                        True, # BUY
                                        self.active_trade['size']
                                    )
                                except Exception as e:
                                    self.add_log(f"❌ Failed to execute SL close: {e}")

                            try:
                                # CORRECT PNL CALCULATION
                                size = self.active_trade.get("size", 0)
                                leverage = self.active_trade.get("leverage", 1)
                                pnl_per_coin = entry_price - current_price  # Short PnL
                                pnl_usdc = pnl_per_coin * size * leverage
                                
                                discord_service.send_alert(
                                    "🛑 STOP LOSS HIT",
                                    f"Symbol: {self.active_symbol}\nPrice: {current_price}\nPnL: ${pnl_usdc:.2f} USDC",
                                    color="ff0000" if pnl_usdc < 0 else "ffff00"
                                )
                                # Record Trade
                                self.trade_recorder.add_trade({
                                    "symbol": self.active_symbol,
                                    "strategy": self.active_trade.get("strategy", "Unknown"),
                                    "side": "SELL",
                                    "entry_price": entry_price,
                                    "exit_price": current_price,
                                    "size": size,
                                    "leverage": leverage,
                                    "pnl_usdc": pnl_usdc,
                                    "pnl_percent": (pnl_per_coin / entry_price) * 100,
                                    "entry_time": self.active_trade.get("timestamp"),
                                    "exit_time": pd.Timestamp.now().isoformat(),
                                    "exit_reason": "SL"
                                })
                            except Exception as e:
                                print(f"Error recording trade: {e}")
                                
                            self.active_trade = None
                        elif current_price <= self.active_trade["tp"]:
                            self.add_log(f"✅ TP HIT @ {current_price}")
                            
                            # Execute Close
                            if self.execution_mode == "Auto (Hyperliquid)":
                                try:
                                    self.add_log(f"📉 CLOSING SHORT {self.active_trade['symbol']} (TP)")
                                    hyperliquid_service.execute_order(
                                        self.active_trade['symbol'], 
                                        True, # BUY
                                        self.active_trade['size']
                                    )
                                except Exception as e:
                                    self.add_log(f"❌ Failed to execute TP close: {e}")

                            try:
                                # CORRECT PNL CALCULATION
                                size = self.active_trade.get("size", 0)
                                leverage = self.active_trade.get("leverage", 1)
                                pnl_per_coin = entry_price - current_price  # Short PnL
                                pnl_usdc = pnl_per_coin * size * leverage
                                
                                discord_service.send_alert(
                                    "✅ TAKE PROFIT HIT",
                                    f"Symbol: {self.active_symbol}\nPrice: {current_price}\nPnL: ${pnl_usdc:.2f} USDC",
                                    color="00ff00"
                                )
                                # Record Trade
                                self.trade_recorder.add_trade({
                                    "symbol": self.active_symbol,
                                    "strategy": self.active_trade.get("strategy", "Unknown"),
                                    "side": "SELL",
                                    "entry_price": entry_price,
                                    "exit_price": current_price,
                                    "size": size,
                                    "leverage": leverage,
                                    "pnl_usdc": pnl_usdc,
                                    "pnl_percent": (pnl_per_coin / entry_price) * 100,
                                    "entry_time": self.active_trade.get("timestamp"),
                                    "exit_time": pd.Timestamp.now().isoformat(),
                                    "exit_reason": "TP"
                                })
                            except Exception as e:
                                print(f"Error recording trade: {e}")
                                
                            self.active_trade = None
                
                time.sleep(30)  # Wait 30 seconds before next iteration (reduced API load)
                
            except Exception as e:
                self.add_log(f"❌ Error in trading loop: {e}")
                time.sleep(10)
        
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
            side = self.active_trade["side"]
            entry_price = self.active_trade["entry"]
            size = self.active_trade.get("size", 0)
            
            # Execute Market Close
            if self.execution_mode == "Auto (Hyperliquid)":
                try:
                    is_buy = side == "BUY"
                    # To close BUY, we SELL. To close SELL, we BUY.
                    # hyperliquid_service.execute_order takes is_buy boolean
                    # So if we are closing a BUY, is_buy for close order is False.
                    self.add_log(f"📉 CLOSING {side} {symbol} ({reason})")
                    hyperliquid_service.execute_order(
                        symbol, 
                        not is_buy, # Reverse side
                        size
                    )
                except Exception as e:
                    self.add_log(f"❌ Failed to execute close order: {e}")
                    # Force close locally anyway logic could go here if critical
            
            # Record Close locally
            current_price = 0
            try:
                # Try to get live price, fallback to entry if needed (shouldn't happen in loop)
                # But here we are outside loop context maybe? 
                # Ideally we fetch latest price.
                current_price = hyperliquid_service.get_current_price(symbol)
            except:
                current_price = entry_price # Fallback
                
            pnl = current_price - entry_price if side == "BUY" else entry_price - current_price
            
            self.add_log(f"✅ Trade Closed ({reason}). PnL: {pnl:.2f}")
            
            # Discord Alert
            try:
                discord_service.send_alert(
                    f"🛑 TRADE CLOSED ({reason})",
                    f"Symbol: {symbol}\nExit Price: {current_price}\nPnL: {pnl:.2f}",
                    color="ff0000" if pnl < 0 else "00ff00"
                )
            except: pass
            
            # Record outcome
            self.trade_recorder.add_trade({
                "symbol": symbol,
                "strategy": self.active_trade.get("strategy", "Unknown"),
                "side": side,
                "entry_price": entry_price,
                "exit_price": current_price,
                "pnl": pnl,
                "pnl_percent": (pnl / entry_price) * 100 if entry_price else 0,
                "entry_time": self.active_trade.get("timestamp"),
                "exit_time": pd.Timestamp.now().isoformat(),
                "exit_reason": reason
            })
            
            self.active_trade = None
            self.risk_manager.record_trade_close(pnl) # Decrement position count and update daily PnL
            StateManager.save_state(self)
            
            return True, "Trade closed successfully"
            
        except Exception as e:
            self.add_log(f"❌ Error closing trade: {e}")
            return False, str(e)

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
    
    # Start API server in background thread
    api_thread = threading.Thread(target=start_api_server, args=(bot,), daemon=True)
    api_thread.start()
    
    print("\n✅ Bot initialized")
    print("📊 Next.js UI: http://localhost:3000")
    print("🔧 API Docs: http://localhost:8001/docs")
    print("\n💡 The bot is ready. Use the Next.js UI to control it.")
    print("   Or use Streamlit as backup: streamlit run main.py")
    
    # Auto-start if bot was running before restart
    if bot.is_running:
        print("\n🔄 Auto-starting bot (was running before restart)...")
        bot.start()
    
    print("\nPress Ctrl+C to stop\n")
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Shutting down...")
        bot.stop()
        print("✅ Bot stopped. Goodbye!")

