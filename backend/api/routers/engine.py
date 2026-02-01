"""
Engine Router - Bot Engine Control Endpoints
Handles start, stop, restart, panic, and status operations
"""
from fastapi import APIRouter, Depends, HTTPException
from backend.api.dependencies import get_bot_context
from pydantic import BaseModel
import logging

logger = logging.getLogger("EngineRouter")

router = APIRouter(prefix="/api", tags=["engine"])


@router.get("/status")
def get_status(bot=Depends(get_bot_context)):
    """Get comprehensive bot status including positions, balance, and settings"""
    try:
        # Get current positions
        positions = []
        if hasattr(bot, 'hyperliquid') and bot.hyperliquid:
            try:
                user_state = bot.hyperliquid.info.user_state(bot.hyperliquid.account_address)
                asset_positions = user_state.get("assetPositions", [])
                
                for pos in asset_positions:
                    position_data = pos.get("position", {})
                    coin = position_data.get("coin", "UNKNOWN")
                    szi = position_data.get("szi", "0")
                    entry_px = position_data.get("entryPx")
                    
                    if float(szi) != 0:
                        positions.append({
                            "symbol": coin,
                            "size": float(szi),
                            "side": "LONG" if float(szi) > 0 else "SHORT",
                            "entry_price": float(entry_px) if entry_px else 0,
                            "unrealized_pnl": float(position_data.get("unrealizedPnl", 0)),
                            "leverage": float(position_data.get("leverage", {}).get("value", 1))
                        })
            except Exception as e:
                logger.error(f"Error fetching positions: {e}")
        
        # Get account balance
        balance = 0.0
        if hasattr(bot, 'hyperliquid') and bot.hyperliquid:
            try:
                user_state = bot.hyperliquid.info.user_state(bot.hyperliquid.account_address)
                margin_summary = user_state.get("marginSummary", {})
                balance = float(margin_summary.get("accountValue", 0))
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
                "daily_stop_loss": bot.global_settings.get("daily_stop_loss", 0),
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
        import json
        from pathlib import Path
        
        # Load strategy metadata from strategies.json
        config_path = Path("data/config/strategies.json")
        strategy_metadata = {}
        
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                strategy_metadata = config.get("strategies", {})
        
        strategies = []
        if hasattr(bot, 'strategy_engine'):
            for name, strategy in bot.strategy_engine.strategies.items():
                # Get metadata from strategies.json
                meta = strategy_metadata.get(name, {})
                
                strategies.append({
                    "id": name,
                    "name": name,
                    "enabled": meta.get("enabled", True),
                    "type": meta.get("type", "unknown").upper(),
                    "description": meta.get("description", "No description")
                })
        return strategies
    except Exception as e:
        logger.error(f"Error fetching strategies: {e}")
        return []


class StrategySelectRequest(BaseModel):
    strategy_id: str

@router.post("/config/strategy-select")
def select_strategy(data: StrategySelectRequest, bot=Depends(get_bot_context)):
    """Select active strategy"""
    try:
        strat_id = data.strategy_id
        if hasattr(bot, 'strategy_engine') and strat_id in bot.strategy_engine.strategies:
            bot.active_strategy_name = strat_id
            bot.add_log(f"🧠 Strategy Switched: {strat_id}")
            return {
                "status": "success",
                "message": f"Strategy switched to {strat_id}",
                "active_strategy": strat_id
            }
        else:
            raise HTTPException(status_code=404, detail=f"Strategy {strat_id} not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error selecting strategy: {e}")
        raise HTTPException(status_code=500, detail=str(e))
