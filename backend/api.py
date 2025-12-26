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
try:
    from backend.routes.settings import router as settings_router
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
            state["sidebar_settings"]["trading_enabled"] = self.trading_enabled
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
        bot_state.trading_enabled = False
        bot_state.add_log("🔴 Live trading DISABLED")
        bot_state.save_state()
        return {"status": "disabled", "message": "Standalone mode - bot_state updated"}

@app.get("/api/candles")
async def get_candles(limit: int = 200, strategy: Optional[str] = None):
    """Get formatted candles for chart, optionally with strategy indicators"""
    try:
        try:
            from backend.market_data import get_hyperliquid_candles
        except ImportError:
            from market_data import get_hyperliquid_candles
            
        # 1. Fetch raw candles
        df = await get_hyperliquid_candles(bot_state.active_symbol, "15m", limit)
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
        try:
            from backend.market_data import get_hyperliquid_candles, get_current_price, calculate_rsi, calculate_atr, calculate_adx, calculate_ema, calculate_bb
        except ImportError:
            from market_data import get_hyperliquid_candles, get_current_price, calculate_rsi, calculate_atr, calculate_adx, calculate_ema, calculate_bb
        
        # Get candles for indicator calculation
        df = await get_hyperliquid_candles(bot_state.active_symbol, "15m", 100)
        
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
            price = await get_current_price(bot_state.active_symbol)
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
        "symbol": bot_state.active_symbol,
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
    """Get account balance (mock for now)"""
    return {
        "total_equity": 27.48,
        "available": 27.48,
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
    """Close active trade"""
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        if bot.active_trade:
            bot.add_log(f"🔴 Trade closed manually via API")
            bot.active_trade = None
            return {"status": "closed", "message": "Trade closed on real bot"}
        return {"status": "no_active_trade"}
    
    if bot_state.active_trade:
        bot_state.active_trade = None
        return {"status": "closed", "message": "Standalone mode - trade closed"}
    return {"status": "no_active_trade"}

@app.get("/api/settings")
async def get_settings():
    """Get money management settings"""
    try:
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
        
        print(f"✅ Settings saved: {settings}")
        return {"status": "success", "message": "Settings saved"}
    except Exception as e:
        print(f"Error saving settings: {e}")
        return {"status": "error", "message": str(e)}



if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting API server...")
    print(f"📁 BASE_DIR: {BASE_DIR}")
    print(f"🌐 API: http://localhost:8000")
    print(f"📚 Docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
