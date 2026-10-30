import logging
import math
import os
import random
import threading
import time
from collections import defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r — using default %s", name, raw, default)
        return default


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

_COOLDOWN_LEVELS = (5.0, 10.0, 20.0, 60.0)

_INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}

_last_info_status_log = 0.0


def maybe_log_info_limiter_status(log_fn: Callable[[str], None]) -> None:
    """At most one synthesis log every 5 minutes."""
    global _last_info_status_log
    now = time.time()
    if now - _last_info_status_log < 300:
        return
    _last_info_status_log = now
    st = hl_info_limiter.get_status()
    log_fn(
        "ℹ️ HL /info limiter: "
        f"tokens={st.get('tokens')} weight/min={st.get('weight')} "
        f"rejects={st.get('local_rejects')} hl429={st.get('rate_limited_429')}"
    )


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
        self.budget_per_min = (
            float(budget_per_min)
            if budget_per_min is not None
            else _env_float("HL_INFO_WEIGHT_PER_MIN", 600.0)
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
        """Reset cooldown tier only — active cooldown window stays until it expires."""
        with self._lock:
            self._cooldown_step = 0

    def note_rate_limited(self) -> None:
        with self._lock:
            self.rate_limited_429 += 1
            self._cooldown_step = min(self._cooldown_step + 1, len(_COOLDOWN_LEVELS))
            idx = max(0, self._cooldown_step - 1)
            base = _COOLDOWN_LEVELS[min(idx, len(_COOLDOWN_LEVELS) - 1)]
            jitter = random.uniform(0.8, 1.2)
            self.cooldown_until = max(self.cooldown_until, self._clock() + base * jitter)

    def _deduct_unlocked(self, weight: int, now: float, *, high: bool) -> None:
        self.tokens -= weight
        self.calls += 1
        self.weight += weight
        if high:
            self._last_high_at = now

    def acquire(self, weight: int, priority: str = "normal") -> None:
        weight = max(1, int(weight))
        rate = self.budget_per_min / 60.0

        if priority == "high":
            max_wait = 2.0
            deadline = self._clock() + max_wait
            while True:
                with self._lock:
                    self._refill_unlocked()
                    now = self._clock()
                    gap = 0.0
                    if now < self.cooldown_until:
                        gap = max(0.0, 1.0 - (now - self._last_high_at))
                    if gap <= 0 and self.tokens >= weight:
                        self._deduct_unlocked(weight, now, high=True)
                        return
                    if now >= deadline:
                        self._deduct_unlocked(weight, now, high=True)
                        return
                    wait_for = gap if gap > 0 else max(0.0, (weight - self.tokens) / rate)
                    wait_for = min(wait_for, deadline - now)
                if wait_for <= 0:
                    continue
                self._sleep(wait_for)
            return

        max_wait = 3.0
        deadline = self._clock() + max_wait
        while True:
            with self._lock:
                self._refill_unlocked()
                now = self._clock()
                if now < self.cooldown_until:
                    self.local_rejects += 1
                    raise InfoRateLimited()
                if self.tokens >= weight:
                    self._deduct_unlocked(weight, now, high=False)
                    return
                if now >= deadline:
                    self.local_rejects += 1
                    raise InfoRateLimited()
                wait_for = min((weight - self.tokens) / rate, deadline - now)
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
