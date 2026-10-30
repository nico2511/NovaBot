"""Deduplicate Discord alert bursts (same message within a short window)."""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from typing import Tuple

from app.utils.hl_log_patterns import is_hl_rate_limit_text

logger = logging.getLogger(__name__)

_DEDUP_SECONDS = 45
_recent: dict[str, float] = {}
_lock = threading.Lock()

_suppressed_counts: dict[str, int] = {}
_suppressed_since: dict[str, float] = {}

def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or str(raw).strip() == "":
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("Invalid %s=%r — using default %s", name, raw, default)
        return default


_DISCORD_ERROR_DEDUP_MINUTES = _env_float("DISCORD_ERROR_DEDUP_MINUTES", 15.0)
_ERROR_WINDOW_S = int(_DISCORD_ERROR_DEDUP_MINUTES * 60)

_KNOWN_SYMBOLS: set[str] | None = None


def _load_known_symbols() -> set[str]:
    global _KNOWN_SYMBOLS
    if _KNOWN_SYMBOLS is not None:
        return _KNOWN_SYMBOLS
    symbols: set[str] = set()
    try:
        with open("data/config/strategies.json", "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for _name, block in (cfg or {}).items():
            if not isinstance(block, dict):
                continue
            params = block.get("params") or {}
            for sym in params.get("symbols") or []:
                if sym:
                    symbols.add(str(sym).upper())
    except Exception:
        pass
    symbols.update(
        {
            "BTC",
            "ETH",
            "SOL",
            "BNB",
            "XRP",
            "DOGE",
            "AVAX",
            "LINK",
            "ARB",
            "OP",
            "SUI",
            "LTC",
            "ADA",
            "DOT",
            "ATOM",
            "NEAR",
            "APT",
            "INJ",
            "KPEPE",
            "PEPE",
            "AAVE",
            "BCH",
        }
    )
    _KNOWN_SYMBOLS = symbols
    return symbols


def dedup_key(source: str, title: str, body: str) -> str:
    return f"{source}|{title}|{body[:200]}"


def _strip_long_parens(text: str) -> str:
    out = []
    depth = 0
    for ch in text:
        if ch in "{(":
            depth += 1
            if depth == 1:
                out.append("<>")
                continue
        if ch in "})":
            depth = max(0, depth - 1)
            continue
        if depth == 0:
            out.append(ch)
    return "".join(out)


def normalize_alert_key(source: str, level: str, title: str, body: str) -> str:
    text = f"{title}\n{body}"
    lower_probe = text.lower()
    if is_hl_rate_limit_text(text):
        return f"{source}|hl_rate_limit"

    for sym in sorted(_load_known_symbols(), key=len, reverse=True):
        text = re.sub(rf"\b{re.escape(sym)}\b", "<sym>", text, flags=re.IGNORECASE)

    text = re.sub(r"0x[a-fA-F0-9]{8,}", "<addr>", text)
    text = re.sub(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
        "<uuid>",
        text,
    )
    text = re.sub(r"\b\d+[mhd]\b", "<tf>", text, flags=re.IGNORECASE)
    text = re.sub(r"\b\d+(?:\.\d+)?\b", "<n>", text)
    text = _strip_long_parens(text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 160:
        text = text[:160]
    return f"{source}|{(level or '').lower()}|{text}"


def _window_for(source: str, level: str) -> Tuple[int, bool]:
    """Return (window_seconds, use_normalized_key)."""
    level_u = (level or "").upper()
    if level_u == "CRITICAL" or source == "execution":
        return _DEDUP_SECONDS, False
    return _ERROR_WINDOW_S, True


def should_send(
    key: str, window_s: int
) -> Tuple[bool, int, float]:
    """Thread-safe dedup with suppressed counter."""
    now = time.time()
    with _lock:
        last = _recent.get(key)
        if last is not None and now - last < window_s:
            _suppressed_counts[key] = _suppressed_counts.get(key, 0) + 1
            if key not in _suppressed_since:
                _suppressed_since[key] = last
            return False, 0, _suppressed_since.get(key, last)
        suppressed = _suppressed_counts.pop(key, 0)
        since = _suppressed_since.pop(key, last or now)
        _recent[key] = now
        return True, suppressed, since


def should_send_discord_alert(key: str, dedup_seconds: int = _DEDUP_SECONDS) -> bool:
    send, _sup, _since = should_send(key, dedup_seconds)
    return send


def should_send_alert(
    source: str, level: str, title: str, body: str
) -> Tuple[bool, str, int, float]:
    window_s, normalized = _window_for(source, level)
    if normalized:
        key = normalize_alert_key(source, level, title, body)
    else:
        key = dedup_key(source, f"{level}:{title}", body)
    send, suppressed, since = should_send(key, window_s)
    return send, key, suppressed, since


def reset_for_tests() -> None:
    with _lock:
        _recent.clear()
        _suppressed_counts.clear()
        _suppressed_since.clear()
