"""
Engine Router - Bot Engine Control Endpoints
Handles start, stop, restart, and status operations
"""
from fastapi import APIRouter, Depends, HTTPException
from app.api.dependencies import get_bot_context
from app.api.auth import require_api_key
from pydantic import BaseModel
import logging
import pandas as pd
from app.services import storage

logger = logging.getLogger("EngineRouter")

router = APIRouter(prefix="/api", tags=["engine"], dependencies=[Depends(require_api_key)])


@router.get("/status")
def get_status(bot=Depends(get_bot_context)):
    """Get comprehensive bot status including positions, balance, and settings"""
    try:
        # Get current positions
        # Get current positions via Service (Fixes missing attribute issue)
        from app.services.hyperliquid_service import hyperliquid_service
        positions = hyperliquid_service.get_positions()
        
        # Self-healing: Clean ghost trades from bot state
        # If exchange says position is closed but bot still tracks it, clean up
        try:
            exchange_symbols = {p["symbol"] for p in positions if float(p.get("size", 0)) > 0}
            with bot.trade_lock:
                ghost_symbols = [s for s in list(bot.active_trades.keys()) if s not in exchange_symbols]
                for ghost in ghost_symbols:
                    logger.warning(f"🧹 Self-healing: Removing ghost trade {ghost} (not on exchange)")
                    bot.active_trades.pop(ghost, None)
            if ghost_symbols:
                try:
                    from app.core.state_manager import StateManager
                    StateManager.save_state(bot)
                except Exception as save_err:
                    logger.warning(f"Failed to persist state after ghost cleanup: {save_err}")
        except Exception as e:
            logger.warning(f"Self-healing check failed: {e}")
        
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
            "loop_responsive": bot.is_loop_responsive() if hasattr(bot, 'is_loop_responsive') else bot.is_running,
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
    """Restart the trading engine (verified stop + verified start)."""
    try:
        import time

        before_state = {
            "is_running": bool(getattr(bot, "is_running", False)),
            "thread_alive": bool(getattr(bot, "thread", None) and bot.thread.is_alive())
        }

        bot.add_log("🔄 RESTART: Stopping engine...")
        bot.stop()

        # Safeguard: wait for thread termination
        stop_deadline = time.time() + 12
        while time.time() < stop_deadline:
            thread_alive = bool(getattr(bot, "thread", None) and bot.thread.is_alive())
            if not thread_alive:
                break
            time.sleep(0.25)

        still_alive = bool(getattr(bot, "thread", None) and bot.thread.is_alive())
        if still_alive:
            msg = "Restart aborted: trading thread did not stop cleanly"
            bot.add_log(f"❌ RESTART FAILED: {msg}")
            raise HTTPException(status_code=500, detail=msg)

        bot.add_log("🔄 RESTART: Starting engine...")
        bot.start()

        # Safeguard: wait for running + thread alive
        start_deadline = time.time() + 10
        started_ok = False
        while time.time() < start_deadline:
            running = bool(getattr(bot, "is_running", False))
            thread_alive = bool(getattr(bot, "thread", None) and bot.thread.is_alive())
            if running and thread_alive:
                started_ok = True
                break
            time.sleep(0.25)

        if not started_ok:
            msg = "Restart failed: engine did not come back up"
            bot.add_log(f"❌ RESTART FAILED: {msg}")
            raise HTTPException(status_code=500, detail=msg)
        
        # Save state after restart
        try:
            from app.core.state_manager import StateManager
            StateManager.save_state(bot)
        except Exception as e:
            logger.warning(f"Failed to save state after restart: {e}")
        
        return {
            "status": "restarted",
            "message": "Engine restarted successfully",
            "before": before_state,
            "after": {
                "is_running": bool(getattr(bot, "is_running", False)),
                "thread_alive": bool(getattr(bot, "thread", None) and bot.thread.is_alive()),
                "loop_responsive": bool(bot.is_loop_responsive() if hasattr(bot, "is_loop_responsive") else True)
            }
        }
    except Exception as e:
        logger.error(f"Restart failed: {e}")
        raise HTTPException(status_code=500, detail=f"Restart failed: {str(e)}")


@router.post("/engine/reload-config")
def reload_engine_config(bot=Depends(get_bot_context)):
    """
    Reload strategy configuration from disk and rebuild strategy engine instances
    without a full process restart.
    """
    try:
        from strategies.engine import StrategyEngine

        bot.add_log("🔁 RELOAD CONFIG: Rebuilding strategy engine from disk...")
        bot.strategy_engine = StrategyEngine(bot.risk_manager)
        bot.add_log("✅ RELOAD CONFIG: Strategy engine rebuilt successfully")

        loaded = list(bot.strategy_engine.strategies.keys()) if hasattr(bot, "strategy_engine") else []
        return {
            "status": "reloaded",
            "message": "Strategy engine reloaded from latest config",
            "strategies_loaded": loaded
        }
    except Exception as e:
        logger.error(f"Reload config failed: {e}")
        raise HTTPException(status_code=500, detail=f"Reload config failed: {str(e)}")


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
    """
    Update strategy parameters and persist to strategies.json.

    Pipeline:
      1. Validate payload against the per-strategy Pydantic schema (rejects
         unknown keys + enforces type / range). This prevents silent corruption
         of strategies.json by typos like "min_rrr" or "1.5" as string.
      2. Persist validated params to disk (merge into existing params).
      3. Refresh the runtime strategy instance:
           - Reassign strategy.config so self.get_param() returns fresh values
             on the NEXT signal generation (no engine rebuild required).
           - Call strategy.refresh_params() for legacy consumers reading
             self.params directly.
      4. Also refresh the shared engine config dict so regime/type decisions
         stay in sync.
    """
    from app.api.models.strategy_params import (
        validate_strategy_params,
        STRATEGY_PARAM_SCHEMAS,
    )
    from pydantic import ValidationError

    strat_id = data.strategy_id

    # --- 0. Guard: known strategy? ---
    if strat_id not in STRATEGY_PARAM_SCHEMAS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown strategy id '{strat_id}'. Known: {sorted(STRATEGY_PARAM_SCHEMAS.keys())}",
        )

    if not hasattr(bot, "strategy_engine") or strat_id not in bot.strategy_engine.strategies:
        raise HTTPException(status_code=404, detail=f"Strategy {strat_id} not found in runtime engine")

    # --- 1. Validate ---
    try:
        clean_params = validate_strategy_params(strat_id, data.params or {})
    except ValidationError as ve:
        logger.warning(f"Strategy params validation failed for {strat_id}: {ve}")
        raise HTTPException(status_code=422, detail={"validation_errors": ve.errors()})
    except KeyError as ke:
        raise HTTPException(status_code=400, detail=str(ke))

    if not clean_params:
        return {
            "status": "noop",
            "message": f"No valid params provided for {strat_id}",
            "applied": {},
        }

    try:
        strategy = bot.strategy_engine.strategies[strat_id]

        # --- 2. Persist to strategies.json (merge) ---
        full_config = storage.storage_service.load_strategies()
        if strat_id not in full_config:
            full_config[strat_id] = {}
        if "params" not in full_config[strat_id]:
            full_config[strat_id]["params"] = {}
        full_config[strat_id]["params"].update(clean_params)

        persisted = storage.storage_service.save_strategies(full_config)
        if not persisted:
            raise HTTPException(status_code=500, detail="Failed to persist strategies.json")

        # --- 3. Refresh runtime strategy config ---
        # Reassign whole config object so get_param() sees the new values
        # without touching cached attributes.
        strategy.config = full_config[strat_id]
        if hasattr(strategy, "refresh_params"):
            try:
                strategy.refresh_params()
            except Exception as e:
                logger.warning(f"refresh_params() failed for {strat_id}: {e}")

        # --- 4. Keep engine-level config in sync ---
        try:
            if hasattr(bot.strategy_engine, "config") and isinstance(bot.strategy_engine.config, dict):
                bot.strategy_engine.config[strat_id] = full_config[strat_id]
        except Exception as e:
            logger.warning(f"Engine config refresh failed for {strat_id}: {e}")

        bot.add_log(f"⚙️ Strategy Params Updated: {strat_id} | keys={list(clean_params.keys())}")
        return {
            "status": "success",
            "message": f"Parameters updated for {strat_id}",
            "applied": clean_params,
            "strategy_config": full_config[strat_id].get("params", {}),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating strategy params: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/strategies-config")
def get_strategies_config():
    """Return full strategies configuration from persistent storage."""
    try:
        return storage.storage_service.load_strategies()
    except Exception as e:
        logger.error(f"Error loading strategies config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/strategy-params-schema")
def get_strategy_params_schema(strategy_id: str | None = None):
    """
    Return the JSON Schema for strategy params.

    - If strategy_id is provided: returns a single schema.
    - Otherwise: returns a dict {strategy_id -> schema}.
    Useful for the frontend to auto-generate typed/range-checked inputs
    that mirror the server-side validation.
    """
    from app.api.models.strategy_params import STRATEGY_PARAM_SCHEMAS

    try:
        if strategy_id:
            if strategy_id not in STRATEGY_PARAM_SCHEMAS:
                raise HTTPException(
                    status_code=404,
                    detail=f"Unknown strategy id '{strategy_id}'. Known: {sorted(STRATEGY_PARAM_SCHEMAS.keys())}",
                )
            return STRATEGY_PARAM_SCHEMAS[strategy_id].model_json_schema()
        return {sid: cls.model_json_schema() for sid, cls in STRATEGY_PARAM_SCHEMAS.items()}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exposing strategy params schema: {e}")
        raise HTTPException(status_code=500, detail=str(e))


