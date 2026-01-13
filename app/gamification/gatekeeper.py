from app.gamification.enums import TierEnum

class Gatekeeper:
    """Service to control access to trading strategies based on user tier."""
    
    # Strategy access rules by tier
    TIER_PERMISSIONS = {
        TierEnum.NEBULA: ["basic_strategy"],  # Limited access
        TierEnum.PROTOSTAR: ["basic_strategy", "advanced_strategy"],  # More access
        TierEnum.SUPERNOVA: ["basic_strategy", "advanced_strategy", "premium_strategy"]  # Full access
    }
    
    @staticmethod
    def check_access(user_tier: TierEnum, strategy_name: str) -> bool:
        """
        Check if a user has access to a specific strategy based on their tier.
        
        Args:
            user_tier: User's current tier (NEBULA, PROTOSTAR, SUPERNOVA)
            strategy_name: Name of the strategy to check access for
            
        Returns:
            bool: True if user has access, False otherwise
            
        Default Behavior:
            - If tier is not recognized, deny access (fail-safe)
            - If strategy is not in any tier list, allow access (backward compatibility)
        """
        # Fail-safe: deny access if tier is invalid
        if user_tier not in Gatekeeper.TIER_PERMISSIONS:
            return False
        
        # Get allowed strategies for this tier
        allowed_strategies = Gatekeeper.TIER_PERMISSIONS.get(user_tier, [])
        
        # If strategy is not in any tier list, allow (backward compatibility)
        all_restricted_strategies = set()
        for strategies in Gatekeeper.TIER_PERMISSIONS.values():
            all_restricted_strategies.update(strategies)
        
        if strategy_name not in all_restricted_strategies:
            return True
        
        # Check if strategy is in allowed list
        return strategy_name in allowed_strategies
