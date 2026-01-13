"""
Test Bot Context integration with gamification.
"""

import pytest
from app.trading.bot_context import BotContext
from app.gamification.enums import TierEnum


def test_bot_context_initialization():
    """Test bot context initializes correctly"""
    bot = BotContext()
    
    assert bot is not None
    assert bot.current_tier == TierEnum.NEBULA
    assert bot.equity == 0.0
    assert bot.running == False


def test_bot_context_tier_update():
    """Test tier updates based on equity"""
    bot = BotContext()
    
    # Update tier with equity
    bot.update_tier(250)
    
    assert bot.current_tier == TierEnum.PROTOSTAR
    assert bot.equity == 250


def test_bot_context_start_stop():
    """Test bot start/stop"""
    bot = BotContext()
    
    bot.start()
    assert bot.running == True
    
    bot.stop()
    assert bot.running == False


def test_bot_context_status():
    """Test bot status"""
    bot = BotContext()
    bot.update_tier(100)
    
    status = bot.get_status()
    
    assert status["tier"] == "PROTOSTAR"
    assert status["equity"] == 100
    assert "logs" in status
