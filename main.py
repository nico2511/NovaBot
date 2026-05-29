"""
Unified Entry Point for NovaBot.

Launches the Trading Engine (background thread) and the FastAPI server (foreground).

All initialization lives inside main(); importing this module has no side effects,
which keeps tests and tools safe from accidentally starting the bot.
"""
import io
import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

from dotenv import load_dotenv


def _setup_stdio_encoding() -> None:
    """Force UTF-8 on Windows stdout/stderr so emoji logs don't crash."""
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")


def _setup_logging(root_dir: str) -> None:
    """Configure root logging with console output and a rotating file handler."""
    logs_dir = os.path.join(root_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())

    # Avoid duplicate handlers when main() is called more than once (e.g. tests).
    for h in list(root.handlers):
        root.removeHandler(h)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        os.path.join(logs_dir, "novabot.log"),
        maxBytes=5 * 1024 * 1024,  # 5 MB per file
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    try:
        from app.utils.discord_log_handler import install_discord_alert_handler

        install_discord_alert_handler(level=logging.WARNING)
    except Exception as e:
        print(f"⚠️ Discord log handler not installed: {e}")


def main() -> None:
    _setup_stdio_encoding()
    load_dotenv()

    root_dir = os.path.dirname(os.path.abspath(__file__))
    if root_dir not in sys.path:
        sys.path.append(root_dir)

    _setup_logging(root_dir)
    logger = logging.getLogger("Launcher")

    bot = None
    try:
        logger.info("📁 Initializing Storage Service...")
        from app.services.storage import init_storage

        ss = init_storage(root_dir)
        if ss:
            ss.sync_strategies_from_defaults()

        logger.info("📦 Importing Core Components...")
        from app.api.main import app
        from app.core.bot import BotContext
        from app.services.internal.bridge import bot_bridge

        logger.info("🤖 Initializing Bot Engine...")
        bot = BotContext()

        logger.info("🚀 Starting Bot Engine...")
        bot.start()

        logger.info("🔗 Connecting API Bridge...")
        bot_bridge.set_bot_context(bot)
        if bot_bridge.is_connected():
            logger.info("✅ Bridge Connected Successfully")
        else:
            logger.error("❌ Bridge Connection FAILED")

        import uvicorn

        port = int(os.getenv("PORT", 3001))
        logger.info(f"🌍 Starting API Server on port {port}...")
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")

    except KeyboardInterrupt:
        # Ctrl+C — normal operator shutdown, exit quietly after cleanup.
        logger.info("⌨️  Ctrl+C received, shutting down...")
    except Exception as e:
        # Covers anything that happens during init OR inside uvicorn.run(),
        # including OSError "address already in use" when the port is busy.
        logger.critical(f"🔥 Launcher failed: {e}")
        traceback.print_exc()
    finally:
        # Always stop the trading thread before exiting, otherwise we leak a
        # background thread that keeps running after the API has crashed —
        # which is exactly how the port ends up held by a zombie process.
        if bot is not None:
            try:
                logger.info("🧹 Stopping bot engine before exit...")
                bot.stop()
            except Exception as stop_err:
                logger.error(f"Failed to stop bot cleanly: {stop_err}")
        # Force a non-zero exit if we got here via an exception path.
        if sys.exc_info()[0] not in (None, KeyboardInterrupt):
            sys.exit(1)


if __name__ == "__main__":
    main()
