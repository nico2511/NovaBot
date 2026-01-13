import pytest
from app.gamification.gatekeeper import Gatekeeper
from app.gamification.enums import TierEnum
from app.core.decorators import safe_execution

class TestGatekeeper:
    """Test suite for Gatekeeper service."""
    
    def test_nebula_tier_limited_access(self):
        """Test NEBULA tier has limited access."""
        assert Gatekeeper.check_access(TierEnum.NEBULA, "basic_strategy") == True
        assert Gatekeeper.check_access(TierEnum.NEBULA, "advanced_strategy") == False
        assert Gatekeeper.check_access(TierEnum.NEBULA, "premium_strategy") == False
    
    def test_protostar_tier_medium_access(self):
        """Test PROTOSTAR tier has medium access."""
        assert Gatekeeper.check_access(TierEnum.PROTOSTAR, "basic_strategy") == True
        assert Gatekeeper.check_access(TierEnum.PROTOSTAR, "advanced_strategy") == True
        assert Gatekeeper.check_access(TierEnum.PROTOSTAR, "premium_strategy") == False
    
    def test_supernova_tier_full_access(self):
        """Test SUPERNOVA tier has full access."""
        assert Gatekeeper.check_access(TierEnum.SUPERNOVA, "basic_strategy") == True
        assert Gatekeeper.check_access(TierEnum.SUPERNOVA, "advanced_strategy") == True
        assert Gatekeeper.check_access(TierEnum.SUPERNOVA, "premium_strategy") == True
    
    def test_unknown_strategy_allowed_by_default(self):
        """Test unknown strategies are allowed (backward compatibility)."""
        assert Gatekeeper.check_access(TierEnum.NEBULA, "unknown_strategy") == True
        assert Gatekeeper.check_access(TierEnum.PROTOSTAR, "custom_strategy") == True


class TestSafeExecutionDecorator:
    """Test suite for @safe_execution decorator."""
    
    def test_decorator_allows_execution_with_access(self):
        """Test decorator allows execution when user has access."""
        @safe_execution(user_tier=TierEnum.SUPERNOVA)
        def test_strategy():
            return "SUCCESS"
        
        result = test_strategy()
        assert result == "SUCCESS"
    
    def test_decorator_blocks_execution_without_access(self):
        """Test decorator blocks execution when user lacks access."""
        @safe_execution(user_tier=TierEnum.NEBULA)
        def premium_strategy():
            return "SHOULD_NOT_EXECUTE"
        
        result = premium_strategy()
        assert result is None
    
    def test_decorator_catches_exceptions(self):
        """Test decorator catches exceptions and returns None."""
        @safe_execution(user_tier=TierEnum.SUPERNOVA)
        def buggy_strategy():
            raise ValueError("Simulated error")
        
        result = buggy_strategy()
        assert result is None  # Should return None instead of crashing
    
    def test_decorator_default_tier_supernova(self):
        """Test decorator defaults to SUPERNOVA tier if not specified."""
        @safe_execution()
        def test_strategy():
            return "EXECUTED"
        
        result = test_strategy()
        assert result == "EXECUTED"
