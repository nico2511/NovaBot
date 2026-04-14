"""
Trading Router - Trading Operations Endpoints
Handles enable/disable trading, symbol switching, position management
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.api.dependencies import get_bot_context
import logging

logger = logging.getLogger("TradingRouter")

router = APIRouter(prefix="/api", tags=["trading"])



# Request models
class SwitchSymbolRequest(BaseModel):
    symbol: str

class ClosePositionRequest(BaseModel):
    symbol: str

class TradeActionRequest(BaseModel):
    symbol: str = None
    action: str = None


@router.post("/trading/enable")
def enable_trading(bot=Depends(get_bot_context)):
    """Enable live trading"""
    try:
        bot.trading_enabled = True
        bot.add_log("✅ TRADING ENABLED via API")
        
        # Save state
        try:
            from app.core.state_manager import StateManager
            StateManager.save_state(bot)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")
        
        return {"status": "enabled", "message": "Trading enabled successfully"}
    except Exception as e:
        logger.error(f"Error enabling trading: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to enable trading: {str(e)}")


@router.post("/trading/disable")
def disable_trading(bot=Depends(get_bot_context)):
    """Disable live trading"""
    try:
        bot.trading_enabled = False
        bot.add_log("⛔ TRADING DISABLED via API")
        
        # Save state
        try:
            from app.core.state_manager import StateManager
            StateManager.save_state(bot)
        except Exception as e:
            logger.warning(f"Failed to save state: {e}")
        
        return {"status": "disabled", "message": "Trading disabled successfully"}
    except Exception as e:
        logger.error(f"Error disabling trading: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to disable trading: {str(e)}")


@router.post("/switch_symbol")
def switch_symbol(data: SwitchSymbolRequest, bot=Depends(get_bot_context)):
    """Switch active trading symbol."""
    new_symbol = data.symbol.upper().strip()
    if not new_symbol:
        raise HTTPException(status_code=400, detail="Missing 'symbol' in request body")
    
    # Validate symbol exists on Hyperliquid
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        meta = hyperliquid_service._fetch_metadata()
        if meta:
            universe = [a["name"] for a in meta.get("universe", [])]
            if new_symbol not in universe and f"k{new_symbol}" not in universe:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Symbol {new_symbol} not found on Hyperliquid"
                )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"⚠️ Symbol validation failed: {e}")
    
    # Switch symbol
    try:
        old_symbol = bot.active_symbol
        bot.switch_active_symbol(new_symbol)
        
        return {
            "status": "success",
            "message": f"Symbol switched to {new_symbol}",
            "old_symbol": old_symbol,
            "new_symbol": new_symbol
        }
    except Exception as e:
        logger.error(f"Failed to switch symbol: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to switch symbol: {str(e)}")


@router.post("/close_position")
def close_position(data: ClosePositionRequest, bot=Depends(get_bot_context)):
    """Close a specific position by symbol"""
    symbol = data.symbol.upper().strip()
    
    if not symbol:
        raise HTTPException(status_code=400, detail="Missing 'symbol' in request body")
    
    try:
        bot.add_log(f"🔒 API Request: Closing position {symbol}...")
        result = bot.execute_exit_atomically(symbol, reason="API Request")
        
        if result:
            return { "status": "success", "message": f"Position closed for {symbol}" }
        else:
            raise HTTPException(status_code=500, detail="Failed to close position (check logs)")

    except Exception as e:
        logger.error(f"Error closing position {symbol}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to close position: {str(e)}")


@router.post("/positions")
def get_positions_post(bot=Depends(get_bot_context)):
    """Alternate POST endpoint for positions (Legacy compatibility)"""
    return get_positions(bot)


@router.get("/positions")
def get_positions(bot=Depends(get_bot_context)):
    """Get all open positions"""
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        positions = hyperliquid_service.get_positions()
        return {"positions": positions}
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch positions: {str(e)}")


@router.get("/balance")
def get_balance(bot=Depends(get_bot_context)):
    """Get account balance and margin info"""
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        
        # Use cached value if available in bot
        if hasattr(bot, 'account_value') and bot.account_value > 0:
            return {"account_value": bot.account_value}

        # Fetch fresh
        balance_data = hyperliquid_service.get_account_balance()
        if balance_data.get("status") == "success":
             return balance_data
        
        return {"account_value": 0.0}

    except Exception as e:
        logger.error(f"Error fetching balance: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch balance: {str(e)}")

# --- MISSING ENDPOINTS RESTORED ---

@router.post("/force_sync")
def force_sync(bot=Depends(get_bot_context)):
    """Force synchronization with exchange"""
    try:
        result = bot.force_sync()
        return result
    except Exception as e:
        logger.error(f"Error forcing sync: {e}")
        raise HTTPException(status_code=500, detail=f"Force sync failed: {str(e)}")

class SymbolRequest(BaseModel):
    symbol: Optional[str] = None

@router.post("/force_breakeven")
def force_breakeven(data: SymbolRequest, bot=Depends(get_bot_context)):
    """Force move SL to Break-Even for specified symbol or active trade"""
    try:
        # Determine target symbol and canonicalize (e.g. BTC-PERP -> BTC)
        raw_symbol = data.symbol if data.symbol else bot.active_symbol
        symbol = bot.get_canonical_symbol(raw_symbol)
        
        bot.add_log(f"🔍 Force BE requested for {raw_symbol} (Resolved: {symbol})")
        
        # Get trade for this symbol
        trade = bot.active_trades.get(symbol)
        if not trade:
            # Try fuzzy match if exact match fails
            if "-" in symbol:
                base = symbol.split("-")[0]
                trade = bot.active_trades.get(base)
                if trade:
                    symbol = base
                    bot.add_log(f"ℹ️ Fuzzy match found: {raw_symbol} -> {symbol}")
            
            if not trade:
                return {"status": "error", "message": f"No active trade for {symbol}"}
        
        entry = trade.get("entry")
        side = trade.get("side")
        
        if not entry:
            return {"status": "error", "message": "Trade has no entry price"}

        # Calculate BE price with slight buffer
        be_price = entry * 1.002 if side == "BUY" else entry * 0.998
        
        # Update local state
        with bot.trade_lock:
            trade["sl"] = be_price
            from app.core.state_manager import StateManager
            StateManager.save_state(bot)
        
        # Enforce
        bot._verify_and_enforce_sl_tp(symbol, trade, bypass_cooldown=True)
        bot.add_log(f"🛡️ Force BE executed for {symbol}: SL -> {be_price:.4f}")
        
        return {"status": "success", "message": f"Moved SL to {be_price:.4f} for {symbol}"}
        
    except Exception as e:
        logger.error(f"Error forcing BE: {e}")
        raise HTTPException(status_code=500, detail=f"Force BE failed: {str(e)}")

@router.post("/recalibrate_stops")
def recalibrate_stops(data: SymbolRequest, bot=Depends(get_bot_context)):
    """Recalibrate SL/TP for specified symbol or active trade"""
    try:
        # Determine target symbol
        symbol = data.symbol if data.symbol else bot.active_symbol
        
        # Get trade for this symbol
        trade = bot.active_trades.get(symbol)
        if not trade:
            return {"status": "error", "message": f"No active trade for {symbol}"}
        
        bot._verify_and_enforce_sl_tp(symbol, trade, bypass_cooldown=True)
        bot.add_log(f"🔧 Recalibrated SL/TP for {symbol}")
        return {"status": "success", "message": f"SL/TP recalibrated for {symbol}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/close_trade")
def close_trade(data: SymbolRequest, bot=Depends(get_bot_context)):
    """Close specified trade or active trade"""
    try:
        # Determine target symbol
        symbol = data.symbol if data.symbol else bot.active_symbol
        
        if not symbol:
            return {"status": "error", "message": "No symbol specified"}
        
        # execute_exit_atomically will validate position exists
        res = bot.execute_exit_atomically(symbol, reason="Manual Close (API)")
        if res:
            return {"status": "success", "message": f"Trade closed for {symbol}"}
        else:
            return {"status": "error", "message": f"Failed to close {symbol}"}
    except Exception as e:
        logger.error(f"Close trade failed: {e}")
        return {"status": "error", "message": str(e)}
