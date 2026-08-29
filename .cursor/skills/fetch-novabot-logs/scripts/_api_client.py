"""Shared NovaBot API client for CLI scripts."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_TIMEOUT_SEC = 15.0


def load_dotenv() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv as _load

        _load(env_path)
    except ImportError:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def api_base_url() -> str:
    load_dotenv()
    return (os.getenv("NOVABOT_API_URL") or os.getenv("API_URL") or "http://localhost:3001").rstrip("/")


def api_key() -> str | None:
    load_dotenv()
    return os.getenv("API_KEY")


def request_json(
    method: str,
    path: str,
    *,
    body: Any | None = None,
    base_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SEC,
) -> tuple[Any | None, str | None]:
    url = f"{(base_url or api_base_url())}{path}"
    headers = {"Accept": "application/json"}
    key = api_key()
    if key:
        headers["X-API-Key"] = key
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            if not raw.strip():
                return {}, None
            return json.loads(raw), None
    except HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
        except Exception:
            detail = str(exc.reason)
        return None, f"HTTP {exc.code}: {detail or exc.reason}"
    except URLError as exc:
        return None, f"Connection failed: {exc.reason}"
    except json.JSONDecodeError as exc:
        return None, f"Invalid JSON: {exc}"


def get_json(path: str, **kwargs: Any) -> tuple[Any | None, str | None]:
    return request_json("GET", path, **kwargs)


def post_json(path: str, body: Any, **kwargs: Any) -> tuple[Any | None, str | None]:
    return request_json("POST", path, body=body, **kwargs)


def put_json(path: str, body: Any, **kwargs: Any) -> tuple[Any | None, str | None]:
    return request_json("PUT", path, body=body, **kwargs)


def load_local_json(rel_path: str) -> dict[str, Any]:
    path = REPO_ROOT / rel_path
    return json.loads(path.read_text(encoding="utf-8"))
