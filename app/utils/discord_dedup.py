"""Deduplicate Discord alert bursts (same message within a short window)."""
from __future__ import annotations

import threading
import time

_DEDUP_SECONDS = 45
_recent: dict[str, float] = {}
_lock = threading.Lock()


def dedup_key(source: str, title: str, body: str) -> str:
    return f"{source}|{title}|{body[:200]}"


def should_send_discord_alert(key: str, dedup_seconds: int = _DEDUP_SECONDS) -> bool:
    now = time.time()
    with _lock:
        last = _recent.get(key)
        if last is not None and now - last < dedup_seconds:
            return False
        _recent[key] = now
        return True
