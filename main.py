"""
Unified Entry Point for NovaBot
Launches both the Trading Engine (Background) and API Server (Foreground)
"""
import os
import sys
import threading
import uvicorn
import logging
from dotenv import load_dotenv

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
    from backend.services.storage import init_storage
    init_storage(BASE_DIR)

    # 2. Import Core Components
    logger.info("📦 Importing Core Components...")
    from app.core.config import config
    from app.core.bot import BotContext
    from backend.api.main import app
    from backend.bot_bridge import bot_bridge
    
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
    logger.info("🌍 Starting API Server on port 8001...")
    
except Exception as e:
    logger.critical(f"🔥 Launcher Initialization Failed: {e}")
    sys.exit(1)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="info")
