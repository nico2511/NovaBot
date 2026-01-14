"""
API Optimizations Module
To be integrated into backend/api.py

Includes:
- API Key security
- AI cooldown
- Logging middleware  
- Bridge status endpoint
- Generalized bot action pattern
"""

import time
import logging
from typing import Dict, Any, Callable, Optional
from fastapi import HTTPException, Request, Depends
from functools import wraps

# ============================================================================
# 1. LOGGING SETUP
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("api")

# ============================================================================
# 2. API KEY SECURITY
# ============================================================================

from app.core.config import config

API_KEY = config.API_KEY

async def verify_api_key(request: Request):
    """Verify API key from header"""
    api_key = request.headers.get("X-API-Key")
    if api_key != API_KEY:
        logger.warning(f"Invalid API key attempt from {request.client.host if request.client else 'unknown'}")
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True

# ============================================================================
# 3. AI COOLDOWN
# ============================================================================

# AI call cache (in-memory)
ai_cache: Dict[str, Dict[str, Any]] = {
    "signal_analysis": {"last_call": 0, "last_response": None},
    "market_commentary": {"last_call": 0, "last_response": None},
    "position_analysis": {"last_call": 0, "last_response": None}
}

AI_COOLDOWN_SECONDS = 60  # Configurable

def ai_cooldown_check(endpoint_name: str) -> Optional[Dict]:
    """
    Check if AI endpoint can be called or return cached response
    
    Returns:
        Cached response if within cooldown, None otherwise
    """
    now = time.time()
    cache_entry = ai_cache.get(endpoint_name, {})
    last_call = cache_entry.get("last_call", 0)
    
    if now - last_call < AI_COOLDOWN_SECONDS:
        # Return cached response
        remaining = int(AI_COOLDOWN_SECONDS - (now - last_call))
        cached_response = cache_entry.get("last_response")
        if cached_response:
            return {
                **cached_response,
                "cached": True,
                "cooldown_remaining": remaining
            }
    
    return None  # Proceed with AI call

def ai_cache_update(endpoint_name: str, response: dict):
    """Update AI cache after successful call"""
    ai_cache[endpoint_name] = {
        "last_call": time.time(),
        "last_response": response
    }

# ============================================================================
# 4. GENERALIZED BOT ACTION PATTERN
# ============================================================================

async def execute_bot_action(
    action_name: str,
    action_func: Callable,
    fallback_func: Optional[Callable] = None,
    require_bot: bool = True,
    bot_bridge = None
) -> Dict[str, Any]:
    """
    Execute an action on the bot context with optional fallback
    
    Args:
        action_name: Name of the action (for logging)
        action_func: Function to execute on bot (receives bot as arg)
        fallback_func: Optional fallback if bot not connected
        require_bot: If True, return error if bot not connected
        bot_bridge: Bot bridge instance
    
    Returns:
        Dict with success/error and result
    """
    # Try bot context first
    if bot_bridge and bot_bridge.is_connected():
        try:
            bot = bot_bridge.get_bot_context()
            result = action_func(bot)
            logger.info(f"{action_name} executed successfully via bot context")
            return {"success": True, "result": result, "source": "bot"}
        except Exception as e:
            logger.error(f"{action_name} error via bot: {e}")
            if not fallback_func:
                return {"error": str(e)}
    
    # Fallback if provided
    if fallback_func:
        try:
            result = fallback_func()
            logger.info(f"{action_name} executed via fallback")
            return {"success": True, "result": result, "source": "fallback"}
        except Exception as e:
            logger.error(f"{action_name} fallback error: {e}")
            return {"error": str(e)}
    
    # No bot and no fallback
    if require_bot:
        return {"error": "Bot not connected and no fallback available"}
    
    return {"error": "Action failed"}

# ============================================================================
# 5. LOGGING MIDDLEWARE (to add to app)
# ============================================================================

async def log_requests_middleware(request: Request, call_next):
    """Log all incoming requests"""
    start_time = time.time()
    
    # Log request
    logger.info(f"{request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Log response time
    process_time = time.time() - start_time
    logger.info(f"{request.method} {request.url.path} - {response.status_code} ({process_time:.2f}s)")
    
    return response
