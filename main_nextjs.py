#!/usr/bin/env python3
"""
Main entry point for HyperLiquid Trading Bot with Next.js UI
Starts both the trading bot and the FastAPI server
"""
import sys
import os
import threading
import time
import asyncio
import uvicorn

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.config import config
from app.services.hyperliquid_service import hyperliquid_service
from app.core.bot import BotContext
from backend.bot_bridge import bot_bridge

def start_api_server(bot_context):
    """Start FastAPI server in a separate thread"""
    # Import here to ensure environment is fully loaded and avoid circular init risks
    from backend.api import app
    
    bot_bridge.set_bot_context(bot_context)
    print("🚀 Starting FastAPI server on http://localhost:8001")
    config = uvicorn.Config(app, host="0.0.0.0", port=8001, log_level="info", loop="asyncio")
    server = uvicorn.Server(config)
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(server.serve())

if __name__ == "__main__":
    print("=" * 60)
    print("🤖 HyperLiquid Trading Bot with Next.js UI")
    print("=" * 60)
    
    # Initialize Bot Context (Core Logic)
    bot = BotContext()
    
    print("\n📡 Initializing WebSocket price feeds...")
    try:
        # Start WebSocket for the active symbol
        hyperliquid_service.start_websocket([bot.active_symbol])
        print(f"✅ WebSocket connected for {bot.active_symbol}")
    except Exception as e:
        print(f"⚠️ WebSocket initialization failed: {e}")
        print("   Falling back to REST API for price feeds")
    
    # Start API Server in background thread
    api_thread = threading.Thread(target=start_api_server, args=(bot,), daemon=True)
    api_thread.start()
    
    print("\n✅ Bot initialized")
    print("📊 Next.js UI: http://localhost:3000")
    print("🔧 API Docs: http://localhost:8001/docs")
    
    should_autostart = bot.is_running or config.AUTO_START_TRADING
    
    if should_autostart:
        print(f"\n🔄 Auto-starting bot...")
        if not bot.is_running:
            bot.is_running = True
        bot.start()
    
    print("\nPress Ctrl+C to stop\n")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n⏹️ Shutting down...")
        try:
            hyperliquid_service.stop_websocket()
            print("✅ WebSocket stopped")
        except Exception as e:
            print(f"⚠️ Error stopping WebSocket: {e}")
        
        bot.stop()
        print("✅ Bot stopped. Goodbye!")