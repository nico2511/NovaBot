from fastapi import APIRouter
from pydantic import BaseModel
from app.gamification.enums import TierEnum

router = APIRouter(prefix="/admin", tags=["admin"])

# Simple in-memory storage for tier override (dev only)
# In production, use database or Redis
tier_override: dict[str, TierEnum] = {}

class OverrideTierRequest(BaseModel):
    user_id: str = "default"  # For now, single user
    tier: str  # NEBULA, PROTOSTAR, or SUPERNOVA

class OverrideTierResponse(BaseModel):
    message: str
    user_id: str
    tier: str

@router.post("/override-tier", response_model=OverrideTierResponse)
def set_tier_override(request: OverrideTierRequest):
    """
    Manually override a user's tier for debugging/testing.
    
    Example:
        POST /api/v1/admin/override-tier
        {"user_id": "default", "tier": "SUPERNOVA"}
    """
    try:
        tier_enum = TierEnum(request.tier.upper())
    except ValueError:
        return OverrideTierResponse(
            message=f"Invalid tier: {request.tier}",
            user_id=request.user_id,
            tier="ERROR"
        )
    
    tier_override[request.user_id] = tier_enum
    
    return OverrideTierResponse(
        message=f"Tier override set successfully",
        user_id=request.user_id,
        tier=tier_enum.value
    )

@router.delete("/override-tier")
def remove_tier_override(user_id: str = "default"):
    """
    Remove tier override for a user.
    
    Example:
        DELETE /api/v1/admin/override-tier?user_id=default
    """
    if user_id in tier_override:
        del tier_override[user_id]
        return {"message": "Tier override removed", "user_id": user_id}
    else:
        return {"message": "No override found", "user_id": user_id}

@router.get("/override-tier")
def get_tier_override(user_id: str = "default"):
    """
    Get current tier override for a user.
    
    Example:
        GET /api/v1/admin/override-tier?user_id=default
    """
    if user_id in tier_override:
        return {
            "user_id": user_id,
            "tier": tier_override[user_id].value,
            "has_override": True
        }
    else:
        return {
            "user_id": user_id,
            "tier": None,
            "has_override": False
        }

def get_override_tier(user_id: str = "default") -> TierEnum | None:
    """
    Helper function to get override tier if it exists.
    Used by TierCalculator to check for overrides.
    """
    return tier_override.get(user_id)
