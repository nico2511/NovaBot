"""
Engine Router - Bot Engine Control Endpoints
Handles start, stop, restart, panic, and status operations
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from app.api.dependencies import get_bot_context
from pydantic import BaseModel
import logging
import pandas as pd
from app.services import storage

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
        
        # Self-healing: Clean ghost trades from bot state
        # If exchange says position is closed but bot still tracks it, clean up
        try:
            exchange_symbols = {p["symbol"] for p in positions if float(p.get("size", 0)) > 0}
            ghost_symbols = [s for s in list(bot.active_trades.keys()) if s not in exchange_symbols]
            if ghost_symbols:
                for ghost in ghost_symbols:
                    logger.warning(f"🧹 Self-healing: Removing ghost trade {ghost} (not on exchange)")
                    bot.active_trades.pop(ghost, None)
                try:
                    from app.core.state_manager import StateManager
                    StateManager.save_state(bot)
                except Exception:
                    pass
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


@router.get("/config/strategies-config")
def get_strategies_config():
    """Return full strategies configuration from persistent storage."""
    try:
        return storage.storage_service.load_strategies()
    except Exception as e:
        logger.error(f"Error loading strategies config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calibration", response_class=HTMLResponse)
def calibration_page():
    """Simple built-in calibration page for strategy params tuning."""
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>NovaBot Calibration</title>
  <style>
    :root { --bg:#f6f7f9; --card:#ffffff; --text:#1b1f24; --muted:#68707a; --ok:#0b6bcb; --line:#d9dee6; }
    body { margin:0; background:var(--bg); color:var(--text); font-family: "Segoe UI", Tahoma, sans-serif; }
    .wrap { max-width: 1100px; margin: 20px auto; padding: 0 12px; }
    h1 { margin: 0 0 6px; font-size: 28px; }
    .sub { color: var(--muted); margin-bottom: 14px; }
    .toolbar { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px; }
    button { border:1px solid var(--line); background:var(--card); padding:8px 12px; border-radius:8px; cursor:pointer; }
    button.primary { background:var(--ok); color:#fff; border-color:var(--ok); }
    .grid { display:grid; gap:12px; grid-template-columns: repeat(auto-fill, minmax(320px,1fr)); }
    .card { background:var(--card); border:1px solid var(--line); border-radius:12px; padding:12px; }
    .name { font-size:18px; font-weight:700; margin-bottom:4px; }
    .meta { color:var(--muted); font-size:12px; margin-bottom:10px; }
    .rows { display:grid; gap:8px; }
    .row { display:grid; grid-template-columns: 1fr 120px; gap:8px; align-items:center; }
    .row label { font-size:13px; color:#2f3742; }
    .row input { width:100%; box-sizing:border-box; border:1px solid var(--line); border-radius:8px; padding:7px; }
    .status { margin-top: 10px; font-size: 12px; color: var(--muted); min-height: 14px; }
  </style>
</head>
<body>
  <div class="wrap">
    <h1>Strategy Calibration</h1>
    <div class="sub">Tune numeric params, save per strategy, then restart engine if needed.</div>
    <div class="toolbar">
      <button id="reloadBtn">Reload Config</button>
      <button class="primary" id="saveAllBtn">Save All Edited Strategies</button>
      <button id="restartBtn">Restart Engine</button>
    </div>
    <div id="grid" class="grid"></div>
  </div>
  <script>
    const grid = document.getElementById("grid");
    let config = {};
    const dirty = new Set();

    const isNumeric = (v) => typeof v === "number" && Number.isFinite(v);
    const parseMaybeNumber = (txt, current) => {
      if (typeof current === "boolean") return txt === "true";
      if (typeof current === "number") {
        const n = Number(txt);
        return Number.isFinite(n) ? n : current;
      }
      return txt;
    };

    async function fetchConfig() {
      const r = await fetch("/api/config/strategies-config");
      if (!r.ok) throw new Error(await r.text());
      return await r.json();
    }

    async function saveStrategy(strategyId) {
      const card = document.querySelector(`[data-strategy='${strategyId}']`);
      if (!card) return;
      const params = {};
      const original = config[strategyId]?.params || {};
      card.querySelectorAll("input[data-param]").forEach(inp => {
        const key = inp.getAttribute("data-param");
        params[key] = parseMaybeNumber(inp.value, original[key]);
      });
      const res = await fetch("/api/config/strategy-params", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy_id: strategyId, params })
      });
      if (!res.ok) throw new Error(await res.text());
      dirty.delete(strategyId);
      card.querySelector(".status").textContent = "Saved";
    }

    function render() {
      grid.innerHTML = "";
      Object.entries(config).forEach(([name, cfg]) => {
        if (!cfg || typeof cfg !== "object" || !cfg.params) return;
        const card = document.createElement("div");
        card.className = "card";
        card.setAttribute("data-strategy", name);
        const rows = Object.entries(cfg.params)
          .map(([k,v]) => `<div class="row"><label>${k}</label><input data-param="${k}" value="${String(v)}"></div>`)
          .join("");
        card.innerHTML = `
          <div class="name">${name}</div>
          <div class="meta">type=${cfg.type || "n/a"} | enabled=${cfg.enabled ? "true":"false"}</div>
          <div class="rows">${rows}</div>
          <div class="toolbar" style="margin-top:10px;">
            <button class="primary" data-save="${name}">Save ${name}</button>
          </div>
          <div class="status"></div>
        `;
        card.querySelectorAll("input[data-param]").forEach(inp => {
          inp.addEventListener("input", () => {
            dirty.add(name);
            card.querySelector(".status").textContent = "Edited (not saved)";
          });
        });
        card.querySelector(`[data-save='${name}']`).addEventListener("click", async () => {
          try { await saveStrategy(name); }
          catch (e) { card.querySelector(".status").textContent = "Error: " + e.message; }
        });
        grid.appendChild(card);
      });
    }

    async function reload() {
      config = await fetchConfig();
      dirty.clear();
      render();
    }

    document.getElementById("reloadBtn").addEventListener("click", async () => {
      try { await reload(); } catch (e) { alert("Reload failed: " + e.message); }
    });

    document.getElementById("saveAllBtn").addEventListener("click", async () => {
      const targets = Array.from(dirty);
      for (const s of targets) {
        try { await saveStrategy(s); } catch (e) { console.error(s, e); }
      }
      if (targets.length === 0) alert("No edited strategy to save.");
    });

    document.getElementById("restartBtn").addEventListener("click", async () => {
      const r = await fetch("/api/engine/restart", { method: "POST" });
      if (!r.ok) alert("Restart failed");
      else alert("Engine restart requested.");
    });

    reload().catch(e => alert("Init failed: " + e.message));
  </script>
</body>
</html>
"""
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
