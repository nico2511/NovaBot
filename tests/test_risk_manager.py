"""
Test Risk Manager with tier-based limits.
"""

import pytest
from app.trading.risk_manager import RiskManager
from app.gamification.enums import TierEnum


def test_risk_manager_initialization():
    """Test risk manager initializes with tier"""
    rm = RiskManager(tier=TierEnum.NEBULA)
    
    assert rm.tier == TierEnum.NEBULA
    assert rm.get_max_positions() == 1
    assert rm.get_max_leverage() == 1


def test_tier_limits():
    """Test tier-based limits"""
    # NEBULA
    rm_nebula = RiskManager(tier=TierEnum.NEBULA)
    assert rm_nebula.get_max_positions() == 1
    assert rm_nebula.get_max_leverage() == 1
    assert rm_nebula.get_max_position_size() == 100
    
    # PROTOSTAR
    rm_proto = RiskManager(tier=TierEnum.PROTOSTAR)
    assert rm_proto.get_max_positions() == 2
    assert rm_proto.get_max_leverage() == 2
    assert rm_proto.get_max_position_size() == 1000
    
    # SUPERNOVA
    rm_super = RiskManager(tier=TierEnum.SUPERNOVA)
    assert rm_super.get_max_positions() == 3
    assert rm_super.get_max_leverage() == 5
    assert rm_super.get_max_position_size() == 10000


def test_tier_update():
    """Test tier update"""
    rm = RiskManager(tier=TierEnum.NEBULA)
    assert rm.get_max_positions() == 1
    
    rm.update_tier(TierEnum.SUPERNOVA)
    assert rm.get_max_positions() == 3


def test_can_trade():
    """Test trading permission check"""
    rm = RiskManager(tier=TierEnum.NEBULA)
    
    # Should allow first trade
    can_trade, reason = rm.check_can_trade()
    assert can_trade == True
    
    # Open position
    rm.record_trade_open()
    
    # Should block second trade (NEBULA max = 1)
    can_trade, reason = rm.check_can_trade()
    assert can_trade == False
    assert "Max positions" in reason


def test_position_size_calculation():
    """Test position size with tier limits"""
    rm = RiskManager(tier=TierEnum.NEBULA)
    
    # Calculate size
    size = rm.calculate_position_size(
        price=50000,
        equity=100,
        leverage=5  # Will be capped to 1 for NEBULA
    )
    
    assert size > 0
    # Size should respect tier limits


def test_daily_stop_loss():
    """Test daily stop loss"""
    rm = RiskManager(tier=TierEnum.NEBULA, daily_stop_loss=50.0)
    
    # Record losing trade
    rm.record_trade_close(pnl=-60.0)
    
    # Should be in stop mode
    can_trade, reason = rm.check_can_trade()
    assert can_trade == False
    assert "Stop Loss" in reason


def test_status():
    """Test status reporting"""
    rm = RiskManager(tier=TierEnum.PROTOSTAR)
    
    status = rm.get_status()
    
    assert status["tier"] == "PROTOSTAR"
    assert status["max_positions"] == 2
    assert status["max_leverage"] == 2
    assert status["daily_pnl"] == 0.0
