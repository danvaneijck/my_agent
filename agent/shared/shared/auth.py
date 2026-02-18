"""Inter-service authentication middleware.

Every internal service (core, modules, bots) shares a single
``SERVICE_AUTH_TOKEN``.  Requests between services must include
``Authorization: Bearer <token>`` on protected endpoints.

Usage in a module or core FastAPI app::

    from shared.auth import require_service_auth

    @app.post("/execute")
    async def execute(call: ToolCall, _=Depends(require_service_auth)):
        ...
"""

from __future__ import annotations

import structlog
from fastapi import Depends, HTTPException, Request

from shared.config import get_settings

logger = structlog.get_logger()


def get_service_auth_headers() -> dict[str, str]:
    """Return HTTP headers for inter-service calls.

    Returns an empty dict when no token is configured (dev mode).
    """
    settings = get_settings()
    token = settings.service_auth_token
    if not token:
        return {}
    return {"Authorization": f"Bearer {token}"}


async def require_service_auth(request: Request) -> None:
    """FastAPI dependency that validates the inter-service auth token.

    Raises 401 if the token is missing or incorrect.
    Skips validation when ``service_auth_token`` is empty (dev mode).
    """
    settings = get_settings()
    expected = settings.service_auth_token
    if not expected:
        # No token configured — allow (development mode).
        # Log once per path to make it visible in logs without flooding.
        logger.warning(
            "service_auth_disabled",
            path=request.url.path,
            hint="Set SERVICE_AUTH_TOKEN in .env for production",
        )
        return

    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing service auth token")

    token = auth_header[7:]  # strip "Bearer "
    if token != expected:
        logger.warning(
            "service_auth_failed",
            path=request.url.path,
            remote=request.client.host if request.client else "unknown",
        )
        raise HTTPException(status_code=401, detail="Invalid service auth token")
