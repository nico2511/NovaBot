
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
        self.scanner_settings = {
            "enabled": config.SCANNER_ENABLED,
            "interval": config.SCANNER_INTERVAL,
            "min_score": config.SCANNER_MIN_SCORE,
            "auto_switch": config.SCANNER_AUTO_SWITCH,
            "leverage": config.DEFAULT_LEVERAGE,
            "margin_type": "Cross"
        }
        self.scanner_job = None

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
                "default_margin_type": "Cross",
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
        
        # Discord signal detection anti-spam
        self._last_signal_discord = {"signature": None, "time": 0}
        
        # Open Interest History
        self.oi_history = deque(maxlen=2000) 
        
        # Data Persistence (Core)
        self.trade_recorder = TradeRecorder()
        
        # Phase 0 Hardening Services
        self.safe_order_manager = SafeOrderManager(hyperliquid_service)
        self.safe_order_manager.bot_context = self
        self.position_reconciler = PositionReconciler(hyperliquid_service, self.safe_order_manager)
        self.position_reconciler.bot_context = self
        

        self.signal_analysis_file = os.path.abspath(os.path.join(BASE_DIR, "data", "analysis", "signal_analysis.json"))
        self._ensure_data_dir()
        
        # Load persisted state
        try:
            state = StateManager.load_state(self)
            requested_max = self.global_settings.get("risk_defaults", {}).get("max_positions", 1)
            self.max_positions = requested_max
            self.add_log(f"⚙️ Max positions: {self.max_positions}")
        except Exception as e:
            print(f"Error loading state: {e}")

    def add_log(self, message: str, metadata: dict = None):
        """Add log message with optional metadata"""
        timestamp = pd.Timestamp.now().strftime('%H:%M:%S')
        structured_entry = {
            "timestamp": timestamp,
            "message": message,
            "metadata": metadata
        }
        self.logs.append(structured_entry)
        
        # Console output
        print(f"[BOT] {message}")
        if metadata and not message.startswith(("📊 Regime:", "🟡 Live", "⏸️ Next analysis")):
            print(f"   >>> Metadata: {metadata}")
            
        try:
            with open("bot_activity.log", "a", encoding="utf-8") as f:
                f.write(f"{timestamp} {message}\n")
        except Exception as e:
            print(f"⚠️ Log write error: {e}")

    def _notify_signal_detected_discord(self, sig: dict, technical_context: dict):
        """Send a Discord notification when a strategy signal is detected (pre-AI)."""
        try:
            symbol = sig.get("symbol", self.active_symbol)
            side = str(sig.get("signal", "UNKNOWN")).upper()
            strategy = sig.get("strategy", "unknown")
            price = float(sig.get("price", 0) or 0)
            sl = sig.get("sl")
            tp = sig.get("tp")
            sig_ts = str(sig.get("timestamp", "n/a"))

            signature = f"{symbol}|{strategy}|{side}|{sl}|{tp}|{sig_ts}"
            now_ts = time.time()
            if self._last_signal_discord.get("signature") == signature and (now_ts - self._last_signal_discord.get("time", 0)) < 300:
                return

            self._last_signal_discord = {"signature": signature, "time": now_ts}

            color = "00FF00" if side == "BUY" else "FF0000" if side == "SELL" else "FFD166"
            title = f"📡 SIGNAL DETECTED (Pre-AI): {side} {symbol}"
            description = (
                f"Strategy: {strategy}\n"
                f"Entry: {price:.8f}\n"
                f"SL/TP: {sl} / {tp}\n"
                f"Regime: {technical_context.get('regime')} | ADX: {technical_context.get('adx')}\n"
                f"RSI: {technical_context.get('rsi')} | Vol: {technical_context.get('volume_ratio')}%"
            )
            discord_service.send_alert(title, description, color=color)
        except Exception as e:
            self.add_log(f"⚠️ Discord notify error: {e}")

    def switch_active_symbol(self, new_symbol: str):
        if self.active_symbol == new_symbol: return
        self.add_log(f"🔄 Switching active symbol from {self.active_symbol} to {new_symbol}")
        self.active_symbol = new_symbol
        try:
            if hyperliquid_service.ws_manager:
                hyperliquid_service.ws_manager.add_symbol(new_symbol)
        except: pass
        StateManager.save_state(self)

    @property
    def active_trade(self):
        return self.active_trades.get(self.active_symbol)
    
    @active_trade.setter
    def active_trade(self, value):
        if value is None:
            self.active_trades.pop(self.active_symbol, None)
        else:
            self.active_trades[self.active_symbol] = value
    
    @property
    def latest_data(self):
        return self.latest_data_map.get(self.active_symbol, pd.DataFrame())
    
    @latest_data.setter
    def latest_data(self, value):
        self.latest_data_map[self.active_symbol] = value

    def _prepare_ai_context(self, position_data: dict = None) -> dict:
        if self.latest_data.empty: return {}
        df = self.latest_data
        current_price = float(df['close'].iloc[-1])
        
        ctx = {
            "symbol": self.active_symbol,
            "current_price": current_price,
            "rsi": float(df['RSI_14'].iloc[-1]) if 'RSI_14' in df.columns else 0,
            "funding_rate": hyperliquid_service.get_funding_rate(self.active_symbol),
            "open_interest": hyperliquid_service.get_open_interest(self.active_symbol)
        }
        return ctx

    def _ensure_data_dir(self):
        data_dir = os.path.dirname(self.signal_analysis_file)
        if not os.path.exists(data_dir): os.makedirs(data_dir)

    def _record_signal_analysis(self, sig: dict, ai_data: dict, approved: bool, indicators: dict = None):
        try:
            entry = {
                "timestamp": pd.Timestamp.now().isoformat(),
                "symbol": self.active_symbol,
                "direction": sig.get("signal"),
                "strategy": sig.get("strategy"),
                "approved": approved,
                "confidence": ai_data.get("confidence", 0),
                "reasoning": ai_data.get("reasoning", "N/A"),
                "indicators": indicators
            }
            history = []
            if os.path.exists(self.signal_analysis_file):
                try:
                    with open(self.signal_analysis_file, "r") as f: history = json.load(f)
                except: pass
            history.append(entry)
            with open(self.signal_analysis_file, "w") as f: json.dump(history[-500:], f, indent=2)
        except Exception as e: self.add_log(f"⚠️ Record analysis error: {e}")

    def execute_entry_atomically(self, symbol: str, side: str, size: float, price: float = None, sl: float = None, tp: float = None, strategy: str = "Unknown", metadata: dict = None, entry_indicators: dict = None):
        """ATOMIC ENTRY FLOW"""
        try:
            if not self.trading_enabled:
                self.add_log(f"⚠️ Signal ignored (Disabled): {side} {symbol}")
                return False
            
            real_positions = hyperliquid_service.get_positions()
            if real_positions is None: return False
            
            active_count = len([p for p in real_positions if float(p["size"]) > 0])
            if active_count >= self.max_positions:
                self.add_log(f"⛔ QUOTA EXCEEDED ({active_count}/{self.max_positions})")
                return False

            self.add_log(f"🔒 ATOMIC ENTRY START: {side} {symbol}")
            hyperliquid_service.cancel_all_orders(symbol)

            result = hyperliquid_service.execute_order(symbol, side == "BUY", size, price, sl, tp)
            if result.get("status") != "success":
                self.add_log(f"❌ Entry Failed: {result.get('message')}")
                return False

            for i in range(5):
                time.sleep(1)
                positions = hyperliquid_service.get_positions()
                pos = next((p for p in (positions or []) if p["symbol"] == symbol and float(p['size']) > 0), None)
                if pos:
                    entry_px = float(pos['entry_price'])
                    self.add_log(f"✅ ENTRY CONFIRMED: {symbol} @ {entry_px}")
                    with self.trade_lock:
                        if self.active_symbol != symbol: self.active_symbol = symbol
                        self.active_trade = {
                            "symbol": symbol, "side": side, "entry": entry_px,
                            "sl": sl, "tp": tp, "strategy": strategy,
                            "timestamp": pd.Timestamp.now().isoformat(),
                            "size": float(pos['size']), "leverage": float(pos.get("leverage", 1.0)),
                            "pnl": 0, "max_pnl": 0, "metadata": metadata or {},
                            "entry_indicators": entry_indicators or {}
                        }
                        StateManager.save_state(self)
                    discord_service.send_alert(f"🚀 ENTERED {side} {symbol}", f"Entry: {entry_px}\nSL/TP: {sl}/{tp}")
                    return True
            return False
        except Exception as e:
            self.add_log(f"❌ ATOMIC ENTRY ERROR: {e}")
            return False

    def execute_exit_atomically(self, symbol: str, reason: str = "SIGNAL"):
        """ATOMIC EXIT FLOW"""
        try:
            positions = hyperliquid_service.get_positions()
            if positions is None: return False
            
            pos_data = next((p for p in positions if p["symbol"] == symbol and float(p.get("size", 0)) > 0), None)
            if not pos_data:
                self.add_log(f"⚠️ Cannot close {symbol}: No position on exchange.")
                with self.trade_lock:
                    if symbol in self.active_trades: self.active_trades.pop(symbol, None)
                    StateManager.save_state(self)
                return False

            self.add_log(f"🔒 ATOMIC EXIT START: {symbol} ({reason})")
            result = hyperliquid_service.close_position(symbol)
            
            if result.get("status") == "success":
                self.add_log(f"✅ POSITION CLOSED: {symbol}")
                hyperliquid_service.cancel_all_orders(symbol)
                
                # Record trade
                with self.trade_lock:
                    trade = self.active_trades.get(symbol, {})
                    entry_px = float(trade.get("entry", pos_data.get("entry_price", 0)))
                    exit_px = hyperliquid_service.get_current_price(symbol)
                    size = float(pos_data.get("size", 0))
                    side = trade.get("side", pos_data.get("side", "BUY"))
                    pnl = (exit_px - entry_px) * size if side == "BUY" else (entry_px - exit_px) * size
                    
                    self.trade_recorder.add_trade({
                        "symbol": symbol, "strategy": trade.get("strategy", "Manual"),
                        "side": side, "entry_price": entry_px, "exit_price": exit_px,
                        "size": size, "pnl_usdc": pnl, "exit_reason": reason,
                        "exit_time": pd.Timestamp.now().isoformat()
                    })
                    if symbol in self.active_trades: self.active_trades.pop(symbol, None)
                    StateManager.save_state(self)
                    self._sync_state(silent=False)
                discord_service.send_alert(f"🏁 CLOSED {symbol}", f"Reason: {reason}\nPnL: ${pnl:.2f}")
                return True
            return False
        except Exception as e:
            self.add_log(f"❌ ATOMIC EXIT ERROR: {e}")
            return False

    def _check_hard_veto(self, signal: str, market_context: dict):
        rsi = market_context.get("rsi")
        if rsi:
            if signal == "BUY" and rsi > 80: return "RSI Overbought"
            if signal == "SELL" and rsi < 30: return "RSI Oversold"
        return None

    def _verify_and_enforce_sl_tp(self, symbol: str, trade_data: dict, bypass_cooldown: bool = False):
        if not self.trading_enabled: return
        if not bypass_cooldown and self._last_sltp_sync_time:
            if (pd.Timestamp.now() - self._last_sltp_sync_time).total_seconds() < self._sltp_sync_cooldown: return

        try:
            open_orders = hyperliquid_service.info.open_orders(config.HL_ACCOUNT_ADDRESS)
            symbol_orders = [o for o in open_orders if o["coin"] == symbol]
            sl_px = float(trade_data.get("sl", 0))
            tp_px = float(trade_data.get("tp", 0))
            
            found_sl = any(abs(float(o.get("triggerPx", 0)) - sl_px) / sl_px < 0.005 for o in symbol_orders if sl_px > 0)
            found_tp = any(abs(float(o.get("triggerPx", 0)) - tp_px) / tp_px < 0.005 for o in symbol_orders if tp_px > 0)
            
            if (sl_px > 0 and not found_sl) or (tp_px > 0 and not found_tp):
                self.add_log(f"⚠️ Audit: Syncing SL/TP for {symbol}")
                hyperliquid_service.sync_sl_tp(symbol, trade_data.get("side") == "BUY", float(trade_data.get("size", 0)), sl_px, tp_px)
                self._last_sltp_sync_time = pd.Timestamp.now()
        except Exception as e: self.add_log(f"⚠️ SL/TP Sync Error: {e}")

    def _update_trailing_stops(self, trade: dict, current_price: float) -> bool:
        entry = trade.get("entry"); side = trade.get("side"); sl = trade.get("sl"); tp = trade.get("tp")
        if not (entry and sl and tp): return False
        
        pnl_pct = ((current_price - entry) / entry) * 100 if side == "BUY" else ((entry - current_price) / entry) * 100
        new_sl = None
        if pnl_pct > 1.5: # Simple BE at 1.5% profit
            be_px = entry * 1.002 if side == "BUY" else entry * 0.998
            if (side == "BUY" and sl < be_px) or (side == "SELL" and (sl == 0 or sl > be_px)):
                new_sl = be_px
                self.add_log(f"🛡️ Trail: Moving {trade['symbol']} to BE")

        if new_sl:
            with self.trade_lock:
                if trade['symbol'] in self.active_trades:
                    self.active_trades[trade['symbol']]['sl'] = new_sl
                    StateManager.save_state(self)
            return True
        return False

    def _check_local_exits(self, trade: dict, symbol: str, current_price: float):
        side = trade.get("side"); sl = float(trade.get("sl") or 0); tp = float(trade.get("tp") or 0)
        if side == "BUY":
            if sl > 0 and current_price <= sl: self.execute_exit_atomically(symbol, "STOP_LOSS")
            elif tp > 0 and current_price >= tp: self.execute_exit_atomically(symbol, "TAKE_PROFIT")
        else:
            if sl > 0 and current_price >= sl: self.execute_exit_atomically(symbol, "STOP_LOSS")
            elif tp > 0 and current_price <= tp: self.execute_exit_atomically(symbol, "TAKE_PROFIT")

    def _manage_all_trades(self):
        trades = []
        with self.trade_lock: trades = list(self.active_trades.values())
        for trade in trades:
            symbol = trade.get("symbol")
            if not symbol: continue
            price = hyperliquid_service.get_current_price(symbol)
            if self._update_trailing_stops(trade, price):
                self._verify_and_enforce_sl_tp(symbol, trade, bypass_cooldown=True)
            self._check_local_exits(trade, symbol, price)

    def _sync_state(self, silent=True):
        """Unified State Synchronization (Stateless Truth)"""
        try:
            positions = hyperliquid_service.get_positions()
            if positions is None: return
            
            exchange_symbols = {p["symbol"]: p for p in positions if float(p.get("size", 0)) != 0}
            
            # 1. Adoption/Update
            for symbol, pos in exchange_symbols.items():
                if symbol not in self.active_trades:
                    if not silent: self.add_log(f"🕵️ SYNC: Orphan {symbol} detected. Adopting...")
                    self._adopt_existing_position(pos)
                else:
                    with self.trade_lock:
                        self.active_trades[symbol]["pnl"] = float(pos.get("pnl", 0))
                        self.active_trades[symbol]["size"] = float(pos.get("size", 0))
            
            # 2. Detect Closures
            for symbol in list(self.active_trades.keys()):
                if symbol not in exchange_symbols:
                    if not silent: self.add_log(f"🕵️ SYNC: {symbol} closed externally. Cleaning...")
                    self._handle_external_closure(symbol, self.active_trades[symbol])
        except Exception as e: self.add_log(f"⚠️ Sync Error: {e}")

    def _handle_external_closure(self, symbol: str, trade: dict):
        """Clean up trade closed on exchange"""
        try:
            self.add_log(f"🔄 Processing external closure for {symbol}")
            exit_px = hyperliquid_service.get_current_price(symbol)
            entry_px = float(trade.get("entry", 0))
            size = float(trade.get("size", 0))
            side = trade.get("side", "BUY")
            pnl = (exit_px - entry_px) * size if side == "BUY" else (entry_px - exit_px) * size
            
            self.trade_recorder.add_trade({
                "symbol": symbol, "strategy": trade.get("strategy", "Unknown"),
                "side": side, "entry_price": entry_px, "exit_price": exit_px,
                "size": size, "pnl_usdc": pnl, "exit_reason": "External Closure",
                "exit_time": pd.Timestamp.now().isoformat()
            })
        finally:
            with self.trade_lock:
                if symbol in self.active_trades: self.active_trades.pop(symbol, None)
                StateManager.save_state(self)

    def force_sync(self):
        self._sync_state(silent=False)
        return {"status": "success"}

    def _enforce_leverage(self):
        try:
            target = int(self.scanner_settings.get("leverage", 5))
            hyperliquid_service.update_leverage(self.active_symbol, target, True)
            self._leverage_synced = True
            self.add_log(f"⚙️ Leverage set to {target}x")
        except Exception as e: self.add_log(f"⚠️ Leverage error: {e}")

    def trading_loop(self):
        """Main trading loop"""
        self.add_log("🚀 Trading loop started")
        
        while self.is_running:
            try:
                # 1. State Sync & Reconcile
                if hasattr(self, 'position_reconciler'): self.position_reconciler.run_tick()
                
                self._loop_heartbeat = time.time()
                if (time.time() - self._last_state_sync_time) > self._state_sync_interval:
                    self._sync_state(silent=True)
                    self._last_state_sync_time = time.time()
                
                # 2. Leverage & Balance
                if self.trading_enabled and not self._leverage_synced: self._enforce_leverage()
                
                # 3. Manage Trades (SL/TP triggers)
                self._manage_all_trades()
                
                # 4. New Entry Analysis
                if len(self.active_trades) < self.max_positions:
                    df_15m = hyperliquid_service.get_candles(self.active_symbol, "15m", 200)
                    if not df_15m.empty:
                        self.latest_data = df_15m
                        result = self.strategy_engine.analyze(df_15m, {"symbol": self.active_symbol})
                        signals = result.get("signals", [])
                        if signals:
                            sig = signals[0]
                            if sig.get("signal"):
                                self.add_log(f"📡 Signal: {sig['signal']} for {self.active_symbol}")
                                self.execute_entry_atomically(
                                    self.active_symbol, sig['signal'], 20.0, 
                                    sig['price'], sig['sl'], sig['tp'], sig['strategy']
                                )

                time.sleep(10)
            except Exception as e:
                self.add_log(f"❌ Loop Error: {e}")
                time.sleep(5)

    def _adopt_existing_position(self, active_pos, sl=0, tp=0):
        symbol = active_pos['symbol']
        with self.trade_lock:
            self.active_trades[symbol] = {
                "symbol": symbol, "side": active_pos['side'],
                "entry": float(active_pos['entry_price']),
                "size": float(active_pos['size']),
                "leverage": float(active_pos.get('leverage', 1.0)),
                "oid": "external", "sl": sl, "tp": tp,
                "strategy": "Manual (Adopted)", "status": "OPEN"
            }
            StateManager.save_state(self)
        self.add_log(f"🕵️ ADOPTED {symbol}")

    def start(self):
        self.is_running = True
        self.thread = threading.Thread(target=self.trading_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.is_running = False
        if self.thread: self.thread.join(timeout=10)

    def close_active_trade(self, reason="Manual Close"):
        if not self.active_trade: return False, "No active trade"
        success = self.execute_exit_atomically(self.active_symbol, reason)
        return success, "Closed"
