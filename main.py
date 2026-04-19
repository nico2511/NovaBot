"""
Unified Entry Point for NovaBot
Launches both the Trading Engine (Background) and API Server (Foreground)
"""
import os
import sys
import io
import threading
import uvicorn
import logging
import traceback
from dotenv import load_dotenv

# Fix stdout/stderr encoding on Windows to prevent Emoji crashes
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Load environment variables
load_dotenv()

# Setup paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT_DIR)

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("Launcher")

try:
    # 1. Initialize Storage Service (FIRST to allow singletons to use it during import)
    logger.info("📁 Initializing Storage Service...")
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    from app.services.storage import init_storage
    ss = init_storage(BASE_DIR)
    # Auto-sync runtime strategies config with versioned defaults (non-destructive)
    if ss:
        ss.sync_strategies_from_defaults()

    # 2. Import Core Components
    logger.info("📦 Importing Core Components...")
    from app.core.config import config
    from app.core.bot import BotContext

    from app.api.main import app
    from app.services.internal.bridge import bot_bridge
    
    # 3. Initialize Bot Instance
    logger.info("🤖 Initializing Bot Engine...")
    bot = BotContext()
    
    # 3. Secure Bridge Disconnected State first
    # (Just in case something accesses it early)
    
    # 4. Start Bot (Standard Method)
    logger.info("🚀 Starting Bot Engine...")
    bot.start()
    
    # 5. Connect Bridge
    logger.info("🔗 Connecting API Bridge...")
    bot_bridge.set_bot_context(bot)
    
    if bot_bridge.is_connected():
        logger.info("✅ Bridge Connected Successfully")
    else:
        logger.error("❌ Bridge Connection FAILED")

    # 6. Start API Server (Blocking)
    port = int(os.getenv("PORT", 3001))
    logger.info(f"🌍 Starting API Server on port {port}...")
    
except Exception as e:
    logger.critical(f"🔥 Launcher Initialization Failed: {e}")
    traceback.print_exc()
    sys.exit(1)
 
if __name__ == "__main__":
    port = int(os.getenv("PORT", 3001))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
