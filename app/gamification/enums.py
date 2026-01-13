from enum import Enum

class TierEnum(str, Enum):
    """User tier based on equity balance."""
    NEBULA = "NEBULA"
    PROTOSTAR = "PROTOSTAR"
    SUPERNOVA = "SUPERNOVA"

# Tier thresholds in USDC
TIER_THRESHOLDS = {
    "NEBULA": 0,      # < 100
    "PROTOSTAR": 100, # >= 100 and < 500
    "SUPERNOVA": 500  # >= 500
}
