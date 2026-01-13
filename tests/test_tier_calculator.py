import pytest
from app.gamification.tier_calculator import TierCalculator
from app.gamification.enums import TierEnum

class TestTierCalculator:
    """Test suite for TierCalculator service."""
    
    def test_nebula_tier_below_threshold(self):
        """Test NEBULA tier for equity below 100."""
        assert TierCalculator.calculate(0) == TierEnum.NEBULA
        assert TierCalculator.calculate(50) == TierEnum.NEBULA
        assert TierCalculator.calculate(99.99) == TierEnum.NEBULA
    
    def test_protostar_tier_range(self):
        """Test PROTOSTAR tier for equity between 100 and 500."""
        assert TierCalculator.calculate(100) == TierEnum.PROTOSTAR
        assert TierCalculator.calculate(250) == TierEnum.PROTOSTAR
        assert TierCalculator.calculate(499.99) == TierEnum.PROTOSTAR
    
    def test_supernova_tier_above_threshold(self):
        """Test SUPERNOVA tier for equity >= 500."""
        assert TierCalculator.calculate(500) == TierEnum.SUPERNOVA
        assert TierCalculator.calculate(1000) == TierEnum.SUPERNOVA
        assert TierCalculator.calculate(10000) == TierEnum.SUPERNOVA
    
    def test_edge_case_zero_equity(self):
        """Test edge case: zero equity returns NEBULA."""
        assert TierCalculator.calculate(0) == TierEnum.NEBULA
    
    def test_edge_case_negative_equity(self):
        """Test edge case: negative equity returns NEBULA (safe default)."""
        assert TierCalculator.calculate(-10) == TierEnum.NEBULA
        assert TierCalculator.calculate(-100) == TierEnum.NEBULA
    
    def test_exact_boundary_100(self):
        """Test exact boundary at 100 USDC."""
        assert TierCalculator.calculate(99.99) == TierEnum.NEBULA
        assert TierCalculator.calculate(100) == TierEnum.PROTOSTAR
        assert TierCalculator.calculate(100.01) == TierEnum.PROTOSTAR
    
    def test_exact_boundary_500(self):
        """Test exact boundary at 500 USDC."""
        assert TierCalculator.calculate(499.99) == TierEnum.PROTOSTAR
        assert TierCalculator.calculate(500) == TierEnum.SUPERNOVA
        assert TierCalculator.calculate(500.01) == TierEnum.SUPERNOVA
