"""
OpenRouter account/key credit probe.

Uses GET /api/v1/credits (account purchased − used) when the key allows it,
and GET /api/v1/key for the optional per-key spend cap. Remaining is the
tightest known limit so the bot does not spend past either ceiling.
"""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

STATUS_OK = "ok"
STATUS_WARN = "warn"
STATUS_CRITICAL = "critical"
STATUS_UNKNOWN = "unknown"
STATUS_DISABLED = "disabled"
STATUS_ERROR = "error"


class OpenRouterHttpError(Exception):
    def __init__(self, status_code: int, body: str = ""):
        self.status_code = status_code
        self.body = body
        super().__init__(f"OpenRouter HTTP {status_code}: {body[:200]}")


def classify_credit_status(
    remaining_usd: Optional[float],
    warn_usd: float,
    min_usd: float,
) -> str:
    """Map remaining USD to ok / warn / critical / unknown."""
    if remaining_usd is None:
        return STATUS_UNKNOWN
    try:
        remaining = float(remaining_usd)
    except (TypeError, ValueError):
        return STATUS_UNKNOWN
    if remaining <= float(min_usd):
        return STATUS_CRITICAL
    if remaining <= float(warn_usd):
        return STATUS_WARN
    return STATUS_OK


def _unwrap_data(payload: Any) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data")
    return data if isinstance(data, dict) else payload


def remaining_from_credits_payload(payload: Any) -> Optional[float]:
    """Account remaining = total_credits − total_usage."""
    data = _unwrap_data(payload)
    try:
        total = data.get("total_credits")
        usage = data.get("total_usage")
        if total is None or usage is None:
            return None
        return float(total) - float(usage)
    except (TypeError, ValueError):
        return None


def remaining_from_key_payload(payload: Any) -> Optional[float]:
    """Per-key cap remaining; None means the key has no spend cap."""
    data = _unwrap_data(payload)
    remaining = data.get("limit_remaining")
    if remaining is None:
        return None
    try:
        return float(remaining)
    except (TypeError, ValueError):
        return None


def tighter_remaining(*values: Optional[float]) -> Optional[float]:
    known = [float(v) for v in values if v is not None]
    return min(known) if known else None


def build_credit_snapshot(
    *,
    credits_payload: Any = None,
    key_payload: Any = None,
    warn_usd: float = 1.0,
    min_usd: float = 0.10,
    error: Optional[str] = None,
    checked_at: Optional[str] = None,
) -> Dict[str, Any]:
    """Pure snapshot builder (no network) — used by IAService and tests."""
    account_remaining = remaining_from_credits_payload(credits_payload)
    key_remaining = remaining_from_key_payload(key_payload)
    remaining = tighter_remaining(account_remaining, key_remaining)

    source = None
    if account_remaining is not None and key_remaining is not None:
        source = "credits+key"
    elif account_remaining is not None:
        source = "credits"
    elif key_remaining is not None:
        source = "key"

    key_data = _unwrap_data(key_payload)
    credits_data = _unwrap_data(credits_payload)

    if error and remaining is None:
        status = STATUS_ERROR
    else:
        status = classify_credit_status(remaining, warn_usd, min_usd)

    return {
        "ok": status not in (STATUS_CRITICAL, STATUS_ERROR),
        "status": status,
        "remaining_usd": remaining,
        "account_remaining_usd": account_remaining,
        "key_remaining_usd": key_remaining,
        "total_credits": _as_float(credits_data.get("total_credits")),
        "total_usage": _as_float(credits_data.get("total_usage")),
        "is_free_tier": key_data.get("is_free_tier"),
        "source": source,
        "error": error,
        "checked_at": checked_at or datetime.now().isoformat(timespec="seconds"),
    }


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def empty_snapshot(status: str = STATUS_UNKNOWN, error: Optional[str] = None) -> Dict[str, Any]:
    return {
        "ok": status not in (STATUS_CRITICAL, STATUS_ERROR),
        "status": status,
        "remaining_usd": None,
        "account_remaining_usd": None,
        "key_remaining_usd": None,
        "total_credits": None,
        "total_usage": None,
        "is_free_tier": None,
        "source": None,
        "error": error,
        "checked_at": None,
    }


def fetch_openrouter_json(path: str, api_key: str, timeout: float = 10.0) -> Dict[str, Any]:
    """GET an OpenRouter JSON endpoint with the account API key."""
    if not path.startswith("/"):
        path = "/" + path
    url = f"{OPENROUTER_BASE}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "X-Title": "NovaBot",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            body = str(e)
        raise OpenRouterHttpError(int(e.code), body) from e
    except urllib.error.URLError as e:
        raise OpenRouterHttpError(0, str(e.reason if getattr(e, "reason", None) else e)) from e

    try:
        parsed = json.loads(raw) if raw else {}
    except json.JSONDecodeError as e:
        raise OpenRouterHttpError(0, f"invalid JSON: {e}") from e
    return parsed if isinstance(parsed, dict) else {"data": parsed}


def fetch_credit_payloads(
    api_key: str,
    timeout: float = 10.0,
    management_key: Optional[str] = None,
) -> tuple[Any, Any, Optional[str]]:
    """
    Fetch /credits then /key.

    /credits often needs a management key; we try management_key first, then
    fall back to api_key. A 401/403 on /credits is expected for normal chat
    keys and is not a hard failure if /key still returns a usable limit.
    """
    credits_payload: Any = None
    key_payload: Any = None
    errors: list[str] = []
    credits_keys = []
    if management_key and management_key != api_key:
        credits_keys.append(management_key)
    if api_key:
        credits_keys.append(api_key)

    for idx, key in enumerate(credits_keys):
        try:
            credits_payload = fetch_openrouter_json("/credits", key, timeout=timeout)
            break
        except OpenRouterHttpError as e:
            if e.status_code in (401, 403):
                logger.info(
                    "OpenRouter /credits not available with key #%s (HTTP %s)%s",
                    idx + 1,
                    e.status_code,
                    "; trying next key" if idx + 1 < len(credits_keys) else "; falling back to /key",
                )
            else:
                errors.append(f"/credits: {e}")
                logger.warning("OpenRouter /credits failed: %s", e)
                break

    try:
        key_payload = fetch_openrouter_json("/key", api_key, timeout=timeout)
    except OpenRouterHttpError as e:
        errors.append(f"/key: {e}")
        logger.warning("OpenRouter /key failed: %s", e)

    error = "; ".join(errors) if errors else None
    if credits_payload is None and key_payload is None and not error:
        error = "OpenRouter credit endpoints returned no data"
    return credits_payload, key_payload, error
