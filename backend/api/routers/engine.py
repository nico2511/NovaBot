"""
Engine Router - Bot Engine Control Endpoints
Handles start, stop, restart, panic, and status operations
"""
from fastapi import APIRouter, Depends, HTTPException
from backend.api.dependencies import get_bot_context
from pydantic import BaseModel
import logging
import pandas as pd
from backend.services import storage

logger = logging.getLogger("EngineRouter")

router = APIRouter(prefix="/api", tags=["engine"])


@router.get("/status")
def get_status(bot=Depends(get_bot_context)):
    """Get comprehensive bot status including positions, balance, and settings"""
    try:
        # Get current positions
        # Get current positions via Service (Fixes missing attribute issue)
        from app.services.hyperliquid_service import hyperliquid_service
        positions = hyperliquid_service.get_positions()
        
        # Add duration to each position
        for pos in positions:
            try:
                entry_time_str = pos.get("entry_time")
                if entry_time_str:
                    # entry_time is stored in ISO format (UTC)
                    entry_time = pd.Timestamp(entry_time_str)
                    # Use UTC now for comparison
                    elapsed = pd.Timestamp.now(tz='UTC').tz_localize(None) - entry_time.tz_localize(None)
                    
                    # Format duration as "Xh Ym" or "Xm" if less than 1 hour
                    total_seconds = int(elapsed.total_seconds())
                    hours = total_seconds // 3600
                    minutes = (total_seconds % 3600) // 60
                    
                    if hours > 0:
                        pos["duration"] = f"{hours}h {minutes}m"
                    else:
                        pos["duration"] = f"{minutes}m"
                else:
                    pos["duration"] = "--"
            except Exception as e:
                logger.warning(f"Failed to calculate duration for {pos.get('symbol', 'UNKNOWN')}: {e}")
                pos["duration"] = "--"
        
        # Get account balance
        balance = 0.0
        try:
            balance_data = hyperliquid_service.get_account_balance()
            if balance_data.get("status") == "success":
                balance = balance_data.get("total_equity", 0.0)
        except Exception as e:
            logger.error(f"Error fetching balance: {e}")
        
        # Build status response
        return {
            "is_running": bot.is_running,
            "status": "running" if bot.is_running else "stopped",
            "trading_enabled": bot.trading_enabled,
            "active_symbol": bot.active_symbol,
            "balance": balance,
            "open_positions": positions,
            "active_positions": len(positions),
            "daily_pnl": getattr(bot, 'daily_pnl', 0.0),
            "total_trades": getattr(bot, 'total_trades', 0),
            "win_rate": getattr(bot, 'win_rate', 0.0),
            "last_updated": getattr(bot, 'last_update_time', None),
            "margin_usage": getattr(bot, 'margin_usage', 0.0),
            "max_drawdown": getattr(bot, 'max_drawdown', 0.0),
            "settings": {
                "max_positions": bot.max_positions,
                "daily_stop_loss": bot.global_settings.get("risk_defaults", {}).get("daily_stop_loss", 0),
                "leverage": getattr(bot, 'leverage', 1),
                "bot_persona": getattr(bot, 'bot_persona', 'Unknown'),
                "risk_profile": getattr(bot, 'risk_profile', 'Unknown')
            },
            "market_analysis": getattr(bot, 'ai_cache', {}).get('last_position_analysis'),
            "logs": list(getattr(bot, 'logs', []))[-50:]
        }
    except Exception as e:
        logger.error(f"Error in get_status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")


@router.post("/engine/start")
def start_engine(bot=Depends(get_bot_context)):
    """Start the trading engine"""
    try:

        # Always enable trading when start is requested
        bot.trading_enabled = True
        
        if bot.is_running:
            bot.add_log("🚀 Trading Enabled (Engine was already running)")
            return {"status": "started", "message": "Trading Enabled"}
        
        bot.add_log("🚀 ENGINE: Starting via API...")
        bot.start()
        
        return {"status": "started", "message": "Engine started successfully"}
    except Exception as e:
        logger.error(f"Error starting engine: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start engine: {str(e)}")


@router.post("/engine/stop")
def stop_engine(bot=Depends(get_bot_context)):
    """Stop the trading engine"""
    try:
        # Always disable trading when stop is requested
        bot.trading_enabled = False
        
        if not bot.is_running:
            return {"status": "stopped", "message": "Trading Disabled"}
        
        bot.add_log("🛑 ENGINE: Stopping via API...")
        bot.stop()
        
        return {"status": "stopped", "message": "Engine stopped successfully"}
    except Exception as e:
        logger.error(f"Error stopping engine: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to stop engine: {str(e)}")


@router.post("/engine/restart")
def restart_engine(bot=Depends(get_bot_context)):
    """Restart the trading engine (stop + start)"""
    try:
        bot.add_log("🔄 RESTART: Stopping engine...")
        bot.stop()
        import time
        time.sleep(2)  # Brief pause to allow clean shutdown
        bot.add_log("🔄 RESTART: Starting engine...")
        bot.start()
        
        # Save state after restart
        try:
            from app.core.state_manager import StateManager
            StateManager.save_state(bot)
        except Exception as e:
            logger.warning(f"Failed to save state after restart: {e}")
        
        return {"status": "restarted", "message": "Engine restarted successfully"}
    except Exception as e:
        logger.error(f"Restart failed: {e}")
        raise HTTPException(status_code=500, detail=f"Restart failed: {str(e)}")


@router.post("/engine/panic")
def panic_close(bot=Depends(get_bot_context)):
    """🚨 PANIC BUTTON: Stop engine and close ALL positions immediately"""
    results = []
    
    # 1. Stop the Engine first
    try:
        bot.stop()
        bot.trading_enabled = False
        bot.add_log("🚨 PANIC BUTTON ACTIVATED! Stopping engine...")
    except Exception as e:
        logger.error(f"Failed to stop engine during panic: {e}")
    
    # 2. Close ALL positions
    try:
        if hasattr(bot, 'hyperliquid') and bot.hyperliquid:
            user_state = bot.hyperliquid.info.user_state(bot.hyperliquid.account_address)
            positions = user_state.get("assetPositions", [])
            
            for pos in positions:
                position_data = pos.get("position", {})
                coin = position_data.get("coin")
                szi = position_data.get("szi", "0")
                
                if float(szi) != 0:
                    try:
                        # Close position with market order
                        is_long = float(szi) > 0
                        close_size = abs(float(szi))
                        
                        bot.add_log(f"🚨 PANIC: Closing {coin} position (size: {szi})")
                        
                        result = bot.hyperliquid.market_close(coin, close_size)
                        results.append({
                            "symbol": coin,
                            "size": szi,
                            "status": "closed" if result.get("status") == "success" else "failed",
                            "result": result
                        })
                    except Exception as e:
                        logger.error(f"Failed to close {coin}: {e}")
                        results.append({
                            "symbol": coin,
                            "size": szi,
                            "status": "error",
                            "error": str(e)
                        })
    except Exception as e:
        logger.error(f"Failed to fetch positions during panic: {e}")
        results.append({"status": "error", "error": f"Failed to fetch positions: {str(e)}"})
    
    # 3. Save state
    try:
        from app.core.state_manager import StateManager
        StateManager.save_state(bot)
    except Exception as e:
        logger.warning(f"Failed to save state after panic: {e}")
    
    return {
        "status": "panic_executed",
        "message": "Panic close executed - engine stopped and positions closed",
        "results": results
    }


# ==========================================
# STRATEGY CONFIGURATION
# ==========================================

@router.get("/config/strategy-list")
def get_strategies(bot=Depends(get_bot_context)):
    """Get list of available strategies"""
    try:
        # Load strategy metadata from strategies.json using centralized storage
        strategy_metadata = storage.storage_service.load_strategies()
        
        strategies = []
        if hasattr(bot, 'strategy_engine'):
            for name, strategy in bot.strategy_engine.strategies.items():
                # Get metadata from strategies.json
                meta = strategy_metadata.get(name, {})
                
                # Check if enabled in bot memory (source of truth for runtime)
                # But fallback to config if not set
                is_enabled = False
                if hasattr(strategy, 'config'):
                    is_enabled = strategy.config.get("enabled", False)
                elif hasattr(strategy, 'active'):
                    is_enabled = strategy.active
                
                strategies.append({
                    "id": name,
                    "name": name,
                    "enabled": is_enabled,
                    "type": meta.get("type", "unknown").upper(),
                    "description": meta.get("description", strategy.description if hasattr(strategy, 'description') else "No description")
                })
        return strategies
    except Exception as e:
        logger.error(f"Error fetching strategies: {e}")
        return []


class StrategySelectRequest(BaseModel):
    strategy_id: str

class StrategyParamsRequest(BaseModel):
    strategy_id: str
    params: dict

@router.post("/config/strategy-select")
def select_strategy(data: StrategySelectRequest, bot=Depends(get_bot_context)):
    """Toggle strategy enabled state"""
    try:
        strat_id = data.strategy_id
        if hasattr(bot, 'strategy_engine') and strat_id in bot.strategy_engine.strategies:
            strategy = bot.strategy_engine.strategies[strat_id]
            
            # Toggle enabled state
            current_state = strategy.config.get("enabled", False)
            new_state = not current_state
            strategy.config["enabled"] = new_state
            strategy.config["active"] = new_state # Sync active/enabled
            
            # Update persistence (strategies.json) using storage service
            full_config = storage.storage_service.load_strategies()
            
            if strat_id in full_config:
                full_config[strat_id]["enabled"] = new_state
                full_config[strat_id]["active"] = new_state
                storage.storage_service.save_strategies(full_config)
                        
            bot.add_log(f"🧠 Strategy Toggled: {strat_id} -> {'ENABLED' if new_state else 'DISABLED'}")
            
            return {
                "status": "success",
                "message": f"Strategy {strat_id} {'enabled' if new_state else 'disabled'}",
                "active_strategy": strat_id,
                "enabled": new_state
            }
        else:
            raise HTTPException(status_code=404, detail=f"Strategy {strat_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error toggling strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/config/strategy-params")
def update_strategy_params(data: StrategyParamsRequest, bot=Depends(get_bot_context)):
    """Update strategy parameters and persist to strategies.json"""
    try:
        strat_id = data.strategy_id
        new_params = data.params
        
        if hasattr(bot, 'strategy_engine') and strat_id in bot.strategy_engine.strategies:
            strategy = bot.strategy_engine.strategies[strat_id]
            
            # Update runtime config
            if not hasattr(strategy, 'config'):
                strategy.config = {}
            if "params" not in strategy.config:
                strategy.config["params"] = {}
                
            strategy.config["params"].update(new_params)
            
            # Persist to JSON using storage service
            full_config = storage.storage_service.load_strategies()
            
            if strat_id in full_config:
                if "params" not in full_config[strat_id]:
                    full_config[strat_id]["params"] = {}
                full_config[strat_id]["params"].update(new_params)
                storage.storage_service.save_strategies(full_config)
                        
            bot.add_log(f"⚙️ Strategy Params Updated: {strat_id}")
            return {"status": "success", "message": f"Parameters updated for {strat_id}"}
        else:
            raise HTTPException(status_code=404, detail=f"Strategy {strat_id} not found")
    except Exception as e:
        logger.error(f"Error updating strategy params: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@router.get("/strategies/monitor")
def monitor_strategies(bot=Depends(get_bot_context)):
    """Get real-time monitoring data for all strategies"""
    try:
        if not hasattr(bot, 'latest_data') or bot.latest_data.empty:
            return {"status": "waiting", "message": "No market data available yet"}

        # Get Regime
        regime = "UNKNOWN"
        try:
             # Try to get from AI cache first
            if hasattr(bot, 'latest_analysis') and bot.latest_analysis:
                regime = bot.latest_analysis.get("regime", "UNKNOWN")
            
            # Fallback to ADX calculation if needed
            if regime == "UNKNOWN" and 'ADX_14' in bot.latest_data.columns:
                 adx = bot.latest_data['ADX_14'].iloc[-1]
                 regime = "TREND" if adx > 25 else "RANGE"
        except: pass

        results = []
        if hasattr(bot, 'strategy_engine'):
            # Load metadata for descriptions using storage service
            strategy_metadata = storage.storage_service.load_strategies()

            df = bot.latest_data
            
            # Pre-fetch 1m data once for the active symbol if any MTF strategies need it
            extra_data = {}
            try:
                from app.services.hyperliquid_service import hyperliquid_service
                df_1m = hyperliquid_service.get_candles(bot.active_symbol, interval="1m", limit=100)
                if df_1m is not None and not df_1m.empty:
                    extra_data["1m"] = df_1m
            except Exception as e:
                logger.error(f"Error fetching 1m data for monitor: {e}")

            # Use active strategies or all enabled strategies?
            for name, strategy in bot.strategy_engine.strategies.items():
                try:
                    # Only check enabled strategies
                    config = strategy.config if hasattr(strategy, 'config') else {}
                    if not config.get("enabled", False):
                        continue
                        
                    progress = strategy.calculate_progress(df, extra_data=extra_data)
                    
                    # Ensure progress is a dict
                    if isinstance(progress, (int, float)):
                         progress = {
                             "strategy": name,
                             "score": progress,
                             "stages": []
                         }
                    elif not isinstance(progress, dict):
                         progress = {"strategy": name, "error": "Invalid progress format"}
                    
                    # Enhance with config data
                    meta = strategy_metadata.get(name, {})
                    progress['type'] = config.get("type", meta.get("type", "unknown")).lower()
                    progress['description'] = meta.get("description", "No description")
                    progress['name'] = meta.get("name", name) # Use friendly name if available
                    progress['bias'] = progress.get('bias', 'NEUTRAL') # Pass the bias through
                    
                    results.append(progress)
                except Exception as e:
                    results.append({
                        "strategy": name,
                        "error": str(e),
                        "type": "unknown"
                    })
                    
        return {
            "timestamp": pd.Timestamp.now().isoformat(),
            "symbol": bot.active_symbol,
            "regime": regime,
            "strategies": results
        }
    except Exception as e:
        logger.error(f"Error monitoring strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))
