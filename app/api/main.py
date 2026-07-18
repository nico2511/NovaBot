"""
Main FastAPI Application - Modular Router Architecture
Registers all routers and handles startup/shutdown events
"""
import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.routing import APIRoute

# Setup paths
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(ROOT) # Point to project root (parent of backend/)
if ROOT not in sys.path:
    sys.path.append(ROOT)

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MainApp")

# Import routers
from app.api.routers import engine, trading, market, settings, history

# Settings Watcher
from app.services.settings_watcher import SettingsWatcher
settings_watcher = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app.
    Handles startup and shutdown events resource management.
    """
    # --- STARTUP ---
    logger.info("🚀 API Startup: Initializing services...")

    try:
        from app.utils.discord_log_handler import install_discord_alert_handler
        install_discord_alert_handler(level=logging.WARNING)
        logger.info("✅ Discord alert handler attached (WARNING+)")
    except Exception as e:
        logger.warning("⚠️ Discord alert handler not installed: %s", e)
    
    # 1. Initialize Storage Service
    try:
        from app.services.storage import init_storage
        ss = init_storage(BASE_DIR)
        # Auto-sync runtime strategies config with versioned defaults (non-destructive)
        if ss:
            ss.sync_strategies_from_defaults()
        logger.info("✅ Storage service initialized")
    except Exception as e:
        logger.error(f"❌ Storage service initialization failed: {e}")
    
    # 2. Initialize Bot Bridge
    try:
        from app.services.internal.bridge import bot_bridge
        logger.info("✅ Bot bridge available")
        if bot_bridge.is_connected():
            logger.info("✅ Bot already connected via bridge")
        else:
            logger.warning("⚠️ Bot not connected - live endpoints will return 503")
    except ImportError:
        logger.warning("⚠️ Bot bridge not available - running without bot connection")
    except Exception as e:
        logger.error(f"❌ Bot bridge initialization error: {e}")
    
    # 3. Initialize Settings Watcher (Hot Reload)
    global settings_watcher
    try:
        config_path = os.path.join(BASE_DIR, "data", "config", "user_settings.json")
        from pathlib import Path
        
        def on_settings_change(new_settings: dict):
            logger.info("🔄 Hot-Reloading Settings...")
            try:
                from app.services.internal.bridge import bot_bridge
                if bot_bridge and bot_bridge.is_connected():
                    bot = bot_bridge.get_bot_context()
                    
                    # Update Global Settings
                    if "risk_defaults" in new_settings or "operations" in new_settings:
                        bot.global_settings = new_settings
                        bot.add_log("⚙️ HOT-RELOAD: Global Settings updated from file")
                        
                        # Trigger Leverage Re-sync in Bot Loop
                        bot._leverage_synced = False
                        bot.add_log("🔄 HOT-RELOAD: Triggering leverage re-sync...")
                        
                        # Refresh Discord Webhooks
                        notif = new_settings.get("notifications", {})
                        if notif:
                            from app.services.discord_service import discord_service
                            discord_service.refresh_webhooks(
                                alert_url=notif.get("discord_webhook_alerts"),
                                log_url=notif.get("discord_webhook_logs")
                            )
                            bot.add_log("🔔 HOT-RELOAD: Discord webhooks refreshed")

                    # Update Scanner Settings
                    if "scanner" in new_settings:
                        bot.scanner_settings = new_settings["scanner"]
                        bot.add_log("🕵️ HOT-RELOAD: Scanner Settings updated from file")
                    
                    # Save state
                    from app.core.state_manager import StateManager
                    StateManager.save_state(bot)
            except Exception as e:
                logger.error(f"Error during hot-reload callback: {e}")
                
        settings_watcher = SettingsWatcher(Path(config_path), on_settings_change)
        settings_watcher.start()
        logger.info("✅ Settings Watcher initialized")
        
    except Exception as e:
        logger.error(f"❌ Settings Watcher initialization failed: {e}")

    logger.info("🎉 API Startup Complete!")
    
    yield
    
    # --- SHUTDOWN ---
    logger.info("🛑 API Shutdown: Cleaning up...")
    
    # Stop Settings Watcher
    if settings_watcher:
        settings_watcher.stop()
        logger.info("✅ Settings Watcher stopped")
    
    # Save final state if bot is connected
    try:
        from app.services.internal.bridge import bot_bridge
        if bot_bridge and bot_bridge.is_connected():
            bot = bot_bridge.get_bot_context()
            from app.core.state_manager import StateManager
            StateManager.save_state(bot)
            logger.info("✅ Final state saved")
    except Exception as e:
        logger.warning(f"⚠️ Failed to save final state: {e}")
    
    logger.info("👋 API Shutdown Complete!")

# Create FastAPI app
app = FastAPI(
    title="NovaBot Trading API",
    version="2.0",
    description="Modular FastAPI backend for HyperLiquid trading bot",
    lifespan=lifespan
)

# CORS middleware: origins come from the CORS_ALLOWED_ORIGINS env var (comma-separated).
# Default targets only local frontends. Setting it to "*" keeps the old behavior but is
# incompatible with allow_credentials=True (browsers reject that combo), so we flip
# allow_credentials off in that case to avoid subtle frontend bugs.
from app.core.config import config as _app_config

_cors_origins = _app_config.CORS_ALLOWED_ORIGINS or ["http://localhost:3000"]
_allow_wildcard = "*" in _cors_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=not _allow_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)
logger.info(f"🌐 CORS allowed origins: {_cors_origins}")
if _app_config.API_KEY_REQUIRED:
    logger.info("🔒 API key authentication ENABLED (X-API-Key header required)")
else:
    logger.warning("🔓 API key authentication DISABLED (set API_KEY_REQUIRED=true in production)")

# Register routers
app.include_router(engine.router)
app.include_router(trading.router)
app.include_router(market.router)
app.include_router(settings.router)
app.include_router(history.router)
app.include_router(history.logs_router)  # Logs at /api/logs

logger.info("✅ Routers registered: engine, trading, market, settings, history, logs")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Report unhandled API errors to logs + Discord."""
    logger.exception("Unhandled API error on %s %s", request.method, request.url.path)
    try:
        from app.services.discord_service import discord_service
        discord_service.notify(
            "ERROR",
            "API",
            f"{request.method} {request.url.path}\n\n{type(exc).__name__}: {exc}",
            source="api",
        )
    except Exception:
        pass
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------
# Serves a lightweight HTML index when a browser hits "/" (Accept: text/html),
# and the historical JSON payload for API clients / tests (Accept: */* or
# application/json). No frontend framework, no CDN, pure inline HTML/CSS.

def _collect_endpoints():
    """Group registered APIRoutes by first path segment (router family)."""
    groups: dict[str, list[dict]] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = sorted(m for m in (route.methods or set()) if m != "HEAD")
        if not methods:
            continue
        path = route.path
        # Skip FastAPI's own schema endpoints (already linked explicitly).
        if path in ("/openapi.json",):
            continue
        parts = [p for p in path.split("/") if p]
        if not parts:
            group = "root"
        elif parts[0] == "api" and len(parts) >= 2:
            group = parts[1]
        else:
            group = parts[0]
        groups.setdefault(group, []).append({
            "path": path,
            "methods": methods,
            "summary": (route.summary or route.name or "").strip(),
            "auth": any(
                getattr(dep, "call", None).__name__ == "require_api_key"
                for dep in (route.dependant.dependencies or [])
                if getattr(dep, "call", None) is not None
            ),
        })
    for endpoints in groups.values():
        endpoints.sort(key=lambda e: (e["path"], ",".join(e["methods"])))
    return dict(sorted(groups.items()))


def _render_index_html(groups: dict) -> str:
    sections = []
    for group, endpoints in groups.items():
        rows = []
        for ep in endpoints:
            methods_html = " ".join(
                f'<span class="m m-{m.lower()}">{m}</span>' for m in ep["methods"]
            )
            is_get_no_auth = ep["methods"] == ["GET"] and not ep["auth"]
            path_html = (
                f'<a href="{ep["path"]}">{ep["path"]}</a>' if is_get_no_auth
                else f'<code>{ep["path"]}</code>'
            )
            lock = ' <span class="lock" title="Requires X-API-Key">🔒</span>' if ep["auth"] else ""
            summary = ep["summary"] or ""
            rows.append(
                f'<tr><td class="methods">{methods_html}</td>'
                f'<td class="path">{path_html}{lock}</td>'
                f'<td class="summary">{summary}</td></tr>'
            )
        sections.append(
            f'<section><h2>{group}</h2>'
            f'<table><thead><tr><th>Method</th><th>Path</th><th>Summary</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></section>'
        )

    body = "".join(sections)
    api_key_hint = (
        '<p class="hint">🔒 marked endpoints require an <code>X-API-Key</code> header.</p>'
        if _app_config.API_KEY_REQUIRED else
        '<p class="hint">API key auth is currently <strong>disabled</strong>.</p>'
    )

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width,initial-scale=1" />
  <title>NovaBot API Index</title>
  <style>
    :root {{
      --bg:#0f1115; --panel:#161a22; --border:#252a35; --text:#e6e8ee;
      --muted:#8a93a6; --accent:#5ab0ff; --accent-soft:#1d3a5a;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; background:var(--bg); color:var(--text);
           font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }}
    .wrap {{ max-width:1100px; margin:0 auto; padding:28px 20px 60px; }}
    header {{ display:flex; justify-content:space-between; align-items:baseline;
              flex-wrap:wrap; gap:12px; margin-bottom:8px; }}
    h1 {{ margin:0; font-size:26px; }}
    .sub {{ color:var(--muted); margin-bottom:18px; }}
    .hint {{ color:var(--muted); font-size:12.5px; margin:8px 0 20px; }}
    .toolbar a {{ display:inline-block; padding:6px 12px; margin-right:8px;
                  border:1px solid var(--border); border-radius:6px;
                  background:var(--panel); color:var(--accent); text-decoration:none; }}
    .toolbar a:hover {{ border-color:var(--accent); }}
    section {{ margin-top:28px; }}
    section h2 {{ font-size:16px; text-transform:uppercase; letter-spacing:0.08em;
                  color:var(--muted); margin:0 0 8px; }}
    table {{ width:100%; border-collapse:collapse; background:var(--panel);
             border:1px solid var(--border); border-radius:8px; overflow:hidden; }}
    th, td {{ padding:9px 12px; text-align:left; border-bottom:1px solid var(--border);
              vertical-align:top; }}
    th {{ background:#1b2029; color:var(--muted); font-weight:600; font-size:12px;
          text-transform:uppercase; letter-spacing:0.04em; }}
    tr:last-child td {{ border-bottom:none; }}
    td.methods {{ white-space:nowrap; width:1%; }}
    td.path {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }}
    td.path a {{ color:var(--accent); text-decoration:none; }}
    td.path a:hover {{ text-decoration:underline; }}
    td.summary {{ color:var(--muted); }}
    code {{ font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            color:var(--text); }}
    .m {{ display:inline-block; padding:2px 7px; border-radius:4px;
          font-size:11px; font-weight:700; letter-spacing:0.04em; color:#fff; }}
    .m-get    {{ background:#2d7a46; }}
    .m-post   {{ background:#2e63b8; }}
    .m-put    {{ background:#b87e2e; }}
    .m-patch  {{ background:#8e4ab8; }}
    .m-delete {{ background:#b8322e; }}
    .lock {{ opacity:0.7; }}
    footer {{ margin-top:40px; color:var(--muted); font-size:12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>NovaBot Trading API</h1>
      <span class="sub">v2.0</span>
    </header>
    <div class="toolbar">
      <a href="/docs">Swagger UI</a>
      <a href="/redoc">ReDoc</a>
      <a href="/openapi.json">OpenAPI JSON</a>
      <a href="/health">/health</a>
    </div>
    {api_key_hint}
    {body}
    <footer>Generated dynamically from registered routes.</footer>
  </div>
</body>
</html>"""


@app.get("/", include_in_schema=False)
def root(request: Request):
    """API root: HTML index for browsers, JSON payload otherwise."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return HTMLResponse(_render_index_html(_collect_endpoints()))
    return {
        "name": "NovaBot Trading API",
        "version": "2.0",
        "status": "running",
        "docs": "/docs",
        "index_html": "/ (with Accept: text/html)",
    }


# Health check endpoint
# Used by Docker HEALTHCHECK and Coolify to decide whether to restart the
# container. HTTP 503 when the trading engine is missing or frozen so the
# orchestrator can recycle the container; HTTP 200 otherwise (including
# intentional engine stop → status "degraded").
_HEARTBEAT_STALE_SEC = 120


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring / Docker HEALTHCHECK."""
    bot_connected = False
    trading_enabled = False
    is_running = False
    active_trades_count = 0
    loop_responsive = None
    last_heartbeat_age_sec = None

    try:
        from app.services.internal.bridge import bot_bridge
        bot_connected = bool(bot_bridge and bot_bridge.is_connected())

        if bot_connected:
            bot = bot_bridge.get_bot_context()
            if bot is not None:
                trading_enabled = bool(getattr(bot, "trading_enabled", False))
                is_running = bool(getattr(bot, "is_running", False))
                try:
                    with bot.trade_lock:
                        active_trades_count = len(bot.active_trades)
                except Exception:
                    active_trades_count = len(getattr(bot, "active_trades", {}) or {})

                # Trading loop heartbeat: age in seconds since the last tick.
                # 0 means "the loop never ran yet" (bot just booted).
                last_hb = getattr(bot, "_loop_heartbeat", 0)
                if last_hb:
                    import time as _time
                    try:
                        last_heartbeat_age_sec = max(0, int(_time.time() - float(last_hb)))
                    except (TypeError, ValueError):
                        last_heartbeat_age_sec = None

                if hasattr(bot, "is_loop_responsive"):
                    try:
                        loop_responsive = bool(bot.is_loop_responsive())
                    except Exception:
                        loop_responsive = None
    except Exception as e:
        logger.debug("health_check: failed to probe bot bridge: %s", e)

    reason = None
    if not bot_connected:
        overall = "unhealthy"
        reason = "bot_not_connected"
    elif is_running and loop_responsive is False:
        overall = "unhealthy"
        reason = "loop_unresponsive"
    elif (
        is_running
        and last_heartbeat_age_sec is not None
        and last_heartbeat_age_sec >= _HEARTBEAT_STALE_SEC
    ):
        overall = "unhealthy"
        reason = "heartbeat_stale"
    elif not is_running:
        overall = "degraded"
        reason = "engine_stopped"
    else:
        overall = "healthy"

    payload = {
        "status": overall,
        "api_version": "2.0",
        "bot_connected": bot_connected,
        "is_running": is_running,
        "trading_enabled": trading_enabled,
        "active_trades": active_trades_count,
        "loop_responsive": loop_responsive,
        "last_heartbeat_age_sec": last_heartbeat_age_sec,
        "api_auth_enabled": bool(_app_config.API_KEY_REQUIRED),
        "reason": reason,
    }
    status_code = 503 if overall == "unhealthy" else 200
    return JSONResponse(status_code=status_code, content=payload)


# Restore missing /api/meta endpoint for Frontend
@app.get("/api/meta")
def get_meta():
    """Get exchange metadata (universe of tokens)"""
    try:
        from app.services.hyperliquid_service import hyperliquid_service
        # Fetch metadata (cached or fresh)
        meta = hyperliquid_service._fetch_metadata()
        if not meta:
             return {"universe": []}
        return meta
    except Exception as e:
        logger.error(f"Error serving /api/meta: {e}")
        return {"universe": []}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
