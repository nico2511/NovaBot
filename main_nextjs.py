#!/usr/bin/env python3
"""
Main entry point for HyperLiquid Trading Bot with Next.js UI
Starts both the trading bot and the FastAPI server
"""
import sys
import os
import threading
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import config
from app.core.risk_manager import RiskManager
from app.core.state_manager import StateManager
from app.services.hyperliquid_service import hyperliquid_service
from app.services.discord_service import discord_service
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
        
        # Load persisted state
        try:
            StateManager.load_state(self)
            
            # Access settings loaded into sidebar_settings if available
            if hasattr(self, "sidebar_settings"):
                self.execution_mode = self.sidebar_settings.get("execution_mode", "Manual (Phantom)")
        except Exception as e:
            print(f"Error loading state: {e}")
            self.execution_mode = "Manual (Phantom)"
    
    def add_log(self, message: str):
        """Add log message"""
        timestamp = pd.Timestamp.now().strftime('%H:%M:%S')
        self.logs.append(f"{timestamp} {message}")
        print(f"[BOT] {message}")
    
    def trading_loop(self):
        """Main trading loop"""
        self.add_log("🚀 Trading loop started")
        self.add_log(f"⚙️ Loop initialized. is_running={self.is_running}")
        
        while self.is_running:
            self.add_log("🔄 Entering loop iteration...")
            try:
                self.add_log("📡 Fetching candles...")
                # Fetch candles
                df = hyperliquid_service.get_candles(self.active_symbol, interval="15m", limit=200)
                
                if df.empty:
                    self.add_log("⚠️ No data received")
                    time.sleep(10)
                    continue
                
                self.add_log(f"✅ Received {len(df)} candles")
                self.latest_data = df
                
                # Get current candle time
                current_candle_time = df.index[-1]
                
                # Only analyze on new candle
                if self.last_candle_time != current_candle_time:
                    self.last_candle_time = current_candle_time
                    
                    self.add_log(f"🔍 Analyzing new candle at {current_candle_time}")
                    # Analyze strategies
                    result = self.strategy_engine.analyze(df)
                    self.latest_strategy_result = result
                    
                    self.add_log(f"📊 Analysis complete: {result.get('regime', 'UNKNOWN')} regime, {len(result.get('signals', []))} signals")
                    
                    if result.get("signals"):
                        sig_data = result["signals"][0]
                        strat_name = sig_data.get("strategy", "Unknown")
                        action = sig_data.get("signal")
                        entry_price = sig_data.get("price")
                        sl = sig_data.get("sl", entry_price * 0.95)
                        tp = sig_data.get("tp", entry_price * 1.05)
                        
                        can_trade, reason = self.risk_manager.check_can_trade()
                        if can_trade:
                            # Open trade
                            self.active_trade = {
                                "symbol": self.active_symbol,
                                "side": action,
                                "entry": entry_price,
                                "sl": sl,
                                "tp": tp,
                                "strategy": strat_name,
                                "timestamp": pd.Timestamp.now().isoformat()
                            }
                            self.risk_manager.record_trade_open()
                            
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
                            


                            # Send Discord notification
                            try:
                                discord_service.send_trade_signal(
                                    self.active_symbol, 
                                    action, 
                                    entry_price, 
                                    f"Strategy: {strat_name}\nSL: {sl}\nTP: {tp}"
                                )
                            except Exception as e:
                                print(f"Failed to send Discord signal: {e}")
                            
                            # Save state
                            StateManager.save_state(self)
                
                # Check active trade
                if self.active_trade:
                    current_price = df['close'].iloc[-1]
                    entry_price = self.active_trade["entry"]
                    tp_price = self.active_trade["tp"]
                    sl_price = self.active_trade["sl"]
                    side = self.active_trade["side"]
                    
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
                            try:
                                pnl = current_price - entry_price
                                discord_service.send_alert(
                                    "🛑 STOP LOSS HIT",
                                    f"Symbol: {self.active_symbol}\nPrice: {current_price}\nPnL: {pnl:.2f}",
                                    color="ff0000" if pnl < 0 else "ffff00" # Red if loss, Yellow if BE/Profit
                                )
                            except: pass
                            self.active_trade = None
                        elif current_price >= self.active_trade["tp"]:
                            self.add_log(f"✅ TP HIT @ {current_price}")
                            try:
                                discord_service.send_alert(
                                    "✅ TAKE PROFIT HIT",
                                    f"Symbol: {self.active_symbol}\nPrice: {current_price}\nPnL: {current_price - entry_price:.2f}",
                                    color="00ff00"
                                )
                            except: pass
                            self.active_trade = None
                    else:  # SELL
                        if current_price >= self.active_trade["sl"]:
                            self.add_log(f"🛑 SL HIT @ {current_price}")
                            try:
                                pnl = entry_price - current_price
                                discord_service.send_alert(
                                    "🛑 STOP LOSS HIT",
                                    f"Symbol: {self.active_symbol}\nPrice: {current_price}\nPnL: {pnl:.2f}",
                                    color="ff0000" if pnl < 0 else "ffff00"
                                )
                            except: pass
                            self.active_trade = None
                        elif current_price <= self.active_trade["tp"]:
                            self.add_log(f"✅ TP HIT @ {current_price}")
                            try:
                                discord_service.send_alert(
                                    "✅ TAKE PROFIT HIT",
                                    f"Symbol: {self.active_symbol}\nPrice: {current_price}\nPnL: {entry_price - current_price:.2f}",
                                    color="00ff00"
                                )
                            except: pass
                            self.active_trade = None
                
                time.sleep(5)  # Wait 5 seconds
                
            except Exception as e:
                self.add_log(f"❌ Error in trading loop: {e}")
                time.sleep(10)
        
        self.add_log("⏸️ Trading loop stopped")
    
    def start(self):
        """Start the bot"""
        if not self.is_running:
            self.is_running = True
            self.thread = threading.Thread(target=self.trading_loop, daemon=True)
            self.thread.start()
            self.add_log("✅ Bot started")
            StateManager.save_state(self)
    
    def stop(self):
        """Stop the bot"""
        if self.is_running:
            self.is_running = False
            if self.thread:
                self.thread.join(timeout=5)
            self.add_log("⏹️ Bot stopped")
            StateManager.save_state(self)


def start_api_server(bot_context):
    """Start FastAPI server in a separate thread"""
    import uvicorn
    from backend.api import app
    
    # Connect bot to API via bridge
    bot_bridge.set_bot_context(bot_context)
    
    print("🚀 Starting FastAPI server on http://localhost:8001")
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")


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
    print("\nPress Ctrl+C to stop\n")
    
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Shutting down...")
        bot.stop()
        print("✅ Bot stopped. Goodbye!")
