from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.gamification.tier_calculator import TierCalculator
from app.gamification.gatekeeper import Gatekeeper
from app.gamification.enums import TierEnum

router = APIRouter(prefix="/gamification", tags=["gamification"])

class CalculateTierRequest(BaseModel):
    equity: float

class CalculateTierResponse(BaseModel):
    equity: float
    tier: str

class CheckAccessRequest(BaseModel):
    user_tier: str
    strategy_name: str

class CheckAccessResponse(BaseModel):
    user_tier: str
    strategy_name: str
    has_access: bool

@router.post("/calculate-tier", response_model=CalculateTierResponse)
def calculate_tier(request: CalculateTierRequest):
    """
    Calculate user tier based on equity.
    
    Example:
        POST /api/v1/gamification/calculate-tier
        {"equity": 250}
        
        Response: {"equity": 250, "tier": "PROTOSTAR"}
    """
    tier = TierCalculator.calculate(request.equity)
    return CalculateTierResponse(
        equity=request.equity,
        tier=tier.value
    )

@router.post("/check-access", response_model=CheckAccessResponse)
def check_access(request: CheckAccessRequest):
    """
    Check if a user tier has access to a strategy.
    
    Example:
        POST /api/v1/gamification/check-access
        {"user_tier": "NEBULA", "strategy_name": "premium_strategy"}
        
        Response: {"user_tier": "NEBULA", "strategy_name": "premium_strategy", "has_access": false}
    """
    try:
        tier_enum = TierEnum(request.user_tier.upper())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid tier: {request.user_tier}")
    
    has_access = Gatekeeper.check_access(tier_enum, request.strategy_name)
    
    return CheckAccessResponse(
        user_tier=request.user_tier.upper(),
        strategy_name=request.strategy_name,
        has_access=has_access
    )

# Legacy compatibility endpoint for old frontend
@router.get("/status")
def get_gamification_status_legacy():
    """
    Legacy endpoint for backward compatibility with old frontend.
    Maps new tier names (NEBULA/PROTOSTAR/SUPERNOVA) to old names (Goblin/Mercenary/Whale).
    
    This endpoint will be deprecated after frontend migration.
    """
    # Mock equity for now (in real app, get from user session/database)
    mock_equity = 250.0  # Example: PROTOSTAR tier
    
    tier = TierCalculator.calculate(mock_equity)
    
    # Map new tiers to old names
    tier_mapping = {
        TierEnum.NEBULA: "Goblin",
        TierEnum.PROTOSTAR: "Mercenary",
        TierEnum.SUPERNOVA: "Whale"
    }
    
    old_tier_name = tier_mapping.get(tier, "Goblin")
    
    # Calculate progress to next tier
    from app.gamification.enums import TIER_THRESHOLDS
    
    if tier == TierEnum.NEBULA:
        next_tier = "Mercenary"
        required = TIER_THRESHOLDS["PROTOSTAR"]
        progress_percent = (mock_equity / required) * 100
        remaining = required - mock_equity
    elif tier == TierEnum.PROTOSTAR:
        next_tier = "Whale"
        required = TIER_THRESHOLDS["SUPERNOVA"]
        progress_percent = ((mock_equity - TIER_THRESHOLDS["PROTOSTAR"]) / 
                           (required - TIER_THRESHOLDS["PROTOSTAR"])) * 100
        remaining = required - mock_equity
    else:  # SUPERNOVA
        next_tier = None
        required = None
        progress_percent = 100
        remaining = 0
    
    return {
        "status": "success",
        "gamification": {
            "level": old_tier_name,
            "balance": mock_equity,
            "allowed_tiers": ["BTC", "ETH", "SOL"] if tier != TierEnum.NEBULA else ["BTC"],
            "max_leverage": 3 if tier == TierEnum.SUPERNOVA else (2 if tier == TierEnum.PROTOSTAR else 1),
            "max_position_size": None if tier == TierEnum.SUPERNOVA else 1000,
            "description": f"You are a {old_tier_name}",
            "recommendation": "Keep trading to level up!",
            "progress": {
                "current_level": old_tier_name,
                "next_level": next_tier,
                "current_balance": mock_equity,
                "required_balance": required,
                "progress_percent": progress_percent,
                "remaining": remaining
            },
            "recommendations": ["Trade more", "Increase equity"]
        }
    }
