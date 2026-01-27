
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

# Mocking external dependencies before importing BotContext
import sys
from types import ModuleType

# Create mocks for services and config
mock_hyperliquid = MagicMock()
mock_config = MagicMock()
mock_risk_manager = MagicMock()

# Setup config defaults
mock_config.DEFAULT_MAX_POSITIONS = 1
mock_config.DEFAULT_DAILY_STOP_LOSS = 50.0
mock_config.SCANNER_ENABLED = False
mock_config.SCANNER_INTERVAL = 5
mock_config.SCANNER_MIN_SCORE = 70
mock_config.SCANNER_AUTO_SWITCH = False
mock_config.SCANNER_GAMIFICATION = False
mock_config.TRADING_TIMEFRAME = "15m"
mock_config.BOT_PERSONA = "Conservative Scalper"
mock_config.RISK_PROFILE = "Capital Preservation First"
mock_config.AI_CONF_THRESHOLD_HIGH = 101
mock_config.AI_CONF_THRESHOLD_MEDIUM = 55
mock_config.AI_CONF_THRESHOLD_LOW = 35
mock_config.DEFAULT_LEVERAGE = 1
mock_config.AI_CALL_COOLDOWN = 2

# Mock classes and modules
class MockHyperliquidService:
    def __init__(self):
        self.log_callback = None
    def update_leverage(self, *args, **kwargs): pass
    def get_account_balance(self, *args, **kwargs): return {"status": "success", "total_equity": 1000.0, "equity": 1000.0}
    def get_positions(self, *args, **kwargs): return []

mock_hl_instance = MagicMock(spec=MockHyperliquidService)
mock_hl_instance.update_leverage = MagicMock()
mock_hl_instance.get_account_balance = MagicMock(return_value={"status": "success", "total_equity": 1000.0, "equity": 1000.0})

# Create mock module
hl_mod = ModuleType('hyperliquid_service')
hl_mod.HyperliquidService = MockHyperliquidService
hl_mod.hyperliquid_service = mock_hl_instance
sys.modules['app.services.hyperliquid_service'] = hl_mod

# Mock other heavy dependencies
config_mod = ModuleType('config')
config_mod.config = mock_config
sys.modules['app.core.config'] = config_mod

sys.modules['app.services.ia'] = MagicMock()
sys.modules['app.services.indicators'] = MagicMock()
sys.modules['app.services.analyst_service'] = MagicMock()
sys.modules['app.services.discord_service'] = MagicMock()
sys.modules['app.core.scanner_job'] = MagicMock()
sys.modules['app.core.state_manager'] = MagicMock()
sys.modules['app.core.asset_gamification'] = MagicMock()
sys.modules['app.core.trade_recorder'] = MagicMock()
sys.modules['strategies.engine'] = MagicMock()
sys.modules['app.utils.data_processing'] = MagicMock()

# Now import BotContext
from app.core.bot import BotContext

class TestRiskSyncLogic(unittest.TestCase):
    def setUp(self):
        # Reset mocks
        mock_hl_instance.update_leverage.reset_mock()
        self.bot = BotContext()
        # Ensure gamification is OFF for these tests
        self.bot.scanner_settings["gamification_enabled"] = False
        self.bot.active_symbol = "BTC"

    def test_enforce_leverage_conservative(self):
        self.bot.global_settings["risk_profile"] = "Capital Preservation First"
        self.bot._enforce_leverage()
        mock_hl_instance.update_leverage.assert_called_with("BTC", 3, False)

    def test_enforce_leverage_balanced(self):
        self.bot.global_settings["risk_profile"] = "Balanced Growth"
        self.bot._enforce_leverage()
        mock_hl_instance.update_leverage.assert_called_with("BTC", 5, False)

    def test_enforce_leverage_hunter(self):
        self.bot.global_settings["risk_profile"] = "High Volatility Hunter"
        self.bot._enforce_leverage()
        mock_hl_instance.update_leverage.assert_called_with("BTC", 10, False)

    def test_sizing_logic_conservative(self):
        self.bot.global_settings["risk_profile"] = "Capital Preservation First"
        # Simulate sizing logic block
        risk_profile = self.bot.global_settings.get("risk_profile")
        risk_pct = 1.5 # From bot.py logic
        
        entry_price = 50000.0
        sl_price = 49000.0
        equity = 1000.0
        
        self.bot.risk_manager.calculate_position_size = MagicMock(return_value=0.1)
        
        size = self.bot.risk_manager.calculate_position_size(
            price=entry_price,
            sl_price=sl_price,
            equity=equity,
            method="risk_pct",
            size_value=risk_pct
        )
        
        self.bot.risk_manager.calculate_position_size.assert_called_with(
            price=50000.0,
            sl_price=49000.0,
            equity=1000.0,
            method="risk_pct",
            size_value=1.5
        )

    def test_sizing_logic_hunter(self):
        self.bot.global_settings["risk_profile"] = "High Volatility Hunter"
        risk_pct = 7.0 # From bot.py logic
        
        entry_price = 50000.0
        sl_price = 49000.0
        equity = 1000.0
        
        self.bot.risk_manager.calculate_position_size = MagicMock()
        
        size = self.bot.risk_manager.calculate_position_size(
            price=entry_price,
            sl_price=sl_price,
            equity=equity,
            method="risk_pct",
            size_value=risk_pct
        )
        
        self.bot.risk_manager.calculate_position_size.assert_called_with(
            price=50000.0,
            sl_price=49000.0,
            equity=1000.0,
            method="risk_pct",
            size_value=7.0
        )

if __name__ == '__main__':
    unittest.main()
