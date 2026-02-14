"""JWT-based authentication for the web portal."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt
from fastapi import Header, HTTPException, WebSocket, WebSocketException, status

from shared.config import get_settings

JWT_ALGORITHM = "HS256"


@dataclass
class PortalUser:
    """Authenticated portal user. Injected by require_auth / verify_ws_auth."""

    user_id: uuid.UUID
    username: str
    permission_level: str
    auth_provider: str = ""


def _decode_token(token: str) -> PortalUser:
    """Decode and validate a JWT, returning a PortalUser."""
    settings = get_settings()
    if not settings.portal_jwt_secret:
        raise HTTPException(status_code=503, detail="Portal auth not configured")
    try:
        payload = jwt.decode(
            token, settings.portal_jwt_secret, algorithms=[JWT_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

    return PortalUser(
        user_id=uuid.UUID(payload["sub"]),
        username=payload.get("username", ""),
        permission_level=payload.get("permission_level", "guest"),
        auth_provider=payload.get("auth_provider", ""),
    )


async def require_auth(authorization: str = Header()) -> PortalUser:
    """FastAPI dependency: extract and validate JWT from Authorization header.

    Expects: Authorization: Bearer <jwt>
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Bearer token")
    token = authorization[7:]
    return _decode_token(token)


async def verify_ws_auth(websocket: WebSocket) -> PortalUser:
    """Validate JWT from WebSocket query params. Returns PortalUser or closes."""
    token = websocket.query_params.get("token", "")
    if not token:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    settings = get_settings()
    if not settings.portal_jwt_secret:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    try:
        payload = jwt.decode(
            token, settings.portal_jwt_secret, algorithms=[JWT_ALGORITHM]
        )
    except jwt.InvalidTokenError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)

    return PortalUser(
        user_id=uuid.UUID(payload["sub"]),
        username=payload.get("username", ""),
        permission_level=payload.get("permission_level", "guest"),
        auth_provider=payload.get("auth_provider", ""),
    )
