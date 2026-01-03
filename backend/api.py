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

# Import services
from app.services.hyperliquid_service import hyperliquid_service
try:
    from app.services.ia import ia_service
    AI_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ AI Service not available: {e}")
    AI_AVAILABLE = False
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
                    MeanReversion, SMCFVG
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
            from backend.market_data import get_hyperliquid_candles, get_current_price, calculate_rsi, calculate_atr, calculate_adx, calculate_ema, calculate_bb, get_open_interest
        except ImportError:
            from market_data import get_hyperliquid_candles, get_current_price, calculate_rsi, calculate_atr, calculate_adx, calculate_ema, calculate_bb, get_open_interest
        
        # MULTI-TIMEFRAME ANALYSIS
        timeframes = ["15m", "1h", "4h", "1d"]
        data_layers = {}
        
        # Base indicators from 15m as default
        # OPTIMIZATION: Try to use bot's latest cached data if available to avoid API spam
        base_df = None
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            if hasattr(bot, 'latest_data') and not bot.latest_data.empty:
                 # Use cached data from bot loop
                 base_df = bot.latest_data
        
        # Fallback to fetching if bot data is empty
        if base_df is None or base_df.empty:
            base_df = await get_hyperliquid_candles(active_symbol, "15m", 100)
        
        price = 0.0
        if base_df is not None and not base_df.empty:
            price = float(base_df['close'].iloc[-1])
            
            # Base Layer (15m)
            rsi = await calculate_rsi(base_df['close'], 14)
            atr = await calculate_atr(base_df, 14)
            adx = await calculate_adx(base_df, 14)
            ema_20 = await calculate_ema(base_df['close'], 20)
            ema_50 = await calculate_ema(base_df['close'], 50)
            bb = await calculate_bb(base_df['close'], 20, 2)
            
            # Volume 24h approximation (sum of last 96 15m candles)
            volume_24h = base_df['volume'].sum() * price
        else:
             price = await get_current_price(active_symbol)
             rsi, atr, adx, ema_20, ema_50 = 50, 0, 0, price, price
             bb = {"upper": price, "middle": price, "lower": price}
             volume_24h = 0

        # Fetch Open Interest
        open_interest = await get_open_interest(active_symbol)

        # Calculate Trends for all timeframes
        trends = {}
        for tf in timeframes:
            tf_df = await get_hyperliquid_candles(active_symbol, tf, 50)
            if tf_df is not None and not tf_df.empty:
                tf_adx = await calculate_adx(tf_df, 14)
                tf_ema20 = await calculate_ema(tf_df['close'], 20)
                tf_ema50 = await calculate_ema(tf_df['close'], 50)
                
                # Simple Trend Logic
                trend_dir = "NEUTRAL"
                if tf_ema20 > tf_ema50:
                    trend_dir = "BULLISH" if tf_adx > 20 else "RANGING BULL"
                else:
                    trend_dir = "BEARISH" if tf_adx > 20 else "RANGING BEAR"
                    
                trends[tf] = {
                    "adx": tf_adx,
                    "trend": trend_dir
                }
            else:
                trends[tf] = {"adx": 0, "trend": "UNKNOWN"}

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
        trends = {tf: {"adx": 0, "trend": "UNKNOWN"} for tf in ["15m", "1h", "4h", "1d"]}
        open_interest = 0
        volume_24h = 0
    
    # Get active strategies and their progress from bot if connected
    active_strategies = []
    strategy_progress = {}
    
    # Defaults from local calculation
    final_regime = trends["15m"]["trend"]
    
    try:
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            # Get strategies from latest analysis result
            if hasattr(bot, 'latest_strategy_result') and bot.latest_strategy_result:
                result = bot.latest_strategy_result
                # Get the list of active strategy names (these are already filtered by regime)
                strategy_names = result.get('strategies', [])
                progress_data = result.get('progress', {})
                
                # CRITICAL: Use the Bot's calculated regime and ADX as source of truth
                if 'regime' in result:
                    final_regime = result['regime']
                
                # Format for frontend
                for name in strategy_names:
                    active_strategies.append(name)
                    strategy_progress[name] = progress_data.get(name, 0)
        
        # If bot not connected or no analysis yet, return empty list
        if not active_strategies:
            active_strategies = []
            strategy_progress = {}
        # Calculate V2 Metrics (RVol & Trend Alignment)
        try:
            # 1. Relative Volume (RVol)
            if base_df is not None and len(base_df) >= 96:
                # Approximation: Current 24h vol vs Previous 24h vol
                vol_24h_current = base_df['volume'].iloc[-96:].sum()
                
                if len(base_df) >= 192:
                    vol_24h_prev = base_df['volume'].iloc[-192:-96].sum()
                else:
                    vol_24h_prev = vol_24h_current # Fallback
                
                rvol = vol_24h_current / vol_24h_prev if vol_24h_prev > 0 else 1.0
            else:
                rvol = 1.0
            
            # 2. Trend Alignment (Strict V2 Definition)
            # Requires EMA 9, 20, 50
            if base_df is not None and not base_df.empty:
                ema_9 = base_df['close'].ewm(span=9).mean().iloc[-1]
                # ema_20 and ema_50 are already calculated above
                
                trend_aligned = (price > ema_9 > ema_20 > ema_50) or \
                               (price < ema_9 < ema_20 < ema_50)
            else:
                trend_aligned = False
                
        except Exception as e:
            print(f"Error calculating V2 metrics: {e}")
            rvol = 1.0
            trend_aligned = False

    except Exception as e:
        print(f"Error getting active strategies: {e}")
        active_strategies = []
        strategy_progress = {}
    
    return {
        "symbol": active_symbol,  # CRITICAL: Return the ACTIVE symbol from bot
        "price": float(price),
        "timestamp": datetime.now().isoformat(),
        "regime": final_regime,
        "adx": float(adx),
        "rsi": float(rsi),
        "atr": float(atr),
        "ema_20": float(ema_20),
        "ema_50": float(ema_50),
        "bb": bb,
        "volume_24h": volume_24h,
        "open_interest": open_interest,
        "rvol": float(rvol),
        "trend_aligned": bool(trend_aligned),
        "trends": trends,
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
        
        from app.services.hyperliquid_service import hyperliquid_service
        
        # This is now cached internally in hyperliquid_service for 10s
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
    """Get current active trade with AI analysis"""
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        trade = bot.active_trade
        
        if trade:
            # Inject AI Analysis if available
            symbol = trade.get("symbol")
            if hasattr(bot, 'ai_cache'):
                cache_key = f"position_analysis_{symbol}"
                ai_analysis = bot.ai_cache.get(cache_key)
                if ai_analysis:
                    # Create a copy to not mutate the original state
                    trade = trade.copy()
                    trade["ai_analysis"] = ai_analysis
        
        return {"active_trade": trade}
    return {"active_trade": bot_state.active_trade}

@app.post("/api/close_trade")
async def close_trade():
    """Close active trade - Manual Override"""
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        
        if bot.active_trade:
            symbol = bot.active_trade["symbol"]
            
            try:
                from app.services.hyperliquid_service import hyperliquid_service
                
                bot.add_log(f"🔴 MANUAL CLOSE: Closing {symbol}")
                
                # Execute close regardless of bot mode (Manual Override)
                result = hyperliquid_service.close_position(symbol)
                
                # CRITICAL: Even if Hyperliquid says "No position found", clear bot state
                # This handles desync cases where bot thinks it has a trade but exchange doesn't
                if result.get("success") or "No position found" in result.get("message", ""):
                    bot.active_trade = None
                    bot.add_log(f"✅ Position cleared from bot state")
                    
                    # Record the close
                    try:
                        from app.core.state_manager import StateManager
                        StateManager.save_state(bot)
                    except Exception as e:
                        print(f"Error saving state: {e}")
                    
                    return {"success": True, "message": "Position closed or cleared"}
                else:
                    bot.add_log(f"❌ Close failed: {result.get('message')}")
                    return {"success": False, "message": result.get("message")}
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                return {"status": "error", "message": str(e)}
        else:
            return {"status": "error", "message": "No active trade to close"}
    
    return {"status": "error", "message": "Bot not connected"}

@app.post("/api/recalibrate_stops")
async def recalibrate_stops():
    """Recalibrate TP/SL for active trade"""
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        
        if not hasattr(bot, 'recalibrate_position_stops'): # Safety check during dev
             return {"status": "ERROR", "message": "Feature not available on bot instance yet"}

        status, message = await bot.recalibrate_position_stops()
        
        return {
            "status": status, # UNCHANGED, UPDATED, ERROR
            "message": message
        }
    
    return {"status": "ERROR", "message": "Bot not connected"}

@app.post("/api/force_breakeven")
async def force_breakeven():
    """Force SL to Break Even (Entry + Fees)"""
    if bot_bridge and bot_bridge.is_connected():
        bot = bot_bridge.get_bot_context()
        
        if not bot.active_trade:
            return {"status": "ERROR", "message": "No active trade"}
        
        try:
            # Calculate Break Even price (Entry + 0.1% for fees)
            entry = bot.active_trade.get("entry", 0)
            side = bot.active_trade.get("side", "BUY")
            
            if side == "BUY":
                be_price = entry * 1.001  # Entry + 0.1%
            else:
                be_price = entry * 0.999  # Entry - 0.1%
            
            # Update local state
            bot.active_trade["sl"] = be_price
            
            # Enforce on exchange
            bot._verify_and_enforce_sl_tp(bot.active_symbol, bot.active_trade)
            
            bot.add_log(f"🛡️ FORCED Break Even @ {be_price:.6f}")
            
            return {
                "status": "SUCCESS",
                "message": f"SL moved to Break Even @ {be_price:.6f}"
            }
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
    
    return {"status": "ERROR", "message": "Bot not connected"}


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
        print(f"📥 RECEIVED MANUAL TRADE REQUEST: {request}") # DEBUG LOG
        symbol = request.get("symbol")
        action = request.get("action")  # "BUY" or "SELL"
        price = request.get("price")
        sl = request.get("sl")
        tp = request.get("tp")
        strategy = request.get("strategy", "Manual")
        
        if not all([symbol, action, price, sl, tp]):
            print("❌ Missing parameters in manual trade")
            return {"status": "error", "message": "Missing required parameters"}
        
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            
            # Vérifier qu'il n'y a pas déjà un trade actif
            if bot.active_trade:
                print(f"❌ Trade rejected: Active trade exists ({bot.active_trade['symbol']})")
                return {"status": "error", "message": "A trade is already active"}
            
            # Vérifier les limites de risque
            can_trade, reason = bot.risk_manager.check_can_trade()
            if not can_trade:
                print(f"❌ Trade rejected by Risk Manager: {reason}")
                return {"status": "error", "message": reason}

            # 🛡️ GAMIFICATION CHECK 🛡️
            try:
                from app.core.asset_gamification import check_asset_access, AssetGamification
                from app.services.hyperliquid_service import hyperliquid_service
                
                # Get fresh balance for accurate level
                balance_data = hyperliquid_service.get_account_balance()
                current_equity = balance_data.get("equity", 0.0) if balance_data.get("status") == "success" else 0.0
                
                # 1. Check Level & Asset Tier
                allowed, reason, status = check_asset_access(symbol, current_equity)
                if not allowed:
                    bot.add_log(f"🛑 Trade blocked by Gamification: {reason}")
                    return {"status": "error", "message": f"Gamification Restriction: {reason}"}
                
                # 2. Check Leverage Limit
                requested_leverage = bot.sidebar_settings.get("leverage", 1)
                max_leverage = status["max_leverage"]
                if requested_leverage > max_leverage:
                    msg = f"Leverage {requested_leverage}x too high for {status['level']} level (Max {max_leverage}x)"
                    bot.add_log(f"🛑 Trade blocked: {msg}")
                    return {"status": "error", "message": msg}
                
                # 3. Check Position Size Limit (if applicable)
                if status["max_position_size"]:
                    size_value = bot.sidebar_settings.get("size_value", 100.0)
                    if size_value > status["max_position_size"]:
                        msg = f"Position size ${size_value} exceeds limit for {status['level']} level (Max ${status['max_position_size']})"
                        bot.add_log(f"🛑 Trade blocked: {msg}")
                        return {"status": "error", "message": msg}
                        
            except Exception as e:
                print(f"⚠️ Gamification check error (proceeding anyway): {e}")

            # Exécuter le trade si mode Auto
            if bot.execution_mode == "Auto (Hyperliquid)":
                try:
                    from app.services.hyperliquid_service import hyperliquid_service
                    
                    is_buy = (action == "BUY")
                    size_value = bot.sidebar_settings.get("size_value", 100.0)
                    size_type = bot.sidebar_settings.get("size_type", "Fixed (USDC)")
                    
                    if size_type == "Fixed (USDC)":
                         quantity = round(size_value / price, 1) # Round to 1 decimal for safety
                    else:
                         quantity = round(size_value / price, 1) # Default fallback
                    
                    leverage = bot.sidebar_settings.get("leverage", 1)
                    bot.add_log(f"📊 MANUAL TRADE: {action} {quantity} {symbol} @ {price} (${size_value}, {leverage}x)")
                    
                    # CRITICAL: Force update leverage before trading
                    try:
                        hyperliquid_service.update_leverage(symbol, leverage, is_cross=True)
                    except Exception as lev_error:
                        bot.add_log(f"⚠️ Leverage update failed: {lev_error}")

                    # Exécuter l'ordre
                    result = hyperliquid_service.execute_order(
                        symbol=symbol,
                        is_buy=is_buy,
                        quantity=quantity
                    )
                    
                    bot.add_log(f"✅ Order executed: {result}")
                    
                    # Enregistrer le trade actif
                    bot.active_trade = {
                        "symbol": symbol,
                        "side": action,
                        "entry": price,
                        "sl": sl,
                        "tp": tp,
                        "size": quantity, # Use quantity (tokens)
                        "size_value": size_value, # Store USDC value too
                        "leverage": bot.sidebar_settings.get("leverage", 1), # Also fix leverage
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
                    "size": bot.sidebar_settings.get("size_value", 100.0),
                    "leverage": bot.sidebar_settings.get("leverage", 1), # Also fix leverage
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
                "balance": 0
            }
        }



@app.get("/api/dev/diagnostics")
async def get_dev_diagnostics():
    """Dev diagnostics endpoint"""
    print("DEBUG: get_dev_diagnostics called")
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        from app.core.asset_gamification import AssetGamification
        bot = bot_bridge.get_bot_context() if bot_bridge and bot_bridge.is_connected() else None
        
        # Get detailed account info
        account_balance = hyperliquid_service.get_account_balance()
        account_value = account_balance.get("total_equity", 0)
        margin_used = account_balance.get("margin_used", 0)
        available_balance = account_balance.get("available_balance", 0)
        
        # Get positions
        positions = hyperliquid_service.get_positions()
        unrealized_pnl = sum([pos.get('pnl', 0) for pos in positions])
        
        # Get user state for additional metrics
        try:
            from hyperliquid.info import Info
            from app.core.config import config
            info = Info(config.HYPERLIQUID_API_URL, skip_ws=True)
            user_state = info.user_state(config.HL_ACCOUNT_ADDRESS)
            margin_summary = user_state.get("marginSummary", {})
            
            # Extract all available margin data
            withdrawable = float(margin_summary.get("withdrawable", 0))
            total_ntl_pos = float(margin_summary.get("totalNtlPos", 0))  # Total notional position value
            total_raw_usd = float(margin_summary.get("totalRawUsd", 0))
            cross_margin_summary = user_state.get("crossMarginSummary", {})
            
            # Calculate additional metrics
            account_leverage = (total_ntl_pos / account_value) if account_value > 0 else 0
            
        except Exception as e:
            print(f"Error fetching extended margin data: {e}")
            import traceback
            traceback.print_exc()
            withdrawable = available_balance
            total_ntl_pos = 0
            total_raw_usd = account_value
            account_leverage = 0
        
        # Get trade history (last 10 trades)
        try:
            trade_history = hyperliquid_service.get_trade_history(limit=10)
            recent_trades = []
            total_fees_paid = 0
            for trade in trade_history[:10]:
                fee = abs(float(trade.get("fee", 0)))
                total_fees_paid += fee
                recent_trades.append({
                    "symbol": trade.get("symbol", "N/A"),
                    "side": trade.get("side", "N/A"),
                    "size": float(trade.get("size", 0)),
                    "price": float(trade.get("entry_price", 0)),
                    "fee": fee,
                    "pnl_real": float(trade.get("pnl", 0)),
                    "time": trade.get("timestamp", 0)
                })
            if recent_trades:
                print(f"DEBUG TRADE: {recent_trades[0]}")
        except:
            recent_trades = []
            total_fees_paid = 0
        
        # Calculate portfolio stats
        total_portfolio_value = account_value + unrealized_pnl
        margin_ratio = (margin_used / account_value * 100) if account_value > 0 else 0
        
        # Get active symbol data
        active_symbol = bot.active_symbol if bot else bot_state.active_symbol
        symbol_data = {"name": active_symbol or "N/A"}
        
        if active_symbol and active_symbol != "N/A":
            try:
                market_data = hyperliquid_service.get_market_data(active_symbol)
                symbol_data.update(market_data)
            except Exception as e:
                print(f"Error fetching market data: {e}")
        
        # Calculate portfolio stats
        total_portfolio_value = account_value + unrealized_pnl
        margin_ratio = (margin_used / account_value * 100) if account_value > 0 else 0
        
        # Get daily PnL from bot state
        daily_pnl = getattr(bot_state, 'risk_state', {}).get('daily_pnl', 0)
        
        return {
            "account": {
                "balance": account_value,
                "margin_used": margin_used,
                "available_margin": available_balance,
                "margin_ratio": round(margin_ratio, 2),
                "withdrawable": round(withdrawable, 2),
                "account_leverage": round(account_leverage, 2)
            },
            "positions": [
                {
                    "symbol": pos.get('symbol'),
                    "side": pos.get('side'),
                    "size": pos.get('size'),
                    "entry_price": pos.get('entry_price'),
                    "leverage": pos.get('leverage', 1),
                    "pnl": pos.get('pnl', 0)
                }
                for pos in positions
            ],
            "symbol": symbol_data,
            "portfolio": {
                "total_value": round(total_portfolio_value, 2),
                "account_equity": round(account_value, 2),
                "unrealized_pnl": round(unrealized_pnl, 2),
                "realized_pnl_today": round(daily_pnl, 2),
                "margin_used": round(margin_used, 2),
                "available_balance": round(available_balance, 2),
                "withdrawable_balance": round(withdrawable, 2),
                "margin_ratio_pct": round(margin_ratio, 2),
                "account_leverage": round(account_leverage, 2),
                "total_notional_position": round(total_ntl_pos, 2),
                "open_positions_count": len(positions),
                "total_fees_paid_recent": round(total_fees_paid, 4),
                "roi_today_pct": round((daily_pnl / account_value * 100) if account_value > 0 else 0, 2),
                "roi_unrealized_pct": round((unrealized_pnl / account_value * 100) if account_value > 0 else 0, 2)
            },
            "recent_trades": recent_trades,
            "api_status": {
                "hyperliquid_connected": hyperliquid_service.exchange is not None,
                "last_call": pd.Timestamp.now().isoformat()
            },
            "bot_state": {
                "trading_enabled": bot.trading_enabled if bot else bot_state.trading_enabled,
                "is_running": bot.is_running if bot else bot_state.is_running,
                "active_symbol": bot.active_symbol if bot else bot_state.active_symbol,
                "execution_mode": bot.execution_mode if bot else bot_state.execution_mode
            },
            "trading_settings": bot.sidebar_settings if bot else {},
            "scanner_settings": getattr(bot, 'scanner_settings', {}) if bot else {},
            "scanner_results": getattr(bot.scanner_job, 'last_results', []) if bot and getattr(bot, 'scanner_job', None) else [],
            "gamification": (lambda: (
                AssetGamification(account_value).get_status_summary()
                if 'AssetGamification' in locals() else {}
            ))(),
            "active_strategy": (lambda: (
                 {
                     "name": getattr(bot, 'active_strategy_name', 'Unknown'), 
                     "params": getattr(bot.strategy_engine.strategies.get(getattr(bot, 'active_strategy_name')), 'config', {}) 
                     if hasattr(bot, 'strategy_engine') and hasattr(bot.strategy_engine, 'strategies') and getattr(bot, 'active_strategy_name') in bot.strategy_engine.strategies
                     else {}
                 } if bot else {"name": "Unknown", "params": {}}
            ))()
        }
    except Exception as e:
        print(f"Error in dev diagnostics: {e}")
        import traceback
        traceback.print_exc()
        return {
            "error": str(e),
            "account": {"balance": 0, "margin_used": 0, "available_margin": 0},
            "positions": [],
            "portfolio": {"total_value": 0},
            "bot_state": {}
        }




@app.post("/api/dev/scan")
async def manual_scan():
    """Trigger a manual scan"""
    bot = bot_bridge.get_bot_context()
    if not bot:
        return {"status": "error", "message": "Bot not initialized"}
    
    if not hasattr(bot, 'scanner_job'):
        return {"status": "error", "message": "Scanner job not initialized"}
        
    return bot.scanner_job.manual_scan()

@app.post("/api/momentum_ranking")
async def momentum_ranking(data: dict = None):
    """Get momentum-based ranking of tokens (Cross-Sectional Momentum)"""
    try:
        from app.services.token_scanner import HyperliquidScanner
        
        scanner = HyperliquidScanner()
        top_n = data.get("top_n", 3) if data else 3
        
        result = scanner.scan_momentum_ranking(top_n=top_n)
        
        return {
            "status": "success",
            "ranking": result
        }
    except Exception as e:
        print(f"Error in momentum_ranking: {e}")
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": str(e),
            "ranking": {"selected": [], "scores": {}, "weights": {}}
        }


@app.post("/api/toggle_gamification")
async def toggle_gamification(data: dict):
    """Toggle Gamification enforcement ON/OFF"""
    bot = bot_bridge.get_bot_context()
    if not bot:
        return {"status": "error", "message": "Bot not initialized"}
    
    enabled = data.get("enabled", True)
    bot.scanner_settings['gamification_enabled'] = enabled
    
    # Save state
    from app.core.state_manager import StateManager
    StateManager.save_state(bot)
    
    status_msg = "enabled" if enabled else "disabled"
    bot.add_log(f"🎮 Gamification {status_msg} via Config")
    
    return {
        "status": "success",
        "gamification_enabled": enabled,
        "message": f"Gamification {status_msg}"
    }


@app.get("/api/market_metrics")
async def get_market_metrics(symbol: str = "BTC"):
    """Get comprehensive market metrics including Scanner V2 data"""
    try:
        # Get candles
        df = hyperliquid_service.get_candles(symbol, "15m", 100)
        
        if df.empty:
            return {"error": "No data"}
        
        # Calculate Scanner V2 metrics
        current_price = df['close'].iloc[-1]
        volume_24h = df['volume'].iloc[-96:].sum() * current_price  # 96 candles = 24h
        avg_volume = df['volume'].iloc[-192:-96].sum() * df['close'].iloc[-96] if len(df) >= 192 else volume_24h
        
        rvol = volume_24h / avg_volume if avg_volume > 0 else 1.0
        
        # EMAs
        ema_9 = df['close'].ewm(span=9).mean().iloc[-1]
        ema_20 = df['close'].ewm(span=20).mean().iloc[-1]
        ema_50 = df['close'].ewm(span=50).mean().iloc[-1]
        
        # Trend Alignment
        trend_aligned = (current_price > ema_9 > ema_20 > ema_50) or \
                       (current_price < ema_9 < ema_20 < ema_50)
        
        # Distance from EMA20
        dist_from_ema20 = abs(current_price - ema_20) / ema_20 * 100
        
        # ADX Components
        import pandas_ta as ta
        adx_res = ta.adx(df['high'], df['low'], df['close'], length=14)
        adx = adx_res['ADX_14'].iloc[-1]
        dmp = adx_res['DMP_14'].iloc[-1]
        dmn = adx_res['DMN_14'].iloc[-1]
        
        adx_quality = 'STRONG_UP' if (adx > 30 and dmp > dmn) else \
                     'STRONG_DOWN' if (adx > 30 and dmn > dmp) else \
                     'WEAK'
        
        # RSI
        rsi = ta.rsi(df['close'], length=14).iloc[-1]
        
        return {
            "symbol": symbol,
            "current_price": current_price,
            "rsi": rsi,
            "adx": adx,
            "volume_24h": volume_24h,
            "rvol": rvol,
            "trend_aligned": trend_aligned,
            "dist_from_ema20": dist_from_ema20,
            "adx_quality": adx_quality
        }
        
    except Exception as e:
        return {"error": str(e)}

@app.post("/api/ai_analysis")
async def get_ai_analysis(data: dict = {}):
    """Get AI analysis for a symbol"""
    symbol = data.get("symbol", bot_state.active_symbol)
    
    try:
        from app.services.ia import ia_service
        
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
        
        # 2. Call AI Service
        analysis = ia_service.analyze_market(market_summary)
        return analysis

    except ImportError:
         return {"error": "AI Service not found"}
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

@app.get("/api/logs")
async def get_logs():
    """Get recent bot logs"""
    bot = bot_bridge.get_bot_context()
    if not bot:
        return {"logs": []}
    
    # Parse logs from strings "HH:MM:SS Message" to objects
    logs = []
    for log_str in list(bot.logs):
        try:
            parts = log_str.split(" ", 1)
            if len(parts) == 2:
                logs.append({"time": parts[0], "message": parts[1]})
            else:
                logs.append({"time": "", "message": log_str})
        except:
            continue
            
    # Return reversed to show newest first (frontend expects this? Or frontend handles it?)
    # Frontend appends? No, frontend sets logs. Backend logs are deque (append). 
    # Frontend LiveLogs.tsx: 
    # logs.map(...)
    # It just displays them. Usually we want newest at top or bottom?
    # LiveLogs.tsx has `logsEndRef`.
    # So it scrolls to bottom. So order should be chronological (oldest first).
    # bot.logs is deque (append). list(bot.logs) is oldest to newest.
    # So returning list(bot.logs) is correct.
    
    return {"logs": list(logs)}

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
            
            # Clear AI cache to prevent stale analysis
            if hasattr(bot, 'ai_cache'):
                if "last_market_analysis" in bot.ai_cache:
                    del bot.ai_cache["last_market_analysis"]
                if "last_market_analysis_time" in bot.ai_cache:
                    del bot.ai_cache["last_market_analysis_time"]
                bot.add_log(f"🧹 AI Cache cleared for {new_symbol}")
            
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
        from app.services.ia import ia_service
        
        signal_data = data.get("signal", {})
        market_context = data.get("market_context", {})
        
        analysis = ia_service.analyze_trade_signal(signal_data, market_context)
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
        from app.services.ia import ia_service
        from backend.market_data import get_hyperliquid_candles, calculate_rsi, calculate_adx
        
        symbol = bot_state.active_symbol if not (bot_bridge and bot_bridge.is_connected()) else bot.active_symbol
        df = await get_hyperliquid_candles(symbol, "15m", 100)
        
        if df is not None and len(df) > 0:
            current_data = {
                "symbol": symbol,
                "price": float(df['close'].iloc[-1]),
                "timestamp": pd.Timestamp.now().isoformat()
            }
            
            analysis = ia_service.analyze_market_evolution(current_data)
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
            symbol = bot.active_symbol
            cache_key = f"position_analysis_{symbol}"
            last_analysis = bot.ai_cache.get(cache_key) or bot.ai_cache.get("last_position_analysis")
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
            from app.services.ia import ia_service
            from backend.market_data import get_hyperliquid_candles
            
            df = await get_hyperliquid_candles(bot.active_symbol, "15m", 50)
            
            if df is not None and len(df) > 0:
                market_context = {
                    "price": float(df['close'].iloc[-1]),
                    "symbol": bot.active_symbol
                }
                
                analysis = ia_service.analyze_active_position(bot.active_trade, market_context)
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




@app.get("/api/dev/diagnostics")
async def dev_diagnostics():
    """Aggregate diagnostics for Developer Dashboard"""
    try:
        data = {
            "account": {},
            "positions": [],
            "symbol": {},
            "portfolio": {},
            "recent_trades": [],
            "api_status": {},
            "gamification": {},
            "trading_settings": {},
            "scanner_settings": {},
            "scanner_results": [],
            "active_strategy": {},
            "bot_state": {}
        }
        
        # 1. Account Info & Positions (Hyperliquid)
        try:
            from app.services.hyperliquid_service import hyperliquid_service
            
            # Balance (Cached)
            balance = hyperliquid_service.get_account_balance()
            if balance.get("status") == "success":
                data["account"] = {
                    "balance": balance.get("total_equity", 0),
                    "margin_used": balance.get("margin_used", 0),
                    "available_margin": balance.get("available_balance", 0),
                    "withdrawable": balance.get("withdrawable", 0),
                    "account_leverage": 0 # TODO: Calculate or fetch real leverage
                }
                
                # Positions
                all_positions = hyperliquid_service.get_positions()
                data["positions"] = []
                for p in all_positions:
                    data["positions"].append({
                        "symbol": p.get("symbol"),
                        "side": p.get("side"),
                        "size": p.get("size"),
                        "entry_price": p.get("entry_price"),
                        "leverage": p.get("leverage"),
                        "pnl": p.get("unrealized_pnl")
                    })
                    
        except Exception as e:
            print(f"Diagnostics Error (Account): {e}")

        # 2. Bot Context Data
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            
            # Bot State
            data["bot_state"] = {
                "trading_enabled": bot.trading_enabled,
                "is_running": bot.is_running,
                "active_symbol": bot.active_symbol,
                "execution_mode": bot.execution_mode
            }
            
            # Trading Settings
            data["trading_settings"] = {
                "leverage": bot.sidebar_settings.get("leverage", 1),
                "max_positions": bot.sidebar_settings.get("max_positions", 1), # Missing setting?
                "size_value": bot.sidebar_settings.get("size_value", 100),
                "size_type": bot.sidebar_settings.get("size_type", "Fixed (USDC)"),
                "daily_stop_loss": bot.sidebar_settings.get("daily_stop_loss", 0), # Config fixed issue
                "stop_loss_pct": bot.sidebar_settings.get("stop_loss_pct", 1.5),
                "take_profit_pct": bot.sidebar_settings.get("take_profit_pct", 3.0)
            }
            
            # Scanner Settings & Results
            if hasattr(bot, 'scanner_settings'):
                 data["scanner_settings"] = bot.scanner_settings
            
            if hasattr(bot, 'latest_scan_results'):
                 data["scanner_results"] = bot.latest_scan_results
                 
            # Active Strategy
            data["active_strategy"] = {
                "name": "N/A",
                "params": {}
            }
            if hasattr(bot, 'latest_strategy_result') and bot.latest_strategy_result:
                 strategies = bot.latest_strategy_result.get("strategies", [])
                 if strategies:
                     data["active_strategy"]["name"] = ", ".join(strategies)
                     # Fetch params from config if possible
                     data["active_strategy"]["params"] =  getattr(bot, 'strategy_config', {})
            
            # Gamification
            try:
                from app.core.asset_gamification import get_user_gamification_state
                from app.services.hyperliquid_service import hyperliquid_service
                
                # Re-fetch equity for accurate level
                eq = data["account"].get("balance", 0)
                gamification_state = get_user_gamification_state(eq)
                data["gamification"] = {
                    "level": gamification_state["level"],
                    "title": gamification_state["title"],
                    "progress_pct": gamification_state["progress_pct"] 
                }
            except Exception as e:
                print(f"Diagnostics Error (Gamification): {e}")
                
            # API/System Status
            data["api_status"] = {
                "hyperliquid_connected": True, # Assumed if we got here
                "last_call": datetime.now().isoformat(),
                # Mock rate limit for now, or fetch from service if available
                "rate_limit_remaining": 1150, 
                "rate_limit_total": 1200
            }
            
            # Symbol Data (Active Symbol)
            try:
                from backend.market_data import get_current_price, get_open_interest
                price = await get_current_price(bot.active_symbol)
                oi = await get_open_interest(bot.active_symbol)
                
                data["symbol"] = {
                    "name": bot.active_symbol,
                    "price": price,
                    "volume_24h": 0, # Fetch if possible
                    "funding_rate": 0, # Fetch if possible
                    "open_interest": oi
                }
            except:
                pass

        # 3. Recent Trades (from Recorder)
        try:
             from app.core.trade_recorder import TradeRecorder
             recorder = TradeRecorder()
             trades = recorder.load_trades()
             data["recent_trades"] = trades[-10:] # Last 10
             
             # Portfolio Stats
             stats = recorder.get_stats()
             data["portfolio"] = {
                 "total_value": data["account"].get("balance", 0),
                 "unrealized_pnl": sum(p.get("pnl", 0) for p in data["positions"]),
                 "realized_pnl_today": stats.get("daily_pnl", 0),
                 "roi_today_pct": 0, # Calc
                 "roi_unrealized_pct": 0, # Calc
                 "total_notional_position": sum(p.get("size", 0) * p.get("entry_price", 0) for p in data["positions"]),
                 "total_fees_paid_recent": 0
             }
        except Exception as e:
             print(f"Diagnostics Error (Recorder): {e}")
             
        return data

    except Exception as e:
        print(f"Diagnostics Fatal Error: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Starting API server...")
    print(f"📁 BASE_DIR: {BASE_DIR}")
    print(f"🌐 API: http://localhost:8000")
    print(f"📚 Docs: http://localhost:8000/docs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
