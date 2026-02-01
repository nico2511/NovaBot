"""
FastAPI Dependencies for NovaBot API
Provides dependency injection for bot context and other shared resources
"""
from typing import Optional
from fastapi import HTTPException
from backend.bot_bridge import bot_bridge


def get_bot_context():
    """
    Dependency to get bot context from bot_bridge.
    Strict enforcement: Raises 503 if bot is not connected.
    Use this for operations that REQUIRE the bot engine.
    """
    if not bot_bridge or not bot_bridge.is_connected():
        raise HTTPException(
            status_code=503,
            detail="Bot engine not connected - service unavailable"
        )
    return bot_bridge.get_bot_context()


def get_bot_context_optional():
    """
    Dependency to get bot context optionally.
    Returns None if bot is not connected.
    Use this for operations that can degrade gracefully (e.g. settings).
    """
    if not bot_bridge or not bot_bridge.is_connected():
        return None
    return bot_bridge.get_bot_context()
