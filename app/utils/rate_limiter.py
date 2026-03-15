import time
from collections import defaultdict
from typing import Dict

class RateLimiter:
    """
    Simple token bucket rate limiter for Hyperliquid API calls.
    Prevents hitting rate limits on small server.
    """
    
    def __init__(self):
        self.calls: Dict[str, list] = defaultdict(list)
        self.max_calls = 30      # per endpoint per 60s
        self.window = 60         # seconds
    
    def can_call(self, endpoint: str = "default") -> bool:
        """Check if we can make a call to this endpoint"""
        now = time.time()
        # Clean old calls
        self.calls[endpoint] = [t for t in self.calls[endpoint] if now - t < self.window]
        
        if len(self.calls[endpoint]) >= self.max_calls:
            return False
        return True
    
    def record_call(self, endpoint: str = "default"):
        """Record that a call was made"""
        self.calls[endpoint].append(time.time())
    
    def get_status(self) -> Dict:
        """Return current rate limit status"""
        now = time.time()
        status = {}
        for endpoint, calls in self.calls.items():
            recent = len([t for t in calls if now - t < self.window])
            status[endpoint] = f"{recent}/{self.max_calls}"
        return status


# Global singleton
rate_limiter = RateLimiter()
