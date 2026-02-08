"""
Main FastAPI Application - Modular Router Architecture
Registers all routers and handles startup/shutdown events
"""
import os
import sys
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Setup paths
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.dirname(ROOT) # Point to project root (parent of backend/)
if ROOT not in sys.path:
    sys.path.append(ROOT)

# Logger setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MainApp")

# Import routers
from backend.api.routers import engine, trading, market, settings, history, analysis

# Settings Watcher
from backend.services.settings_watcher import SettingsWatcher
settings_watcher = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for FastAPI app.
    Handles startup and shutdown events resource management.
    """
    # --- STARTUP ---
    logger.info("🚀 API Startup: Initializing services...")
    
    # 1. Initialize Storage Service
    try:
        from backend.services.storage import init_storage
        init_storage(BASE_DIR)
        logger.info("✅ Storage service initialized")
    except Exception as e:
        logger.error(f"❌ Storage service initialization failed: {e}")
    
    # 2. Initialize Bot Bridge
    try:
        from backend.bot_bridge import bot_bridge
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
                from backend.bot_bridge import bot_bridge
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
        from backend.bot_bridge import bot_bridge
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

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(engine.router)
app.include_router(trading.router)
app.include_router(market.router)
app.include_router(settings.router)
app.include_router(history.router)
app.include_router(history.logs_router)  # Logs at /api/logs
app.include_router(analysis.router)
from backend.api.routers import scanner
app.include_router(scanner.router)

logger.info("✅ Routers registered: engine, trading, market, settings, history, logs, scanner")


# Root endpoint
@app.get("/")
def root():
    """API root endpoint"""
    return {
        "name": "NovaBot Trading API",
        "version": "2.0",
        "status": "running",
        "routers": ["engine", "trading"],
        "docs": "/docs"
    }


# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    try:
        from backend.bot_bridge import bot_bridge
        bot_connected = bot_bridge.is_connected() if bot_bridge else False
    except:
        bot_connected = False
    
    return {
        "status": "healthy",
        "bot_connected": bot_connected,
        "api_version": "2.0"
    }


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
