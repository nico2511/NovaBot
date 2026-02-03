from fastapi import HTTPException, Depends
from backend.bot_bridge import bot_bridge

def get_bot_context():
    """
    Dependency to get bot context. 
    Raises 503 if not connected (Bridge not ready or Bot not started).
    """
    if not bot_bridge or not bot_bridge.is_connected():
        raise HTTPException(
            status_code=503,
            detail="Bot engine not connected - service unavailable"
        )
    return bot_bridge.get_bot_context()

def get_bot_context_optional():
    """
    Dependency to get bot context if available, else None.
    Does NOT raise 503.
    """
    if not bot_bridge or not bot_bridge.is_connected():
        return None
    return bot_bridge.get_bot_context()

