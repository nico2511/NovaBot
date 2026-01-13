import functools
import logging
from typing import Callable, Any, Optional
from app.gamification.gatekeeper import Gatekeeper
from app.gamification.enums import TierEnum

logger = logging.getLogger(__name__)

def safe_execution(user_tier: Optional[TierEnum] = None):
    """
    Decorator to ensure safe execution of strategy functions.
    
    Features:
    1. Catches all exceptions and logs them
    2. Returns None on exception (no trade signal)
    3. Checks user access via Gatekeeper before execution
    
    Args:
        user_tier: User's tier for access control (optional, defaults to SUPERNOVA for backward compatibility)
        
    Usage:
        @safe_execution(user_tier=TierEnum.PROTOSTAR)
        def analyze_market(data):
            # Strategy logic here
            return signal
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            strategy_name = func.__name__
            
            # Default to SUPERNOVA if no tier specified (backward compatibility)
            tier = user_tier if user_tier is not None else TierEnum.SUPERNOVA
            
            try:
                # Step 1: Check access via Gatekeeper
                if not Gatekeeper.check_access(tier, strategy_name):
                    logger.warning(
                        f"Access denied: {strategy_name} not allowed for tier {tier.value}"
                    )
                    return None
                
                # Step 2: Execute the function
                result = func(*args, **kwargs)
                return result
                
            except Exception as e:
                # Step 3: Catch all exceptions, log, and return None
                logger.error(
                    f"Exception in {strategy_name}: {type(e).__name__}: {str(e)}",
                    exc_info=True
                )
                # TODO: Log to AuditService for compliance
                return None
        
        return wrapper
    return decorator
