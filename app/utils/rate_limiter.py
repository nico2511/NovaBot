import math
import os
import random
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Dict, Optional

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


# Global singleton (legacy per-endpoint counter)
rate_limiter = RateLimiter()


class InfoRateLimited(Exception):
    """Local /info budget reject — no network call was made."""


_HL_PRIORITY: ContextVar[str] = ContextVar("hl_priority", default="normal")

_HIGH_INFO_TYPES = frozenset(
    {
        "clearinghouseState",
        "spotClearinghouseState",
        "openOrders",
        "frontendOpenOrders",
        "orderStatus",
    }
)

_INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


def _parse_interval_seconds(interval: str) -> int:
    iv = str(interval or "15m").strip().lower()
    if iv in _INTERVAL_SECONDS:
        return _INTERVAL_SECONDS[iv]
    if iv.endswith("m"):
        return int(iv[:-1]) * 60
    if iv.endswith("h"):
        return int(iv[:-1]) * 3600
    if iv.endswith("d"):
        return int(iv[:-1]) * 86400
    return 900


def estimate_info_weight(payload: dict) -> int:
    """Estimate Hyperliquid /info request weight from payload."""
    req_type = (payload or {}).get("type") or ""
    if req_type in (
        "clearinghouseState",
        "spotClearinghouseState",
        "allMids",
        "l2Book",
        "orderStatus",
        "exchangeStatus",
    ):
        return 2
    if req_type == "userRole":
        return 60
    if req_type == "candleSnapshot":
        start = int(payload.get("startTime") or 0)
        end = int(payload.get("endTime") or start)
        interval = payload.get("interval") or "15m"
        sec = _parse_interval_seconds(interval)
        span_ms = max(0, end - start)
        est_bars = max(1, int(span_ms / (sec * 1000)) + 1)
        return 20 + int(math.ceil(est_bars / 60))
    return 20


def payload_priority(payload: dict) -> str:
    req_type = (payload or {}).get("type") or ""
    if req_type in _HIGH_INFO_TYPES:
        return "high"
    if _HL_PRIORITY.get() == "high":
        return "high"
    return "normal"


@contextmanager
def hl_priority(level: str = "high"):
    token = _HL_PRIORITY.set(level)
    try:
        yield
    finally:
        _HL_PRIORITY.reset(token)


class HyperliquidInfoLimiter:
    """Thread-safe weighted token bucket for Hyperliquid /info REST."""

    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        budget_per_min: Optional[float] = None,
    ):
        self._lock = threading.Lock()
        self._clock = clock
        self._sleep = sleep
        self.budget_per_min = float(
            budget_per_min
            if budget_per_min is not None
            else os.getenv("HL_INFO_WEIGHT_PER_MIN", "600")
        )
        self.capacity = self.budget_per_min
        self.tokens = self.capacity
        self.last_refill = self._clock()
        self.cooldown_until = 0.0
        self._cooldown_step = 0
        self._last_high_at = 0.0
        self.calls = 0
        self.weight = 0
        self.local_rejects = 0
        self.rate_limited_429 = 0

    def reset(self) -> None:
        with self._lock:
            self.tokens = self.capacity
            self.last_refill = self._clock()
            self.cooldown_until = 0.0
            self._cooldown_step = 0
            self._last_high_at = 0.0
            self.calls = 0
            self.weight = 0
            self.local_rejects = 0
            self.rate_limited_429 = 0

    def _refill_unlocked(self) -> None:
        now = self._clock()
        elapsed = now - self.last_refill
        if elapsed <= 0:
            return
        rate = self.budget_per_min / 60.0
        self.tokens = min(self.capacity, self.tokens + elapsed * rate)
        self.last_refill = now

    def note_success(self) -> None:
        with self._lock:
            self._cooldown_step = 0
            self.cooldown_until = 0.0

    def note_rate_limited(self) -> None:
        with self._lock:
            self.rate_limited_429 += 1
            self._cooldown_step = min(self._cooldown_step + 1, 4)
            base = min(60.0, 5.0 * (2 ** (self._cooldown_step - 1)))
            jitter = random.uniform(0.8, 1.2)
            self.cooldown_until = max(self.cooldown_until, self._clock() + base * jitter)

    def acquire(self, weight: int, priority: str = "normal") -> None:
        weight = max(1, int(weight))
        max_wait = 2.0 if priority == "high" else 3.0
        deadline = self._clock() + max_wait

        while True:
            with self._lock:
                self._refill_unlocked()
                now = self._clock()

                if priority == "normal" and now < self.cooldown_until:
                    self.local_rejects += 1
                    raise InfoRateLimited()

                if priority == "high" and now < self.cooldown_until:
                    gap = 1.0 - (now - self._last_high_at)
                    if gap > 0 and now + gap > deadline:
                        self.local_rejects += 1
                        raise InfoRateLimited()
                    need_wait = max(gap, 0.0)
                    if self.tokens >= weight and need_wait <= 0:
                        self.tokens -= weight
                        self.calls += 1
                        self.weight += weight
                        self._last_high_at = now
                        return
                    if now >= deadline:
                        self.local_rejects += 1
                        raise InfoRateLimited()
                    wait_for = min(
                        need_wait if need_wait > 0 else max(0.0, (weight - self.tokens) / (self.budget_per_min / 60.0)),
                        deadline - now,
                    )
                else:
                    if self.tokens >= weight:
                        self.tokens -= weight
                        self.calls += 1
                        self.weight += weight
                        if priority == "high":
                            self._last_high_at = now
                        return
                    if now >= deadline:
                        self.local_rejects += 1
                        raise InfoRateLimited()
                    wait_for = min(
                        (weight - self.tokens) / (self.budget_per_min / 60.0),
                        deadline - now,
                    )

            if wait_for <= 0:
                continue
            self._sleep(wait_for)

    def get_status(self) -> Dict:
        with self._lock:
            self._refill_unlocked()
            return {
                "tokens": round(self.tokens, 2),
                "budget_per_min": self.budget_per_min,
                "cooldown_until": self.cooldown_until,
                "calls": self.calls,
                "weight": self.weight,
                "local_rejects": self.local_rejects,
                "rate_limited_429": self.rate_limited_429,
            }


hl_info_limiter = HyperliquidInfoLimiter()
