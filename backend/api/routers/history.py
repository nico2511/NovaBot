"""
History Router - Trade History & Logs Endpoints
Handles exchange fills, bot trade history, and logs retrieval
"""
import os
import time
import logging
import pandas as pd
from typing import Union
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from backend.api.dependencies import get_bot_context
from app.core.trade_recorder import TradeRecorder

logger = logging.getLogger("HistoryRouter")

router = APIRouter(prefix="/api/history", tags=["history"])
logs_router = APIRouter(prefix="/api", tags=["logs"])  # For backward compatibility


# ==========================================
# EXCHANGE HISTORY (Hyperliquid API)
# ==========================================

_exchange_fills_cache = {
    "data": [],
    "timestamp": 0
}
EXCHANGE_CACHE_DURATION = 60  # 60 seconds

@router.get("/fills")
def get_exchange_fills(limit: int = 100):
    """
    Get ALL fills from Hyperliquid exchange.
    Includes manual trades, bot trades, etc.
    """
    global _exchange_fills_cache
    current_time = time.time()
    
    # Return cached data if valid
    if current_time - _exchange_fills_cache["timestamp"] < EXCHANGE_CACHE_DURATION and _exchange_fills_cache["data"]:
        return {"source": "hyperliquid", "trades": _exchange_fills_cache["data"], "cached": True}

    try:
        from app.services.hyperliquid_service import hyperliquid_service
        
        logger.info(f"📊 Fetching fills from Hyperliquid API (limit={limit})...")
        trades = hyperliquid_service.get_trade_history(limit=limit)
        
        if trades:
            _exchange_fills_cache["data"] = trades
            _exchange_fills_cache["timestamp"] = current_time
            
        return {"source": "hyperliquid", "trades": trades, "count": len(trades), "cached": False}
    except Exception as e:
        logger.error(f"❌ Error fetching Hyperliquid fills: {e}")
        if _exchange_fills_cache["data"]:
            return {"source": "hyperliquid", "trades": _exchange_fills_cache["data"], "cached": True, "stale": True}
        return {"source": "hyperliquid", "trades": [], "error": str(e)}



# ==========================================
# EQUITY HISTORY
# ==========================================

@router.get("/equity")
def get_equity_history(limit: int = 168): # Default to 1 week of hourly data
    """
    Get equity history for performance charting.
    Combines daily PnL snapshots with current equity.
    """
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        from backend.services.storage import storage_service
        
        # 1. Load snapshots from storage
        snapshots = storage_service.load_pnl_snapshot()
        history = []
        
        # 2. Parse snapshots into format {time: timestamp, value: equity}
        if snapshots:
            # Sort dates to ensure chronological order
            sorted_dates = sorted(snapshots.keys())
            for date_str in sorted_dates:
                data = snapshots[date_str]
                try:
                    ts = int(pd.Timestamp(data.get("timestamp", date_str)).timestamp())
                    history.append({
                        "time": ts,
                        "value": float(data.get("start_value", 0))
                    })
                except: continue
        
        # 3. Add current equity as the latest point
        try:
            balance_info = hyperliquid_service.get_account_balance()
            current_equity = balance_info.get("total_equity", 0)
            if current_equity > 0:
                history.append({
                    "time": int(time.time()),
                    "value": float(current_equity)
                })
        except: pass
        
        # 4. Fallback if empty
        if not history:
            history = [
                {"time": int(time.time()) - 86400, "value": 0},
                {"time": int(time.time()), "value": 0}
            ]
            
        return history
        
    except Exception as e:
        logger.error(f"❌ Error fetching equity history: {e}")
        return []


# ==========================================
# BOT TRADE RECORDER (Local CSV)
# ==========================================

@router.get("/bot/trades")
def get_bot_trades(limit: int = 50, bot=Depends(get_bot_context)):
    """
    Get trades executed BY THE BOT only.
    Source: Local CSV (data/state/trade_history.csv)
    """
    try:
        # Try to use bot instance recorder
        if hasattr(bot, 'trade_recorder'):
            trades = bot.trade_recorder.get_history(limit)
            return {"source": "bot_recorder", "trades": trades, "count": len(trades)}
        
        # Fallback: Direct read
        recorder = TradeRecorder()
        trades = recorder.get_history(limit)
        return {"source": "bot_recorder", "trades": trades, "count": len(trades)}
    except Exception as e:
        logger.error(f"❌ Error fetching bot trades: {e}")
        return {"source": "bot_recorder", "trades": [], "error": str(e)}


@router.get("/bot/trades/stats")
def get_bot_trades_stats(bot=Depends(get_bot_context)):
    """
    Get aggregated performance stats from bot's trade history.
    """
    try:
        if hasattr(bot, 'trade_recorder'):
            stats = bot.trade_recorder.get_stats()
            return {"source": "bot_recorder", "stats": stats}
        
        recorder = TradeRecorder()
        stats = recorder.get_stats()
        return {"source": "bot_recorder", "stats": stats}
    except Exception as e:
        logger.error(f"❌ Error fetching bot stats: {e}")
        return {"source": "bot_recorder", "stats": {}, "error": str(e)}


@router.get("/bot/trades/download")
def download_bot_trades():
    """Download bot's trade history as CSV file"""
    csv_path = "data/state/trade_history.csv"
    if not os.path.exists(csv_path):
        csv_path = "data/trade_history.csv"
    
    if os.path.exists(csv_path):
        return FileResponse(csv_path, filename="bot_trade_history.csv", media_type="text/csv")
    else:
        return {"error": "No trade history file found"}


# ==========================================
# LOGS (Separate router for /api/logs)
# ==========================================

@logs_router.get("/logs")
def get_logs(limit: int = 50, bot=Depends(get_bot_context)):
    """Get recent logs with structured format"""
    
    def parse_log_entry(log_entry: Union[str, dict]) -> dict:
        if isinstance(log_entry, dict):
            if "level" not in log_entry:
                msg_upper = log_entry.get("message", "").upper()
                if "ERROR" in msg_upper or "❌" in msg_upper: log_entry["level"] = "ERROR"
                elif "WARNING" in msg_upper or "⚠️" in msg_upper: log_entry["level"] = "WARNING"
                elif "SUCCESS" in msg_upper or "✅" in msg_upper: log_entry["level"] = "SUCCESS"
                elif "SIGNAL" in msg_upper: log_entry["level"] = "SIGNAL"
                else: log_entry["level"] = "INFO"
            return log_entry

        log_line = str(log_entry)
        result = {
            "timestamp": "",
            "level": "INFO",
            "message": log_line,
            "metadata": None
        }
        
        parts = log_line.split(" ", 1)
        if len(parts) >= 2:
            result["timestamp"] = parts[0]
            remaining = parts[1]
        else:
            remaining = log_line
        
        remaining_upper = remaining.upper()
        if "ERROR" in remaining_upper or "❌" in remaining: result["level"] = "ERROR"
        elif "WARNING" in remaining_upper or "⚠️" in remaining: result["level"] = "WARNING"
        elif "SUCCESS" in remaining_upper or "✅" in remaining: result["level"] = "SUCCESS"
        elif "SIGNAL" in remaining_upper: result["level"] = "SIGNAL"
        elif "TRADE" in remaining_upper: result["level"] = "TRADE"
        
        result["message"] = remaining
        return result
    
    try:
        total = len(bot.logs) if hasattr(bot, 'logs') else 0
        raw_logs = list(bot.logs)[-limit:] if hasattr(bot, 'logs') else []
        logs = [parse_log_entry(l) for l in raw_logs]
        return {
            "logs": logs[::-1],  # Newest first
            "total": total
        }
    except Exception as e:
        logger.error(f"Error fetching logs: {e}")
        return {"logs": [], "total": 0}


@logs_router.get("/sentiment-history")
def get_sentiment_history():
    """Get market sentiment analysis history"""
    try:
        from backend.services.storage import storage_service
        data = storage_service.load_sentiment_history()
        # Ensure it returns an array
        if isinstance(data, dict):
            return data.get("history", []) if "history" in data else []
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Error fetching sentiment history: {e}")
        return []


@logs_router.get("/signal-analysis")
def get_signal_analysis():
    """Get signal analysis decision history"""
    try:
        from backend.services.storage import storage_service
        data = storage_service.load_signal_analysis()
        # Ensure it returns an array
        if isinstance(data, dict):
            return data.get("signals", []) if "signals" in data else []
        return data if isinstance(data, list) else []
    except Exception as e:
        logger.error(f"Error fetching signal analysis: {e}")
        return []


@logs_router.get("/signal-analysis/download")
def download_signal_analysis():
    """Download signal analysis JSON file"""
    try:
        from backend.services.storage import storage_service
        import json
        
        file_path = storage_service.analysis_dir / "signal_analysis.json"
        
        # Create empty file if not exists
        if not file_path.exists():
            logger.info("ℹ️ Signal analysis file not found, creating empty one for download.")
            try:
                # Ensure parent dir exists
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "w", encoding='utf-8') as f:
                    json.dump([], f)
            except Exception as e:
                logger.error(f"Failed to create empty signal analysis file: {e}")
                # Fallback to 404 if we can't create it
                raise HTTPException(status_code=404, detail="Signal analysis file not found and could not be created")
        
        return FileResponse(
            path=str(file_path),
            filename="signal_analysis.json",
            media_type="application/json"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading signal analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@logs_router.get("/sentiment-history/download")
def download_sentiment_history():
    """Download sentiment history JSON file"""
    try:
        from backend.services.storage import storage_service
        import json
        
        file_path = storage_service.analysis_dir / "sentiment_history.json"
        
        # Create empty file if not exists
        if not file_path.exists():
            logger.info("ℹ️ Sentiment history file not found, creating empty one for download.")
            try:
                # Ensure parent dir exists
                file_path.parent.mkdir(parents=True, exist_ok=True)
                with open(file_path, "w", encoding='utf-8') as f:
                    json.dump([], f)
            except Exception as e:
                logger.error(f"Failed to create empty sentiment history file: {e}")
                # Fallback to 404 if we can't create it
                raise HTTPException(status_code=404, detail="Sentiment history file not found and could not be created")
        
        return FileResponse(
            path=str(file_path),
            filename="sentiment_history.json",
            media_type="application/json"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading sentiment history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
