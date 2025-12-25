"""
Bridge between main bot (main.py) and FastAPI
Allows API to access bot state and control the bot
"""
from typing import Optional
import threading

class BotBridge:
    """Singleton bridge to share bot context with API"""
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.bot_context = None
        return cls._instance
    
    def set_bot_context(self, context):
        """Set the bot context from main.py"""
        self.bot_context = context
        print(f"✅ Bot context connected to API bridge (id={id(self)}, context={type(context).__name__})")
    
    def get_bot_context(self):
        """Get the bot context"""
        print(f"🔍 get_bot_context called (id={id(self)}, has_context={self.bot_context is not None})")
        return self.bot_context
    
    def is_connected(self) -> bool:
        """Check if bot is connected"""
        result = self.bot_context is not None
        print(f"🔍 is_connected called (id={id(self)}, result={result})")
        return result

# Global bridge instance
bot_bridge = BotBridge()
