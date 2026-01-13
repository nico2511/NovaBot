from app.gamification.enums import TierEnum, TIER_THRESHOLDS

class TierCalculator:
    """Service to calculate user tier based on equity balance."""
    
    @staticmethod
    def calculate(equity: float, user_id: str = "default") -> TierEnum:
        """
        Calculate user tier based on equity balance.
        
        Args:
            equity: User's current equity balance
            user_id: User identifier (for override lookup)
            
        Returns:
            TierEnum: User's tier (NEBULA, PROTOSTAR, or SUPERNOVA)
            
        Business Logic:
            - Check for admin override first
            - If no override, calculate based on equity:
                - equity < 100: NEBULA
                - 100 <= equity < 500: PROTOSTAR
                - equity >= 500: SUPERNOVA
        """
        # Check for admin override first
        try:
            from app.api.routes.admin import get_override_tier
            override = get_override_tier(user_id)
            if override is not None:
                return override
        except ImportError:
            pass  # Admin module not loaded yet
        
        # Calculate tier based on equity
        if equity < TIER_THRESHOLDS["PROTOSTAR"]:
            return TierEnum.NEBULA
        elif equity < TIER_THRESHOLDS["SUPERNOVA"]:
            return TierEnum.PROTOSTAR
        else:
            return TierEnum.SUPERNOVA
