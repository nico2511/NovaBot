"""
Settings routes for bot configuration
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import json
import os

router = APIRouter()

class SettingsUpdate(BaseModel):
    asset: Optional[str] = None
    interval: Optional[str] = None
    leverage: Optional[int] = None
    position_size: Optional[float] = None

SETTINGS_FILE = "bot_settings.json"

def load_settings():
    """Load settings from file"""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    return {
        "asset": "BTC",
        "interval": "15m",
        "leverage": 5,
        "position_size": 100
    }

def save_settings(settings):
    """Save settings to file"""
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f, indent=2)

@router.get("/settings")
async def get_settings():
    """Get current bot settings"""
    return load_settings()

@router.post("/settings")
async def update_settings(settings: SettingsUpdate):
    """Update bot settings"""
    current = load_settings()
    
    if settings.asset:
        current["asset"] = settings.asset
    if settings.interval:
        current["interval"] = settings.interval
    if settings.leverage:
        current["leverage"] = settings.leverage
    if settings.position_size:
        current["position_size"] = settings.position_size
    
    save_settings(current)
    
    return {
        "success": True,
        "settings": current
    }
