
import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("API_OPT")

# AI Cooldown Cache
_ai_cooldowns: Dict[str, float] = {}
AI_COOLDOWN_SECONDS = 60

# AI Cache (Simple in-memory store)
_ai_cache: Dict[str, Any] = {}

def verify_api_key():
    """Verify API Key (Placeholder for actual logic)"""
    return True

def ai_cooldown_check(key: str) -> Optional[Dict]:
    """Check if AI request is within cooldown period"""
    now = time.time()
    last_call = _ai_cooldowns.get(key, 0)
    
    if now - last_call < AI_COOLDOWN_SECONDS:
        remaining = int(AI_COOLDOWN_SECONDS - (now - last_call))
        # Return cached result if available
        if key in _ai_cache:
            return {"status": "cached", "data": _ai_cache[key], "ttl": remaining}
        return {"status": "cooldown", "message": f"Wait {remaining}s"}
    
    _ai_cooldowns[key] = now
    return None

def ai_cache_update(key: str, data: Any):
    """Update AI result cache"""
    _ai_cache[key] = data

def execute_bot_action(action_func, *args, **kwargs):
    """Safe wrapper for bot actions"""
    try:
        return action_func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Bot Action Failed: {e}")
        return {"status": "error", "message": str(e)}

async def log_requests_middleware(request, call_next):
    """Lightweight request logger (less verbose)"""
    # Only log state modifying requests to keep terminal clean
    if request.method not in ["GET", "OPTIONS"]:
        print(f"📝 API ACTION: {request.method} {request.url.path}")
    response = await call_next(request)
    return response
