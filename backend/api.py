"""
FastAPI Backend for HyperLiquid Trading Bot
Exposes REST API and integrates with main bot
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import asyncio
import json
from datetime import datetime
import os
import numpy as np
import pandas as pd

# Import routes (optional - will be added later)
# Import routes (optional)
try:
    # from backend.routes.settings import router as settings_router # CONFLICT: Removing legacy settings router
    from backend.routes.scanner import router as scanner_router
    ROUTES_AVAILABLE = True
except ImportError:
    print("⚠️ Routes not available - running in basic mode")
    ROUTES_AVAILABLE = False

# When running from backend/, we need to go up one level
BASE_DIR = os.path.dirname(os.getcwd()) if os.path.basename(os.getcwd()) == "backend" else os.getcwd()

# Import bot bridge for integration with main bot
try:
    from backend.bot_bridge import bot_bridge
    print("✅ Bot bridge imported successfully")
except ImportError:
    print("⚠️ Bot bridge not available - running in standalone mode")
    bot_bridge = None

app = FastAPI(title="HyperLiquid Trading Bot API", version="2.0")

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers if available
if ROUTES_AVAILABLE:
    app.include_router(scanner_router, prefix="/api", tags=["scanner"])
    # app.include_router(settings_router, prefix="/api", tags=["settings"]) # CONFLICT: Using main API logic instead
    print("✅ Scanner and Settings routes registered")


# Simple bot state
class BotState:
    def __init__(self):
        self.is_running = False
        self.trading_enabled = False
        self.active_symbol = "BTC"
        self.execution_mode = "Manual (Phantom)"
        self.active_trade = None
        self.signals_log = []
        self.logs = []
        self.load_state()
    
    def add_log(self, message):
        """Add a log message with timestamp"""
        time_str = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"{time_str} {message}")
        # Keep last 100
        if len(self.logs) > 100:
            self.logs.pop(0)

    def load_state(self):
        """Load state from bot_state.json"""
        try:
            state_file = os.path.join(BASE_DIR, "bot_state.json")
            with open(state_file, "r") as f:
                state = json.load(f)
                self.is_running = state.get("is_running", False)
                self.trading_enabled = state.get("trading_enabled", False)
                self.active_symbol = state.get("active_symbol", "BTC")
                sidebar = state.get("sidebar_settings", {})
                self.execution_mode = sidebar.get("execution_mode", "Manual (Phantom)")
        except Exception as e:
            print(f"Error loading state: {e}")

    def save_state(self):
        """Save state to bot_state.json"""
        try:
            state_file = os.path.join(BASE_DIR, "bot_state.json")
            # Load existing to preserve other fields
            try:
                with open(state_file, "r") as f:
                    state = json.load(f)
            except:
                state = {}
            
            state["is_running"] = self.is_running
            state["trading_enabled"] = self.trading_enabled
            state["active_symbol"] = self.active_symbol
            state["execution_mode"] = self.execution_mode
            
            # Ensure sidebar settings match
            if "sidebar_settings" not in state:
                state["sidebar_settings"] = {}
            # Note: trading_enabled is now ONLY in global state, not duplicated in sidebar_settings
            state["sidebar_settings"]["execution_mode"] = self.execution_mode
            
            with open(state_file, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            print(f"Error saving state: {e}")

bot_state = BotState()

# Pydantic models
class BotStatus(BaseModel):
    is_running: bool
    trading_enabled: bool
    active_symbol: str
    execution_mode: str
    active_trade: Optional[Dict[str, Any]]

# REST API Endpoints

@app.get("/")
async def root():
    return {"message": "HyperLiquid Trading Bot API", "version": "2.0"}

@app.get("/api/status", response_model=BotStatus)
async def get_status():
    """Get current bot status"""
    # Try to get from connected bot first
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        return BotStatus(
            is_running=bot.is_running,
            trading_enabled=bot.trading_enabled,
            active_symbol=bot.active_symbol,
            execution_mode=bot.execution_mode,
            active_trade=bot.active_trade
        )
    
    # Fallback to bot_state
    return BotStatus(
        is_running=bot_state.is_running,
        trading_enabled=bot_state.trading_enabled,
        active_symbol=bot_state.active_symbol,
        execution_mode=bot_state.execution_mode,
        active_trade=bot_state.active_trade
    )


@app.post("/api/engine/start")
async def start_engine():
    """Start the trading engine"""
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        bot.start()
        # Bot saves state internally usually, but we force sync if needed
        return {"status": "started", "message": "Real bot started"}
    else:
        bot_state.is_running = True
        bot_state.add_log(f"🚀 Bot started on {bot_state.active_symbol}")
        bot_state.save_state()
        return {"status": "started", "message": "Standalone mode - bot_state updated"}

@app.post("/api/engine/stop")
async def stop_engine():
    """Stop the trading engine"""
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        bot.stop()
        return {"status": "stopped", "message": "Real bot stopped"}
    else:
        bot_state.is_running = False
        bot_state.add_log("🛑 Bot stopped")
        bot_state.save_state()
        return {"status": "stopped", "message": "Standalone mode - bot_state updated"}


@app.post("/api/trading/enable")
async def enable_trading():
    """Enable live trading"""
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        bot.trading_enabled = True
        bot.execution_mode = "Auto (Hyperliquid)"
        bot.add_log("🟢 Live trading ENABLED via API")
        # CRITICAL: Save state to persist the change
        try:
            from app.core.state_manager import StateManager
            StateManager.save_state(bot)
        except Exception as e:
            print(f"Error saving state: {e}")
        return {"status": "enabled", "message": "Live trading enabled on real bot"}
    else:
        # Single source of truth: only global trading_enabled
        bot_state.trading_enabled = True
        bot_state.execution_mode = "Auto (Hyperliquid)"
        bot_state.add_log("🟢 Live trading ENABLED")
        bot_state.save_state()
        return {"status": "enabled", "message": "Standalone mode - bot_state updated"}

@app.post("/api/trading/disable")
async def disable_trading():
    """Disable live trading"""
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        bot.trading_enabled = False
        bot.add_log("🔴 Live trading DISABLED via API")
        # CRITICAL: Save state to persist the change
        try:
            from app.core.state_manager import StateManager
            StateManager.save_state(bot)
        except Exception as e:
            print(f"Error saving state: {e}")
        return {"status": "disabled", "message": "Live trading disabled on real bot"}
    else:
        # Single source of truth: only global trading_enabled
        bot_state.trading_enabled = False
        bot_state.add_log("🔴 Live trading DISABLED")
        bot_state.save_state()
        return {"status": "disabled", "message": "Standalone mode - bot_state updated"}

@app.get("/api/candles")
async def get_candles(limit: int = 200, strategy: Optional[str] = None, symbol: Optional[str] = None):
    """Get formatted candles for chart, optionally with strategy indicators"""
    try:
        try:
            from backend.market_data import get_hyperliquid_candles
        except ImportError:
            from market_data import get_hyperliquid_candles
            
        # Use provided symbol or fallback to active
        target_symbol = symbol if symbol else bot_state.active_symbol

        # 1. Fetch raw candles
        df = await get_hyperliquid_candles(target_symbol, "15m", limit)
        if df is None:
            return {"candles": []}
        
        # 2. Add default indicators (BB, EMA) for chart visualization
        try:
            # Bollinger Bands (20, 2)
            df['mean'] = df['close'].rolling(window=20).mean()
            df['std'] = df['close'].rolling(window=20).std()
            df['BBU_20_2.0'] = df['mean'] + (df['std'] * 2)
            df['BBM_20_2.0'] = df['mean']
            df['BBL_20_2.0'] = df['mean'] - (df['std'] * 2)
            
            # EMAs
            df['EMA_20'] = df['close'].ewm(span=20, adjust=False).mean()
            df['EMA_50'] = df['close'].ewm(span=50, adjust=False).mean()
            
            # Drop temp columns
            df.drop(columns=['mean', 'std'], inplace=True, errors='ignore')
        except Exception as e:
            print(f"Error adding default indicators: {e}")

        # 3. Add strategy indicators if provided (might overwrite/augment)
        if strategy:
            try:
                # Dynamic import to avoid circular dependency
                # Assuming strategies are in strategies/definitions.py
                import sys
                
                # Check where we are running from
                if os.path.basename(os.getcwd()) == "backend":
                    # If running from backend dir, we need to add parent to sys.path
                     sys.path.append(os.path.dirname(os.getcwd()))

                from strategies.definitions import (
                    ScalpEmaRsi, InstitutionalScalp, SwingTrendPullback, 
                    MeanReversion, SMCFVG, TestTriggerStrategy
                )
                
                # Config loading...
                config_file = os.path.join(BASE_DIR, "strategies.json")
                strat_config = {}
                try:
                    with open(config_file, "r") as f:
                        full_config = json.load(f)
                        strat_config = full_config.get("strategies", {}).get(strategy, {})
                except:
                    pass

                # Instantiate strategy
                strat_instance = None
                if strategy == "ScalpEmaRsi":
                    strat_instance = ScalpEmaRsi(strat_config)
                elif strategy == "InstitutionalScalp":
                    strat_instance = InstitutionalScalp(strat_config)
                elif strategy == "SwingTrendPullback":
                    strat_instance = SwingTrendPullback(strat_config)
                elif strategy == "MeanReversion":
                    strat_instance = MeanReversion(strat_config)
                elif strategy == "SMCFVG":
                    strat_instance = SMCFVG(strat_config)
                elif strategy == "TestTriggerStrategy":
                    strat_instance = TestTriggerStrategy(strat_config)
                
                if strat_instance:
                    strat_instance.add_indicators(df)
            except Exception as e:
                print(f"Error adding indicators for {strategy}: {e}")

        # 3. Format for frontend
        candles = []
        for index, row in df.iterrows():
            ts = int(index.timestamp())
            
            # Base candle
            c = {
                "time": ts,
                "open": float(row['open']),
                "high": float(row['high']),
                "low": float(row['low']),
                "close": float(row['close']),
            }
            
            # Add all other columns as indicators (skip ohlc volume)
            for col in df.columns:
                if col not in ['open', 'high', 'low', 'close', 'volume', 'time']:
                     # Check if it's numeric/float before adding
                     val = row[col]
                     if isinstance(val, (int, float, np.number)):
                         if not np.isnan(val):
                             c[col] = float(val)
            
            candles.append(c)
            
        return {"candles": candles}
    except Exception as e:
        print(f"Error serving candles: {e}")
        import traceback
        traceback.print_exc()
        return {"candles": []}

@app.get("/api/market/data")
async def get_market_data():
    """Get current market data from HyperLiquid with real indicators"""
    try:
        # CRITICAL FIX: Use bot_bridge to get active_symbol from real bot
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            active_symbol = bot.active_symbol
        else:
            active_symbol = bot_state.active_symbol
        
        try:
            from backend.market_data import get_hyperliquid_candles, get_current_price, calculate_rsi, calculate_atr, calculate_adx, calculate_ema, calculate_bb
        except ImportError:
            from market_data import get_hyperliquid_candles, get_current_price, calculate_rsi, calculate_atr, calculate_adx, calculate_ema, calculate_bb
        
        # Get candles for indicator calculation using ACTIVE symbol
        df = await get_hyperliquid_candles(active_symbol, "15m", 100)
        
        if df is not None and len(df) > 0:
            # Get current price from latest candle
            price = float(df['close'].iloc[-1])
            
            # Calculate real indicators
            rsi = await calculate_rsi(df['close'], 14)
            atr = await calculate_atr(df, 14)
            adx = await calculate_adx(df, 14)
            ema_20 = await calculate_ema(df['close'], 20)
            ema_50 = await calculate_ema(df['close'], 50)
            bb = await calculate_bb(df['close'], 20, 2)
        else:
            # Fallback to just price if candles fail
            price = await get_current_price(active_symbol)
            rsi = 50.0
            atr = price * 0.001
            adx = 50.0
            ema_20 = price
            ema_50 = price
            bb = {"upper": price, "middle": price, "lower": price}
            
    except Exception as e:
        print(f"Error in get_market_data: {e}")
        # Fallback values
        price = 87000.0
        rsi = 50.0
        atr = 870.0
        adx = 50.0
        ema_20 = price
        ema_50 = price
        bb = {"upper": price, "middle": price, "lower": price}
        active_symbol = "BTC"  # Fallback symbol
    
    # Get active strategies and their progress from bot if connected
    active_strategies = []
    strategy_progress = {}
    try:
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            # Get strategies from latest analysis result
            if hasattr(bot, 'latest_strategy_result') and bot.latest_strategy_result:
                result = bot.latest_strategy_result
                # Get the list of active strategy names (these are already filtered by regime)
                strategy_names = result.get('strategies', [])
                progress_data = result.get('progress', {})
                
                # Format for frontend
                for name in strategy_names:
                    active_strategies.append(name)
                    strategy_progress[name] = progress_data.get(name, 0)
        
        # If bot not connected or no analysis yet, return empty list
        if not active_strategies:
            active_strategies = []
            strategy_progress = {}
    except Exception as e:
        print(f"Error getting active strategies: {e}")
        active_strategies = []
        strategy_progress = {}
    
    regime = "TREND" if adx > 25 else "RANGE"
    
    return {
        "symbol": active_symbol,  # CRITICAL: Return the ACTIVE symbol from bot
        "price": float(price),
        "timestamp": datetime.now().isoformat(),
        "regime": regime,
        "adx": float(adx),
        "rsi": float(rsi),
        "atr": float(atr),
        "ema_20": float(ema_20),
        "ema_50": float(ema_50),
        "bb": bb,
        "active_strategies": active_strategies,
        "strategy_progress": strategy_progress,
        "signals": []
    }

@app.get("/api/strategies")
async def get_strategies():
    """Get all strategies and their status"""
    try:
        config_file = os.path.join(BASE_DIR, "strategies.json")
        with open(config_file, "r") as f:
            config = json.load(f)
        
        strategies = []
        for name, strat in config.get("strategies", {}).items():
            strategies.append({
                "name": name,
                "enabled": strat.get("enabled", False),
                "type": strat.get("type", "unknown"),
                "params": strat.get("params", {})
            })
        
        return {"strategies": strategies}
    except Exception as e:
        print(f"Error loading strategies.json: {e}")
        return {"strategies": []}

@app.get("/api/balance")
async def get_balance():
    """Get account balance from Hyperliquid"""
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        
        balance_data = hyperliquid_service.get_account_balance()
        
        if balance_data.get("status") == "success":
            return {
                "total_equity": balance_data.get("equity", 0.0),
                "available": balance_data.get("available", 0.0),
                "margin": balance_data.get("margin_used", 0.0)
            }
            
        # Fallback if status error
        return {
            "total_equity": 0.0,
            "available": 0.0,
            "margin": 0.0
        }
    except Exception as e:
        print(f"Error getting balance: {e}")
        return {
            "total_equity": 0.0,
            "available": 0.0,
            "margin": 0.0
        }

@app.get("/api/signals")
async def get_signals():
    """Get recent signals"""
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        # Convert deque to list and format
        signals = []
        for sig in list(bot.signals_log)[-50:]:
            signals.append({
                "timestamp": sig.get("time", "").isoformat() if hasattr(sig.get("time", ""), "isoformat") else str(sig.get("time", "")),
                "strategy": sig.get("strategy", "Unknown"),
                "side": sig.get("type", "BUY"),
                "price": sig.get("price", 0),
                "symbol": sig.get("symbol", "BTC")
            })
        return {"signals": signals}
    return {"signals": bot_state.signals_log[-50:]}

@app.get("/api/logs")
async def get_logs():
    """Get recent logs"""
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        # Convert deque to list and format
        logs = []
        for log in list(bot.logs)[-50:]:
            # Parse log format: "HH:MM:SS message"
            parts = log.split(" ", 1)
            if len(parts) == 2:
                logs.append({"time": parts[0], "message": parts[1]})
            else:
                logs.append({"time": "", "message": log})
        return {"logs": logs}
    
    # Return standalone logs
    logs = []
    for log in list(bot_state.logs)[-50:]:
        parts = log.split(" ", 1)
        if len(parts) == 2:
            logs.append({"time": parts[0], "message": parts[1]})
        else:
            logs.append({"time": "", "message": log})
    
    # If empty, show welcome message
    if not logs:
        return {
            "logs": [
                {"time": datetime.now().strftime("%H:%M:%S"), "message": "🤖 Standalone mode ready"}
            ]
        }
    
    return {"logs": logs}

@app.get("/api/active_trade")
async def get_active_trade():
    """Get current active trade"""
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        return {"active_trade": bot.active_trade}
    return {"active_trade": bot_state.active_trade}

@app.post("/api/close_trade")
async def close_trade():
    """Close active trade - WITH REAL EXECUTION AND CORRECT PNL"""
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        if bot.active_trade:
            symbol = bot.active_trade["symbol"]
            side = bot.active_trade["side"]
            entry_price = bot.active_trade["entry"]
            size = bot.active_trade.get("size", 0)
            leverage = bot.active_trade.get("leverage", 1)
            
            # EXÉCUTION RÉELLE si mode Auto
            if bot.execution_mode == "Auto (Hyperliquid)":
                try:
                    from app.services.hyperliquid_service import hyperliquid_service
                    
                    bot.add_log(f"🔴 MANUAL CLOSE: Closing {symbol}")
                    
                    # Utiliser la nouvelle méthode close_position
                    result = hyperliquid_service.close_position(symbol)
                    
                    if result["status"] == "success":
                        bot.add_log(f"✅ Position closed: {result}")
                        
                        # Calculer PNL correct
                        current_price = hyperliquid_service.get_current_price(symbol)
                        
                        # CORRECT PNL CALCULATION
                        pnl_per_coin = (current_price - entry_price) if side == "BUY" else (entry_price - current_price)
                        pnl_usdc = pnl_per_coin * size * leverage
                        
                        bot.add_log(f"💰 PNL: ${pnl_usdc:.2f} USDC")
                        
                        # Enregistrer le trade
                        bot.trade_recorder.add_trade({
                            "symbol": symbol,
                            "strategy": bot.active_trade.get("strategy", "Unknown"),
                            "side": side,
                            "entry_price": entry_price,
                            "exit_price": current_price,
                            "size": size,
                            "leverage": leverage,
                            "pnl_usdc": pnl_usdc,
                            "pnl_percent": (pnl_per_coin / entry_price) * 100,
                            "entry_time": bot.active_trade.get("timestamp"),
                            "exit_time": pd.Timestamp.now().isoformat(),
                            "exit_reason": "Manual Close"
                        })
                        
                        # Discord notification
                        try:
                            from app.services.discord_service import discord_service
                            discord_service.send_alert(
                                "🔴 MANUAL CLOSE",
                                f"Position {symbol} closed manually\\nPNL: ${pnl_usdc:.2f} USDC\\nEntry: ${entry_price}\\nExit: ${current_price}",
                                color="0000FF"
                            )
                        except Exception as e:
                            bot.add_log(f"⚠️ Discord notification failed: {e}")
                    else:
                        bot.add_log(f"❌ Close failed: {result.get('message')}")
                        return {"status": "error", "message": result.get("message")}
                        
                except Exception as e:
                    bot.add_log(f"❌ Error closing position: {e}")
                    return {"status": "error", "message": str(e)}
            
            # Nettoyer le bot state
            bot.active_trade = None
            bot.risk_manager.record_trade_close(pnl_usdc if 'pnl_usdc' in locals() else 0)
            
            # Sauvegarder
            try:
                from app.core.state_manager import StateManager
                StateManager.save_state(bot)
            except Exception as e:
                print(f"Error saving state: {e}")
            
            return {"status": "closed", "message": "Trade closed successfully"}
        return {"status": "no_active_trade"}
    
    # Standalone mode
    if bot_state.active_trade:
        bot_state.active_trade = None
        return {"status": "closed", "message": "Standalone mode - trade closed"}
    return {"status": "no_active_trade"}

@app.get("/api/trades")
async def get_trades():
    """Get trade history"""
    try:
        from app.core.trade_recorder import TradeRecorder
        recorder = TradeRecorder()
        return {"trades": recorder.load_trades()}
    except Exception as e:
        print(f"Error loading trades: {e}")
        return {"trades": []}

@app.get("/api/trades/hyperliquid")
async def get_hyperliquid_trades(limit: int = 100):
    """Get trade history from Hyperliquid API"""
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        
        trades = hyperliquid_service.get_trade_history(limit)
        
        return {
            "status": "success",
            "trades": trades,
            "source": "hyperliquid_api",
            "count": len(trades)
        }
    except Exception as e:
        print(f"Error in /api/trades/hyperliquid: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
            "trades": []
        }

@app.get("/api/stats")
async def get_stats():
    """Get trade statistics"""
    try:
        from app.core.trade_recorder import TradeRecorder
        recorder = TradeRecorder()
        return {"stats": recorder.get_stats()}
    except Exception as e:
        print(f"Error loading stats: {e}")
        return {"stats": {}}

@app.post("/api/execute_manual_trade")
async def execute_manual_trade(request: dict):
    """Execute a manually validated trade signal"""
    try:
        symbol = request.get("symbol")
        action = request.get("action")  # "BUY" or "SELL"
        price = request.get("price")
        sl = request.get("sl")
        tp = request.get("tp")
        strategy = request.get("strategy", "Manual")
        
        if not all([symbol, action, price, sl, tp]):
            return {"status": "error", "message": "Missing required parameters"}
        
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            
            # Vérifier qu'il n'y a pas déjà un trade actif
            if bot.active_trade:
                return {"status": "error", "message": "A trade is already active"}
            
            # Vérifier les limites de risque
            can_trade, reason = bot.risk_manager.check_can_trade()
            if not can_trade:
                return {"status": "error", "message": reason}
            
            # Exécuter le trade si mode Auto
            if bot.execution_mode == "Auto (Hyperliquid)":
                try:
                    from app.services.hyperliquid_service import hyperliquid_service
                    
                    is_buy = (action == "BUY")
                    size = bot.trade_size  # Utiliser la taille configurée
                    
                    bot.add_log(f"📊 MANUAL TRADE: {action} {symbol} @ {price}")
                    
                    # Exécuter l'ordre
                    result = hyperliquid_service.execute_order(
                        symbol=symbol,
                        is_buy=is_buy,
                        quantity=size
                    )
                    
                    bot.add_log(f"✅ Order executed: {result}")
                    
                    # Enregistrer le trade actif
                    bot.active_trade = {
                        "symbol": symbol,
                        "side": action,
                        "entry": price,
                        "sl": sl,
                        "tp": tp,
                        "size": size,
                        "leverage": bot.leverage,
                        "strategy": strategy,
                        "timestamp": pd.Timestamp.now().isoformat()
                    }
                    
                    bot.risk_manager.record_trade_open()
                    
                    # Notification Discord
                    try:
                        from app.services.discord_service import discord_service
                        rr = abs(tp - price) / abs(price - sl)
                        discord_service.send_alert(
                            f"📊 MANUAL TRADE: {action}",
                            f"Symbol: {symbol}\nEntry: ${price}\nSL: ${sl}\nTP: ${tp}\nR:R: 1:{rr:.2f}\nStrategy: {strategy}",
                            color="0000FF"
                        )
                    except: pass
                    
                    # Sauvegarder
                    from app.core.state_manager import StateManager
                    StateManager.save_state(bot)
                    
                    return {"status": "success", "message": "Trade executed successfully"}
                    
                except Exception as e:
                    bot.add_log(f"❌ Failed to execute manual trade: {e}")
                    return {"status": "error", "message": str(e)}
            else:
                # Mode Phantom
                bot.active_trade = {
                    "symbol": symbol,
                    "side": action,
                    "entry": price,
                    "sl": sl,
                    "tp": tp,
                    "size": bot.trade_size,
                    "leverage": bot.leverage,
                    "strategy": strategy,
                    "timestamp": pd.Timestamp.now().isoformat()
                }
                
                bot.risk_manager.record_trade_open()
                
                from app.core.state_manager import StateManager
                StateManager.save_state(bot)
                
                return {"status": "success", "message": "Phantom trade recorded"}
        
        return {"status": "error", "message": "Bot not connected"}
        
    except Exception as e:
        print(f"Error executing manual trade: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/gamification_status")
async def get_gamification_status():
    """Get gamification status based on account balance"""
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        from app.core.asset_gamification import AssetGamification
        
        # Récupérer le solde du compte (retourne un float directement)
        balance_usdc = hyperliquid_service.get_account_value()
        
        # Créer l'instance de gamification
        gam = AssetGamification(balance_usdc)
        status = gam.get_status_summary()
        
        return {
            "status": "success",
            "gamification": status
        }
        
    except Exception as e:
        print(f"Error getting gamification status: {e}")
        return {
            "status": "error",
            "message": str(e),
            "gamification": {
                "level": "Goblin",
                "balance": 0,
                "allowed_tiers": ["Casino"],
                "allowed_assets_count": 0,
                "max_leverage": 3,
                "max_position_size": 50,
                "description": "Erreur de connexion",
                "recommendation": "Vérifiez votre connexion Hyperliquid",
                "progress": {
                    "current_level": "Goblin",
                    "next_level": "Mercenary",
                    "current_balance": 0,
                    "required_balance": 100,
                    "progress_percent": 0,
                    "remaining": 100
                },
                "recommendations": []
            }
        }






@app.post("/api/ai_analysis")
async def get_ai_analysis(data: dict = {}):
    """Get AI analysis for a symbol"""
    symbol = data.get("symbol", bot_state.active_symbol)
    
    try:
        from app.services.gemini_service import gemini_service
        
        # 1. Gather Market Data
        try:
            from backend.market_data import get_hyperliquid_candles, calculate_rsi, calculate_atr, calculate_adx, calculate_ema
        except ImportError:
            from market_data import get_hyperliquid_candles, calculate_rsi, calculate_atr, calculate_adx, calculate_ema
    
        df = await get_hyperliquid_candles(symbol, "15m", 100)
        
        if df is None or df.empty:
            return {"error": "No market data available"}
            
        current_price = float(df['close'].iloc[-1])
        rsi = await calculate_rsi(df['close'])
        adx = await calculate_adx(df)
        atr = await calculate_atr(df)
        ema_20 = await calculate_ema(df['close'], 20)
        ema_50 = await calculate_ema(df['close'], 50)
        
        # Trend
        trend = "BULLISH" if ema_20 > ema_50 else "BEARISH"
        
        # Prepare data packet for AI
        market_summary = {
            "symbol": symbol,
            "price": current_price,
            "rsi": rsi,
            "adx": adx,
            "atr": atr,
            "trend_technical": trend,
            "volatility": "HIGH" if adx > 25 else "LOW"
        }
        
        # 2. Call Gemini
        analysis = gemini_service.analyze_market(market_summary)
        return analysis

    except ImportError:
         return {"error": "Gemini Service not found"}
    except Exception as e:
        print(f"Error in AI analysis: {e}")
        return {"error": str(e)}

@app.get("/api/settings")
async def get_settings():
    """Get money management settings"""
    try:
        # 1. Try to get from live bot context first (Source of Truth)
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            if hasattr(bot, 'sidebar_settings'):
                # Ensure defaults if keys missing
                s = bot.sidebar_settings
                sc = getattr(bot, 'scanner_settings', {})
                return {
                    "asset": s.get("asset", "BTC"),
                    "execution_mode": s.get("execution_mode", "Manual (Phantom)"),
                    "trading_enabled": s.get("trading_enabled", False),
                    "size_type": s.get("size_type", "Fixed (USDC)"),
                    "size_value": s.get("size_value", 100.0),
                    "leverage": s.get("leverage", 5),
                    "max_positions": s.get("max_positions", 3),
                    "daily_stop_loss": s.get("daily_stop_loss", 100.0),
                    "scanner": {
                        "enabled": sc.get("enabled", False),
                        "interval": sc.get("interval", 15),
                        "min_score": sc.get("min_score", 75),
                        "auto_switch": sc.get("auto_switch", False)
                    }
                }
            # If bot exists but no sidebar_settings yet, allow fallthrough to file
            
        state_file = os.path.join(BASE_DIR, "bot_state.json")
        with open(state_file, "r") as f:
            state = json.load(f)
            sidebar = state.get("sidebar_settings", {})
            
            return {
                "asset": sidebar.get("asset", "BTC"),
                "execution_mode": sidebar.get("execution_mode", "Manual (Phantom)"),
                "trading_enabled": sidebar.get("trading_enabled", False),
                "size_type": sidebar.get("size_type", "Fixed (USDC)"),
                "size_value": sidebar.get("size_value", 100.0),
                "leverage": sidebar.get("leverage", 5),
                "max_positions": sidebar.get("max_positions", 3),
                "daily_stop_loss": sidebar.get("daily_stop_loss", 100.0)
            }
    except:
        # Return defaults
        return {
            "asset": "BTC",
            "execution_mode": "Manual (Phantom)",
            "trading_enabled": False,
            "size_type": "Fixed (USDC)",
            "size_value": 100.0,
            "leverage": 5,
            "max_positions": 3,
            "daily_stop_loss": 100.0
        }

@app.post("/api/settings")
async def save_settings(settings: dict):
    """Save money management settings"""
    try:
        state_file = os.path.join(BASE_DIR, "bot_state.json")
        
        # 1. Update live bot context first (Source of Truth)
        # 1. Update live bot context first (Source of Truth)
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            
            # Extract scanner settings
            scanner_settings = settings.pop("scanner", {})
            bot.scanner_settings = scanner_settings
            
            bot.sidebar_settings = settings
            bot.active_symbol = settings.get("asset", "BTC")
            # We don't necessarily want to force trading_enabled from sidebar if it logic differs, 
            # but usually settings controls it.
            # bot.trading_enabled = settings.get("trading_enabled", False) 
            # Actually, execution_mode is what matters more
            bot.execution_mode = settings.get("execution_mode", "Manual (Phantom)")
            
            # Use StateManager to save everything consistently
            try:
                from app.core.state_manager import StateManager
                StateManager.save_state(bot)
                print(f"✅ Settings synced to bot and saved.")
                return {"status": "success", "message": "Settings saved and synced"}
            except Exception as e:
                print(f"Error saving via StateManager: {e}")

        # 2. Fallback / Standalone persistence
        # Read existing state
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
        except:
            state = {}
        
        # Update sidebar settings
        state["sidebar_settings"] = settings
        state["active_symbol"] = settings.get("asset", "BTC")
        
        # Update bot_state object
        bot_state.active_symbol = settings.get("asset", "BTC")
        bot_state.execution_mode = settings.get("execution_mode", "Manual (Phantom)")
        bot_state.trading_enabled = settings.get("trading_enabled", False)
        
        # Save to file
        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
        
        print(f"✅ Settings saved (Standalone): {settings}")
        return {"status": "success", "message": "Settings saved"}
    except Exception as e:
        print(f"Error saving settings: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/symbol/switch")
async def switch_symbol(data: dict):
    """Switch active trading symbol"""
    try:
        new_symbol = data.get("symbol", "BTC")
        
        # Update bot if connected
        # Update bot if connected
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            bot.active_symbol = new_symbol
            
            # Sync to sidebar settings to ensure persistence
            if hasattr(bot, 'sidebar_settings'):
                bot.sidebar_settings["asset"] = new_symbol
                
            bot.add_log(f"🔄 Switched to {new_symbol}")
            
            # Save state
            try:
                from app.core.state_manager import StateManager
                StateManager.save_state(bot)
            except Exception as e:
                print(f"Error saving state: {e}")
        
        # Update bot_state
        bot_state.active_symbol = new_symbol
        bot_state.save_state()
        
        print(f"✅ Symbol switched to: {new_symbol}")
        return {"status": "success", "symbol": new_symbol}
    except Exception as e:
        print(f"Error switching symbol: {e}")
        return {"status": "error", "message": str(e)}

# ============================================
# AI COMMENTARY ENDPOINTS
# ============================================

@app.post("/api/ai/signal_analysis")
async def ai_signal_analysis(data: dict):
    """Analyse un signal de trading avec l'IA"""
    try:
        from app.services.gemini_service import gemini_service
        
        signal_data = data.get("signal", {})
        market_context = data.get("market_context", {})
        
        analysis = gemini_service.analyze_trade_signal(signal_data, market_context)
        return analysis
    except Exception as e:
        print(f"Error in AI signal analysis: {e}")
        return {"error": str(e)}

@app.get("/api/ai/market_commentary")
async def ai_market_commentary():
    """Obtient le dernier commentaire de marché de l'IA"""
    try:
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            
            # Retourner l'analyse en cache
            last_analysis = bot.ai_cache.get("last_market_analysis")
            last_time = bot.ai_cache.get("last_market_analysis_time")
            
            if last_analysis:
                return {
                    "analysis": last_analysis,
                    "timestamp": last_time.isoformat() if last_time else None,
                    "cached": True
                }
        
        # Si pas de cache, générer une nouvelle analyse
        from app.services.gemini_service import gemini_service
        from backend.market_data import get_hyperliquid_candles, calculate_rsi, calculate_adx
        
        symbol = bot_state.active_symbol if not (bot_bridge and bot_bridge.is_connected()) else bot.active_symbol
        df = await get_hyperliquid_candles(symbol, "15m", 100)
        
        if df is not None and len(df) > 0:
            current_data = {
                "symbol": symbol,
                "price": float(df['close'].iloc[-1]),
                "timestamp": pd.Timestamp.now().isoformat()
            }
            
            analysis = gemini_service.analyze_market_evolution(current_data)
            return {
                "analysis": analysis,
                "timestamp": pd.Timestamp.now().isoformat(),
                "cached": False
            }
        
        return {"error": "No market data available"}
    except Exception as e:
        print(f"Error in AI market commentary: {e}")
        return {"error": str(e)}

@app.get("/api/ai/position_analysis")
async def ai_position_analysis():
    """Analyse la position active avec l'IA"""
    try:
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            
            if not bot.active_trade:
                return {"error": "No active position"}
            
            # Retourner l'analyse en cache si récente
            last_analysis = bot.ai_cache.get("last_position_analysis")
            last_time = bot.ai_cache.get("last_position_analysis_time")
            
            if last_analysis and last_time:
                from datetime import datetime, timedelta
                if (datetime.now() - last_time) < timedelta(minutes=5):
                    return {
                        "analysis": last_analysis,
                        "timestamp": last_time.isoformat(),
                        "cached": True
                    }
            
            # Générer une nouvelle analyse
            from app.services.gemini_service import gemini_service
            from backend.market_data import get_hyperliquid_candles
            
            df = await get_hyperliquid_candles(bot.active_symbol, "15m", 50)
            
            if df is not None and len(df) > 0:
                market_context = {
                    "price": float(df['close'].iloc[-1]),
                    "symbol": bot.active_symbol
                }
                
                analysis = gemini_service.analyze_active_position(bot.active_trade, market_context)
                return {
                    "analysis": analysis,
                    "timestamp": pd.Timestamp.now().isoformat(),
                    "cached": False
                }
        
        return {"error": "No active position or bot not connected"}
    except Exception as e:
        print(f"Error in AI position analysis: {e}")
        return {"error": str(e)}

@app.get("/api/ai/history")
async def ai_history():
    """Historique des analyses IA"""
    try:
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            
            # Récupérer les analyses de signaux
            signal_analyses = list(bot.ai_cache.get("signal_analyses", []))
            
            # Récupérer les snapshots de marché
            market_snapshots = list(bot.ai_cache.get("market_snapshots", []))
            
            return {
                "signal_analyses": signal_analyses[-10:],  # Dernières 10
                "market_snapshots": market_snapshots[-5:],  # Derniers 5
                "last_market_analysis": bot.ai_cache.get("last_market_analysis"),
                "last_position_analysis": bot.ai_cache.get("last_position_analysis")
            }
        
        return {"error": "Bot not connected"}
    except Exception as e:
        print(f"Error getting AI history: {e}")
        return {"error": str(e)}




if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting API server...")
    print(f"📁 BASE_DIR: {BASE_DIR}")
    print(f"🌐 API: http://localhost:8000")
    print(f"📚 Docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
