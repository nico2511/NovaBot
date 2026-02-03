import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import sys
import os

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

@pytest.fixture
def mock_bot():
    """Mock BotContext with default attributes"""
    bot = MagicMock()
    # Engine state
    bot.is_running = False
    bot.trading_enabled = False
    bot.active_symbol = "BTC"
    
    # Status data
    bot.active_positions = []
    bot.daily_pnl = 100.50
    bot.total_trades = 42
    bot.win_rate = 65.0
    bot.margin_usage = 0.15
    bot.max_drawdown = 5.0
    
    # Settings
    bot.global_settings = {
        "risk_defaults": {
            "default_leverage": 5, 
            "daily_stop_loss": 500
        },
        "operations": {
             "auto_start": False
        }
    }
    bot.scanner_settings = {
        "enabled": True,
        "interval": 15
    }
    
    # Methods
    bot.start = MagicMock()
    bot.stop = MagicMock()
    bot.add_log = MagicMock()
    
    bot.logs = ["Log 1", "Log 2"]
    
    return bot

@pytest.fixture
def mock_bridge(mock_bot):
    """Patch the singleton BotBridge instance methods"""
    from backend.bot_bridge import bot_bridge
    
    # Save original state
    # We patch the instance methods directly to ensure all imports see the change
    with patch.object(bot_bridge, 'is_connected', return_value=True), \
         patch.object(bot_bridge, 'get_bot_context', return_value=mock_bot):
        
        # Also set the attribute just in case direct access is used
        bot_bridge.bot_context = mock_bot
        yield bot_bridge
        bot_bridge.bot_context = None

@pytest.fixture
def client(mock_bridge):
    """TestClient with mocked storage init"""
    # Mock storage service instance directly
    mock_storage = MagicMock()
    mock_storage.load_settings.return_value = {
        "operations": {},
        "risk_defaults": {},
        "ai_config": {},
        "scanner": {},
        "notifications": {}
    }
    
    # Patch the module attribute directly where it's defined
    with patch("backend.services.storage.storage_service", mock_storage), \
         patch("backend.services.storage.init_storage", return_value=mock_storage):
        
        from backend.api.main import app
        with TestClient(app) as test_client:
            yield test_client

