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
from portal.git_oauth import (
    BitbucketOAuthProvider,
    GitHubOAuthProvider,
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
            {"key": "github_token", "label": "GitHub Token (PAT or OAuth)", "type": "password"},
            {"key": "github_refresh_token", "label": "Refresh Token (auto-managed)", "type": "password"},
            {"key": "github_token_expires_at", "label": "Token Expiry (auto-populated)", "type": "text"},
            {"key": "github_token_scope", "label": "Token Scopes (auto-populated)", "type": "text"},
            {"key": "github_username", "label": "GitHub Username (auto-populated)", "type": "text"},
            {"key": "ssh_private_key", "label": "SSH Private Key (optional)", "type": "textarea"},
            {"key": "git_author_name", "label": "Git Author Name", "type": "text"},
            {"key": "git_author_email", "label": "Git Author Email", "type": "text"},
        ],
    },
    "bitbucket": {
        "label": "Bitbucket",
        "keys": [
            {"key": "bitbucket_token", "label": "Bitbucket OAuth Token", "type": "password"},
            {"key": "bitbucket_refresh_token", "label": "Refresh Token (auto-managed)", "type": "password"},
            {"key": "bitbucket_token_expires_at", "label": "Token Expiry (auto-populated)", "type": "text"},
            {"key": "bitbucket_token_scope", "label": "Token Scopes (auto-populated)", "type": "text"},
            {"key": "bitbucket_username", "label": "Bitbucket Username (auto-populated)", "type": "text"},
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
    state = pkce.get("state")

    # Handle code#state format from Anthropic's callback page
    code = body.code.strip()
    if "#" in code:
        code, returned_state = code.split("#", 1)
        # Use the state from the callback if available
        if returned_state:
            state = returned_state

    # Exchange code for tokens
    try:
        token_data = await claude_exchange_code(code, verifier, state=state)
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


# ---------------------------------------------------------------------------
# Git OAuth (GitHub, Bitbucket)
# ---------------------------------------------------------------------------

_OAUTH_STATE_TTL = 600  # 10 minutes


def _get_github_provider() -> GitHubOAuthProvider:
    """Get configured GitHub OAuth provider."""
    settings = get_settings()
    if not settings.github_oauth_client_id or not settings.github_oauth_client_secret:
        raise HTTPException(503, "GitHub OAuth not configured")
    return GitHubOAuthProvider(
        settings.github_oauth_client_id,
        settings.github_oauth_client_secret,
    )


def _get_bitbucket_provider() -> BitbucketOAuthProvider:
    """Get configured Bitbucket OAuth provider."""
    settings = get_settings()
    if not settings.bitbucket_oauth_client_id or not settings.bitbucket_oauth_client_secret:
        raise HTTPException(503, "Bitbucket OAuth not configured")
    return BitbucketOAuthProvider(
        settings.bitbucket_oauth_client_id,
        settings.bitbucket_oauth_client_secret,
    )


# ---------------------------------------------------------------------------
# GitHub OAuth
# ---------------------------------------------------------------------------


@router.post("/credentials/github/oauth/start")
async def github_oauth_start(user: PortalUser = Depends(require_auth)) -> dict:
    """Start GitHub OAuth flow.

    Returns an authorize URL to redirect the browser to.
    GitHub will redirect back to the callback endpoint after user authorization.
    """
    provider = _get_github_provider()
    settings = get_settings()
    state = secrets.token_urlsafe(32)

    # Store user_id + state in Redis with short TTL
    # We embed user_id in the OAuth state so the callback can identify the user
    r = await _get_redis()
    try:
        state_data = json.dumps({"user_id": str(user.user_id), "state": state})
        await r.setex(f"git_oauth:github:{state}", _OAUTH_STATE_TTL, state_data)
    finally:
        await r.aclose()

    # Build redirect URI
    redirect_uri = f"{settings.git_oauth_redirect_uri}/github/oauth/callback"
    authorize_url = provider.get_auth_url(redirect_uri, state)

    logger.info("github_oauth_started", user_id=str(user.user_id))
    return {"authorize_url": authorize_url, "state": state}


@router.get("/credentials/github/oauth/callback")
async def github_oauth_callback(
    code: str,
    state: str,
) -> dict:
    """GitHub OAuth callback endpoint.

    GitHub redirects here after user authorization with code and state parameters.
    This endpoint is public (no auth required) because browser redirects can't include auth headers.
    The user_id is retrieved from the state stored in Redis.
    """
    from uuid import UUID
    provider = _get_github_provider()
    settings = get_settings()

    # Retrieve user_id from state stored in Redis
    r = await _get_redis()
    try:
        state_data_raw = await r.get(f"git_oauth:github:{state}")
        if not state_data_raw:
            raise HTTPException(400, "Invalid or expired OAuth state")
        state_data = json.loads(state_data_raw.decode())
        await r.delete(f"git_oauth:github:{state}")
    finally:
        await r.aclose()

    # Extract user_id from state data
    try:
        user_id = UUID(state_data["user_id"])
    except (KeyError, ValueError):
        raise HTTPException(400, "Invalid state format")

    # Exchange code for tokens
    redirect_uri = f"{settings.git_oauth_redirect_uri}/github/oauth/callback"
    try:
        tokens = await provider.exchange_code(code, redirect_uri)
    except ValueError as e:
        logger.error("github_oauth_exchange_failed", error=str(e))
        raise HTTPException(400, str(e))

    # Get user info
    try:
        user_info = await provider.get_user_info(tokens.access_token)
    except Exception as e:
        logger.error("github_userinfo_failed", error=str(e))
        user_info = None

    # Store credentials
    store = _get_credential_store()
    factory = get_session_factory()
    async with factory() as session:
        creds_to_store = {
            "github_token": tokens.access_token,
            "github_token_scope": tokens.scope or "repo user:email",
        }
        if tokens.refresh_token:
            creds_to_store["github_refresh_token"] = tokens.refresh_token
        if tokens.expires_at:
            from datetime import datetime, timezone
            expires_dt = datetime.fromtimestamp(tokens.expires_at / 1000, tz=timezone.utc)
            creds_to_store["github_token_expires_at"] = expires_dt.isoformat()
        if user_info:
            creds_to_store["github_username"] = user_info.username

        await store.set_many(session, user_id, "github", creds_to_store)

    logger.info(
        "github_oauth_success",
        user_id=str(user_id),
        username=user_info.username if user_info else None,
    )

    # Redirect to success page
    from fastapi.responses import RedirectResponse
    return RedirectResponse(
        url=f"{settings.portal_oauth_redirect_uri.replace('/api/settings/credentials', '')}/settings?oauth=github&status=success",
        status_code=302,
    )


@router.post("/credentials/github/oauth/refresh")
async def github_oauth_refresh(user: PortalUser = Depends(require_auth)) -> dict:
    """Manually refresh GitHub OAuth token (only for fine-grained tokens with expiration)."""
    provider = _get_github_provider()
    store = _get_credential_store()
    factory = get_session_factory()

    async with factory() as session:
        refresh_token = await store.get(session, user.user_id, "github", "github_refresh_token")

    if not refresh_token:
        raise HTTPException(400, "No refresh token available")

    new_tokens = await provider.refresh_access_token(refresh_token)
    if not new_tokens:
        raise HTTPException(502, "Token refresh failed")

    # Update stored credentials
    async with factory() as session:
        creds_to_store = {
            "github_token": new_tokens.access_token,
        }
        if new_tokens.refresh_token:
            creds_to_store["github_refresh_token"] = new_tokens.refresh_token
        if new_tokens.expires_at:
            from datetime import datetime, timezone
            expires_dt = datetime.fromtimestamp(new_tokens.expires_at / 1000, tz=timezone.utc)
            creds_to_store["github_token_expires_at"] = expires_dt.isoformat()
        if new_tokens.scope:
            creds_to_store["github_token_scope"] = new_tokens.scope

        await store.set_many(session, user.user_id, "github", creds_to_store)

    logger.info("github_oauth_refresh_success", user_id=str(user.user_id))
    return {"status": "ok", "expires_in": new_tokens.expires_in}


@router.get("/credentials/github/status")
async def github_credential_status(user: PortalUser = Depends(require_auth)) -> dict:
    """Return status of GitHub credentials."""
    store = _get_credential_store()
    factory = get_session_factory()

    async with factory() as session:
        token = await store.get(session, user.user_id, "github", "github_token")
        username = await store.get(session, user.user_id, "github", "github_username")
        scope = await store.get(session, user.user_id, "github", "github_token_scope")
        expires_at_str = await store.get(session, user.user_id, "github", "github_token_expires_at")

    if not token:
        return {"configured": False}

    # Parse expiry if present
    expires_in_seconds = None
    is_expired = False
    if expires_at_str:
        from datetime import datetime, timezone
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            now = datetime.now(timezone.utc)
            expires_in_seconds = int((expires_at - now).total_seconds())
            is_expired = expires_in_seconds <= 0
        except Exception:
            pass

    return {
        "configured": True,
        "username": username,
        "scopes": scope.split() if scope else [],
        "expires_at": expires_at_str,
        "expires_in_seconds": expires_in_seconds,
        "is_expired": is_expired,
    }


# ---------------------------------------------------------------------------
# Bitbucket OAuth
# ---------------------------------------------------------------------------


@router.post("/credentials/bitbucket/oauth/start")
async def bitbucket_oauth_start(user: PortalUser = Depends(require_auth)) -> dict:
    """Start Bitbucket OAuth flow."""
    provider = _get_bitbucket_provider()
    settings = get_settings()
    state = secrets.token_urlsafe(32)

    # Store user_id + state in Redis with short TTL
    # We embed user_id in the OAuth state so the callback can identify the user
    r = await _get_redis()
    try:
        state_data = json.dumps({"user_id": str(user.user_id), "state": state})
        await r.setex(f"git_oauth:bitbucket:{state}", _OAUTH_STATE_TTL, state_data)
    finally:
        await r.aclose()

    # Build redirect URI
    redirect_uri = f"{settings.git_oauth_redirect_uri}/bitbucket/oauth/callback"
    authorize_url = provider.get_auth_url(redirect_uri, state)

    logger.info("bitbucket_oauth_started", user_id=str(user.user_id))
    return {"authorize_url": authorize_url, "state": state}


@router.get("/credentials/bitbucket/oauth/callback")
async def bitbucket_oauth_callback(
    code: str,
    state: str,
) -> dict:
    """Bitbucket OAuth callback endpoint.

    Bitbucket redirects here after user authorization with code and state parameters.
    This endpoint is public (no auth required) because browser redirects can't include auth headers.
    The user_id is retrieved from the state stored in Redis.
    """
    from uuid import UUID
    provider = _get_bitbucket_provider()
    settings = get_settings()

    # Retrieve user_id from state stored in Redis
    r = await _get_redis()
    try:
        state_data_raw = await r.get(f"git_oauth:bitbucket:{state}")
        if not state_data_raw:
            raise HTTPException(400, "Invalid or expired OAuth state")
        state_data = json.loads(state_data_raw.decode())
        await r.delete(f"git_oauth:bitbucket:{state}")
    finally:
        await r.aclose()

    # Extract user_id from state data
    try:
        user_id = UUID(state_data["user_id"])
    except (KeyError, ValueError):
        raise HTTPException(400, "Invalid state format")

    # Exchange code for tokens
    redirect_uri = f"{settings.git_oauth_redirect_uri}/bitbucket/oauth/callback"
    try:
        tokens = await provider.exchange_code(code, redirect_uri)
    except ValueError as e:
        logger.error("bitbucket_oauth_exchange_failed", error=str(e))
        raise HTTPException(400, str(e))

    # Get user info
    try:
        user_info = await provider.get_user_info(tokens.access_token)
    except Exception as e:
        logger.error("bitbucket_userinfo_failed", error=str(e))
        user_info = None

    # Store credentials
    store = _get_credential_store()
    factory = get_session_factory()
    async with factory() as session:
        from datetime import datetime, timezone
        expires_dt = datetime.fromtimestamp(tokens.expires_at / 1000, tz=timezone.utc)

        creds_to_store = {
            "bitbucket_token": tokens.access_token,
            "bitbucket_refresh_token": tokens.refresh_token,
            "bitbucket_token_expires_at": expires_dt.isoformat(),
            "bitbucket_token_scope": tokens.scope or "",
        }
        if user_info:
            creds_to_store["bitbucket_username"] = user_info.username

        await store.set_many(session, user_id, "bitbucket", creds_to_store)

    logger.info(
        "bitbucket_oauth_success",
        user_id=str(user_id),
        username=user_info.username if user_info else None,
    )

    # Redirect to success page
    from fastapi.responses import RedirectResponse
    return RedirectResponse(
        url=f"{settings.portal_oauth_redirect_uri.replace('/api/settings/credentials', '')}/settings?oauth=bitbucket&status=success",
        status_code=302,
    )


@router.post("/credentials/bitbucket/oauth/refresh")
async def bitbucket_oauth_refresh(user: PortalUser = Depends(require_auth)) -> dict:
    """Manually refresh Bitbucket OAuth token."""
    provider = _get_bitbucket_provider()
    store = _get_credential_store()
    factory = get_session_factory()

    async with factory() as session:
        refresh_token = await store.get(session, user.user_id, "bitbucket", "bitbucket_refresh_token")

    if not refresh_token:
        raise HTTPException(400, "No refresh token available")

    new_tokens = await provider.refresh_access_token(refresh_token)
    if not new_tokens:
        raise HTTPException(502, "Token refresh failed")

    # Update stored credentials
    async with factory() as session:
        from datetime import datetime, timezone
        expires_dt = datetime.fromtimestamp(new_tokens.expires_at / 1000, tz=timezone.utc)

        creds_to_store = {
            "bitbucket_token": new_tokens.access_token,
            "bitbucket_refresh_token": new_tokens.refresh_token,
            "bitbucket_token_expires_at": expires_dt.isoformat(),
        }
        if new_tokens.scope:
            creds_to_store["bitbucket_token_scope"] = new_tokens.scope

        await store.set_many(session, user.user_id, "bitbucket", creds_to_store)

    logger.info("bitbucket_oauth_refresh_success", user_id=str(user.user_id))
    return {"status": "ok", "expires_in": new_tokens.expires_in}


@router.get("/credentials/bitbucket/status")
async def bitbucket_credential_status(user: PortalUser = Depends(require_auth)) -> dict:
    """Return status of Bitbucket credentials."""
    store = _get_credential_store()
    factory = get_session_factory()

    async with factory() as session:
        token = await store.get(session, user.user_id, "bitbucket", "bitbucket_token")
        username = await store.get(session, user.user_id, "bitbucket", "bitbucket_username")
        scope = await store.get(session, user.user_id, "bitbucket", "bitbucket_token_scope")
        expires_at_str = await store.get(session, user.user_id, "bitbucket", "bitbucket_token_expires_at")

    if not token:
        return {"configured": False}

    # Parse expiry
    expires_in_seconds = None
    is_expired = False
    needs_refresh = False
    if expires_at_str:
        from datetime import datetime, timezone
        try:
            expires_at = datetime.fromisoformat(expires_at_str)
            now = datetime.now(timezone.utc)
            expires_in_seconds = int((expires_at - now).total_seconds())
            is_expired = expires_in_seconds <= 0
            needs_refresh = expires_in_seconds < 1800  # < 30 minutes
        except Exception:
            pass

    return {
        "configured": True,
        "username": username,
        "scopes": scope.split() if scope else [],
        "expires_at": expires_at_str,
        "expires_in_seconds": expires_in_seconds,
        "is_expired": is_expired,
        "needs_refresh": needs_refresh,
    }
