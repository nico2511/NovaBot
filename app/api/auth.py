"""
API Authentication.

Lightweight header-based API key check used as a FastAPI dependency.
Behavior is controlled by two env vars (see app.core.config):

  - API_KEY            : the secret expected in the X-API-Key header
  - API_KEY_REQUIRED   : when "true", every protected endpoint enforces the key

When API_KEY_REQUIRED is false (default) the dependency is a no-op, which keeps
local development friction-free. In production (Coolify) set both:

    API_KEY=<long-random-string>
    API_KEY_REQUIRED=true
"""
from __future__ import annotations

import logging
import secrets

from fastapi import Header, HTTPException, status

from app.core.config import config

logger = logging.getLogger("Auth")

_WARNED_ABOUT_MISSING_KEY = False


def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")) -> None:
    """
    FastAPI dependency enforcing the X-API-Key header.

    Attach at router level:
        router = APIRouter(dependencies=[Depends(require_api_key)])
    """
    global _WARNED_ABOUT_MISSING_KEY

    # Opt-in model: stay permissive unless explicitly enabled.
    if not config.API_KEY_REQUIRED:
        return

    # If auth is on but API_KEY is empty we refuse everything rather than
    # accepting an empty header, and log a one-shot warning.
    if not config.API_KEY:
        if not _WARNED_ABOUT_MISSING_KEY:
            logger.error(
                "API_KEY_REQUIRED=true but API_KEY is empty; all API calls will be rejected."
            )
            _WARNED_ABOUT_MISSING_KEY = True
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API key not configured on server",
        )

    if not x_api_key or not secrets.compare_digest(x_api_key, config.API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
            headers={"WWW-Authenticate": "X-API-Key"},
        )
