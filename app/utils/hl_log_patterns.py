"""Shared patterns for Hyperliquid rate-limit detection in logs/alerts."""
from __future__ import annotations

import re


def is_hl_rate_limit_text(text: str) -> bool:
    """True only for real HTTP 429 / rate-limit messages (not prices like 3429.5)."""
    if not text:
        return False
    lower = text.lower()
    if "hyperliquid 429" in lower:
        return True
    if "too many requests" in lower:
        return True
    if "rate limit" in lower and re.search(r"\b429\b", text):
        return True
    if re.search(r"\bclienterror\s*\(\s*429\b", lower):
        return True
    if re.search(r"\(\s*429\s*,", text):
        return True
    return False
