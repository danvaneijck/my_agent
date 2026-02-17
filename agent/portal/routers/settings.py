"""Account settings endpoints — credentials, profile, connected accounts."""

from __future__ import annotations

import json
import secrets

import redis.asyncio as aioredis
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from portal.auth import PortalUser, require_auth
from portal.claude_oauth import (
    build_authorize_url,
    build_credentials_json,
    exchange_code as claude_exchange_code,
    generate_pkce,
    get_token_expiry_info,
    parse_credentials_json,
    refresh_access_token,
)
from shared.config import get_settings
from shared.credential_store import CredentialStore
from shared.database import get_session_factory
from shared.models.user import User, UserPlatformLink

logger = structlog.get_logger()

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Credential service definitions — describes which keys each service accepts
SERVICE_DEFINITIONS = {
    "claude_code": {
        "label": "Claude Code",
        "keys": [
            {"key": "credentials_json", "label": "Claude CLI Credentials JSON", "type": "textarea"},
        ],
    },
    "github": {
        "label": "GitHub",
        "keys": [
            {"key": "github_token", "label": "GitHub Token (PAT)", "type": "password"},
            {"key": "ssh_private_key", "label": "SSH Private Key", "type": "textarea"},
            {"key": "git_author_name", "label": "Git Author Name", "type": "text"},
            {"key": "git_author_email", "label": "Git Author Email", "type": "text"},
        ],
    },
    "garmin": {
        "label": "Garmin Connect",
        "keys": [
            {"key": "email", "label": "Email", "type": "text"},
            {"key": "password", "label": "Password", "type": "password"},
        ],
    },
    "renpho": {
        "label": "Renpho",
        "keys": [
            {"key": "email", "label": "Email", "type": "text"},
            {"key": "password", "label": "Password", "type": "password"},
        ],
    },
    "atlassian": {
        "label": "Atlassian",
        "keys": [
            {"key": "url", "label": "Instance URL", "type": "text"},
            {"key": "username", "label": "Username", "type": "text"},
            {"key": "api_token", "label": "API Token", "type": "password"},
        ],
    },
}


def _get_credential_store() -> CredentialStore:
    settings = get_settings()
    if not settings.credential_encryption_key:
        raise HTTPException(503, "Credential storage not configured")
    return CredentialStore(settings.credential_encryption_key)


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


@router.get("/credentials")
async def list_credentials(user: PortalUser = Depends(require_auth)) -> dict:
    """List configured services with metadata (no secret values returned)."""
    store = _get_credential_store()
    factory = get_session_factory()
    async with factory() as session:
        configured = await store.list_services(session, user.user_id)

    # Merge with service definitions so frontend knows all available services
    result = []
    configured_map = {s["service"]: s for s in configured}
    for svc_name, svc_def in SERVICE_DEFINITIONS.items():
        entry = {
            "service": svc_name,
            "label": svc_def["label"],
            "keys": [k["key"] for k in svc_def["keys"]],
            "key_definitions": svc_def["keys"],
            "configured": svc_name in configured_map,
            "configured_keys": configured_map[svc_name]["keys"]
            if svc_name in configured_map
            else [],
            "configured_at": configured_map[svc_name]["configured_at"]
            if svc_name in configured_map
            else None,
        }
        result.append(entry)

    return {"services": result}


class CredentialUpdate(BaseModel):
    credentials: dict[str, str]


@router.put("/credentials/{service}")
async def upsert_credentials(
    service: str,
    body: CredentialUpdate,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Upsert credentials for a service. Values are encrypted before storage."""
    if service not in SERVICE_DEFINITIONS:
        raise HTTPException(400, f"Unknown service: {service}")

    valid_keys = {k["key"] for k in SERVICE_DEFINITIONS[service]["keys"]}
    invalid = set(body.credentials.keys()) - valid_keys
    if invalid:
        raise HTTPException(400, f"Invalid keys for {service}: {invalid}")

    # Filter out empty values — don't store blanks
    to_store = {k: v for k, v in body.credentials.items() if v.strip()}
    if not to_store:
        raise HTTPException(400, "No non-empty credentials provided")

    store = _get_credential_store()
    factory = get_session_factory()
    async with factory() as session:
        await store.set_many(session, user.user_id, service, to_store)

    logger.info(
        "credentials_updated",
        user_id=str(user.user_id),
        service=service,
        keys=list(to_store.keys()),
    )
    return {"status": "ok", "service": service, "keys": list(to_store.keys())}


@router.delete("/credentials/{service}")
async def delete_service_credentials(
    service: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Delete all credentials for a service."""
    store = _get_credential_store()
    factory = get_session_factory()
    async with factory() as session:
        count = await store.delete(session, user.user_id, service)
    return {"status": "ok", "deleted": count}


@router.delete("/credentials/{service}/{key}")
async def delete_credential_key(
    service: str,
    key: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Delete a single credential key for a service."""
    store = _get_credential_store()
    factory = get_session_factory()
    async with factory() as session:
        count = await store.delete(session, user.user_id, service, key)
    return {"status": "ok", "deleted": count}


# ---------------------------------------------------------------------------
# Claude OAuth (PKCE flow for in-portal credential setup)
# ---------------------------------------------------------------------------

_PKCE_TTL = 600  # 10 minutes


async def _get_redis() -> aioredis.Redis:
    settings = get_settings()
    return aioredis.from_url(settings.redis_url)


class OAuthCodeExchange(BaseModel):
    code: str


@router.post("/credentials/claude_code/oauth/start")
async def claude_oauth_start(user: PortalUser = Depends(require_auth)) -> dict:
    """Start the Anthropic OAuth PKCE flow.

    Returns an authorize URL the frontend should open in a new tab.
    The user authorizes on Anthropic's site, gets a code, and pastes it back.
    """
    verifier, challenge = generate_pkce()
    state = secrets.token_urlsafe(32)

    # Store PKCE state in Redis with a short TTL
    r = await _get_redis()
    try:
        pkce_data = json.dumps({"verifier": verifier, "state": state})
        await r.setex(f"claude_pkce:{user.user_id}", _PKCE_TTL, pkce_data)
    finally:
        await r.aclose()

    authorize_url = build_authorize_url(challenge, state)

    logger.info("claude_oauth_started", user_id=str(user.user_id))
    return {"authorize_url": authorize_url, "state": state}


@router.post("/credentials/claude_code/oauth/exchange")
async def claude_oauth_exchange(
    body: OAuthCodeExchange,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Exchange the authorization code from Anthropic for OAuth tokens.

    The code may be in ``code#state`` format (as displayed by Anthropic's callback
    page) or just the bare code.
    """
    # Retrieve PKCE state from Redis
    r = await _get_redis()
    try:
        raw = await r.get(f"claude_pkce:{user.user_id}")
        if not raw:
            raise HTTPException(400, "OAuth session expired or not started. Please try again.")
        pkce = json.loads(raw)
        await r.delete(f"claude_pkce:{user.user_id}")
    finally:
        await r.aclose()

    verifier = pkce["verifier"]

    # Handle code#state format from Anthropic's callback page
    code = body.code.strip()
    if "#" in code:
        code = code.split("#")[0]

    # Exchange code for tokens
    try:
        token_data = await claude_exchange_code(code, verifier)
    except ValueError as e:
        raise HTTPException(400, str(e))

    if "access_token" not in token_data:
        raise HTTPException(502, "Anthropic did not return an access token")

    # Build and store credentials in Claude CLI format
    creds_json = build_credentials_json(token_data)

    store = _get_credential_store()
    factory = get_session_factory()
    async with factory() as session:
        await store.set(session, user.user_id, "claude_code", "credentials_json", creds_json)

    scopes = token_data.get("scope", "").split()
    logger.info(
        "claude_oauth_exchange_success",
        user_id=str(user.user_id),
        scopes=scopes,
    )
    return {
        "status": "ok",
        "scopes": scopes,
        "expires_in": token_data.get("expires_in"),
    }


@router.post("/credentials/claude_code/oauth/refresh")
async def claude_oauth_refresh(user: PortalUser = Depends(require_auth)) -> dict:
    """Manually refresh the stored Claude OAuth access token."""
    store = _get_credential_store()
    factory = get_session_factory()

    async with factory() as session:
        creds_raw = await store.get(session, user.user_id, "claude_code", "credentials_json")

    if not creds_raw:
        raise HTTPException(404, "No Claude credentials stored")

    oauth = parse_credentials_json(creds_raw)
    if not oauth:
        raise HTTPException(400, "Invalid stored credentials format")

    refresh_tok = oauth.get("refreshToken") or oauth.get("refresh_token")
    if not refresh_tok:
        raise HTTPException(400, "No refresh token available — please reconnect via OAuth")

    new_tokens = await refresh_access_token(refresh_tok)
    if not new_tokens:
        raise HTTPException(502, "Token refresh failed — Anthropic may be unavailable")

    # Update stored credentials
    creds_json = build_credentials_json(new_tokens)
    async with factory() as session:
        await store.set(session, user.user_id, "claude_code", "credentials_json", creds_json)

    logger.info("claude_oauth_manual_refresh", user_id=str(user.user_id))
    return {
        "status": "ok",
        "expires_in": new_tokens.get("expires_in"),
    }


@router.get("/credentials/claude_code/status")
async def claude_credential_status(user: PortalUser = Depends(require_auth)) -> dict:
    """Return status of stored Claude credentials (expiry, scopes, etc.)."""
    store = _get_credential_store()
    factory = get_session_factory()

    async with factory() as session:
        creds_raw = await store.get(session, user.user_id, "claude_code", "credentials_json")

    if not creds_raw:
        return {"configured": False}

    oauth = parse_credentials_json(creds_raw)
    if not oauth:
        return {"configured": True, "valid": False, "error": "Invalid credentials format"}

    expiry = get_token_expiry_info(oauth)
    return {
        "configured": True,
        "valid": not expiry["is_expired"],
        "expires_at": expiry["expires_at"],
        "expires_in_seconds": expiry["expires_in_seconds"],
        "needs_refresh": expiry["needs_refresh"],
        "scopes": oauth.get("scopes", []),
        "subscription_type": oauth.get("subscriptionType"),
        "rate_limit_tier": oauth.get("rateLimitTier"),
    }


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@router.get("/profile")
async def get_profile(user: PortalUser = Depends(require_auth)) -> dict:
    """Get user profile info."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(User).where(User.id == user.user_id)
        )
        db_user = result.scalar_one_or_none()

    if not db_user:
        raise HTTPException(404, "User not found")

    return {
        "user_id": str(db_user.id),
        "username": user.username,
        "permission_level": db_user.permission_level,
        "token_budget_monthly": db_user.token_budget_monthly,
        "tokens_used_this_month": db_user.tokens_used_this_month,
        "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
    }


# ---------------------------------------------------------------------------
# Connected accounts
# ---------------------------------------------------------------------------


@router.get("/connected-accounts")
async def get_connected_accounts(user: PortalUser = Depends(require_auth)) -> dict:
    """List linked OAuth platform accounts."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(UserPlatformLink).where(
                UserPlatformLink.user_id == user.user_id
            )
        )
        links = result.scalars().all()

    accounts = [
        {
            "platform": link.platform,
            "username": link.platform_username,
            "platform_user_id": link.platform_user_id,
        }
        for link in links
        if link.platform != "web"  # hide internal web link
    ]

    return {"accounts": accounts}
