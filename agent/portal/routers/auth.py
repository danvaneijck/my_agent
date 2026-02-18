"""Multi-provider OAuth2 authentication endpoints."""

from __future__ import annotations

from datetime import datetime, timezone, timedelta

import jwt
import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from portal.auth import JWT_ALGORITHM, PortalUser, require_auth
from portal.oauth_providers import (
    DiscordOAuthProvider,
    GoogleOAuthProvider,
    SlackOAuthProvider,
    OAuthProvider,
    OAuthUserProfile,
)
from shared.config import get_settings
from shared.database import get_session_factory
from shared.models.user import User, UserPlatformLink

logger = structlog.get_logger()

router = APIRouter(prefix="/api/auth", tags=["auth"])

JWT_EXPIRY_HOURS = 72


class TokenExchangeRequest(BaseModel):
    code: str


# ---------------------------------------------------------------------------
# Provider helpers
# ---------------------------------------------------------------------------


def _get_discord_provider() -> DiscordOAuthProvider:
    settings = get_settings()
    if not settings.discord_client_id or not settings.discord_client_secret:
        raise HTTPException(503, "Discord OAuth not configured")
    return DiscordOAuthProvider(settings.discord_client_id, settings.discord_client_secret)


def _get_google_provider() -> GoogleOAuthProvider:
    settings = get_settings()
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(503, "Google OAuth not configured")
    return GoogleOAuthProvider(settings.google_client_id, settings.google_client_secret)


def _get_slack_provider() -> SlackOAuthProvider:
    settings = get_settings()
    if not settings.slack_client_id or not settings.slack_client_secret:
        raise HTTPException(503, "Slack OAuth not configured")
    return SlackOAuthProvider(settings.slack_client_id, settings.slack_client_secret)


def _get_redirect_uri(provider: str) -> str:
    """Build the redirect URI for a given provider."""
    settings = get_settings()
    base = settings.portal_oauth_redirect_uri.rstrip("/")
    # Support both /auth/callback (legacy) and /auth/callback/{provider} patterns.
    # If the base already ends with a provider name, strip it for the new format.
    for p in ("discord", "google", "slack"):
        if base.endswith(f"/{p}"):
            base = base[: -len(f"/{p}")]
            break
    if base.endswith("/callback"):
        base = base[: -len("/callback")]
    return f"{base}/callback/{provider}"


# ---------------------------------------------------------------------------
# Shared OAuth callback logic
# ---------------------------------------------------------------------------


async def _handle_oauth_callback(profile: OAuthUserProfile) -> dict:
    """Look up or create user from OAuth profile, return JWT + user info."""
    settings = get_settings()
    factory = get_session_factory()

    async with factory() as session:
        # Look up existing platform link
        result = await session.execute(
            select(UserPlatformLink).where(
                UserPlatformLink.platform == profile.provider,
                UserPlatformLink.platform_user_id == profile.provider_user_id,
            )
        )
        link = result.scalar_one_or_none()

        if link:
            # Existing user — fetch and update username if changed
            user_result = await session.execute(
                select(User).where(User.id == link.user_id)
            )
            user = user_result.scalar_one()
            if link.platform_username != profile.username:
                link.platform_username = profile.username
                await session.commit()
        else:
            # Self-registration: create new guest user + platform link
            user = User(
                permission_level="guest",
                token_budget_monthly=settings.default_guest_token_budget,
                tokens_used_this_month=0,
                budget_reset_at=datetime.now(timezone.utc),
            )
            session.add(user)
            await session.flush()  # get user.id

            session.add(
                UserPlatformLink(
                    user_id=user.id,
                    platform=profile.provider,
                    platform_user_id=profile.provider_user_id,
                    platform_username=profile.username,
                )
            )
            await session.commit()

            logger.info(
                "portal_self_registration",
                user_id=str(user.id),
                provider=profile.provider,
                username=profile.username,
            )

        # Ensure web platform link exists (needed for portal chat)
        web_link_result = await session.execute(
            select(UserPlatformLink).where(
                UserPlatformLink.platform == "web",
                UserPlatformLink.platform_user_id == str(user.id),
            )
        )
        web_link = web_link_result.scalar_one_or_none()
        if web_link:
            if web_link.user_id != user.id:
                web_link.user_id = user.id
                web_link.platform_username = profile.username
                await session.commit()
        else:
            session.add(
                UserPlatformLink(
                    user_id=user.id,
                    platform="web",
                    platform_user_id=str(user.id),
                    platform_username=profile.username,
                )
            )
            await session.commit()

    # Create JWT
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user.id),
        "username": profile.username,
        "permission_level": user.permission_level,
        "auth_provider": profile.provider,
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRY_HOURS),
    }
    token = jwt.encode(payload, settings.portal_jwt_secret, algorithm=JWT_ALGORITHM)

    logger.info(
        "portal_login",
        user_id=str(user.id),
        provider=profile.provider,
        username=profile.username,
        permission_level=user.permission_level,
    )

    return {
        "token": token,
        "user_id": str(user.id),
        "username": profile.username,
        "permission_level": user.permission_level,
    }


# ---------------------------------------------------------------------------
# Provider discovery
# ---------------------------------------------------------------------------


@router.get("/providers")
async def get_providers() -> dict:
    """Return which OAuth providers are configured."""
    settings = get_settings()
    providers = []
    if settings.discord_client_id and settings.discord_client_secret:
        providers.append({"name": "discord", "label": "Discord"})
    if settings.google_client_id and settings.google_client_secret:
        providers.append({"name": "google", "label": "Google"})
    if settings.slack_client_id and settings.slack_client_secret:
        providers.append({"name": "slack", "label": "Slack"})
    return {"providers": providers}


# ---------------------------------------------------------------------------
# Discord OAuth2
# ---------------------------------------------------------------------------


@router.get("/discord/url")
async def get_discord_auth_url() -> dict:
    """Return the Discord OAuth2 authorization URL."""
    provider = _get_discord_provider()
    redirect_uri = _get_redirect_uri("discord")
    return {"url": provider.get_auth_url(redirect_uri)}


@router.post("/discord/callback")
async def discord_callback(body: TokenExchangeRequest) -> dict:
    """Exchange a Discord auth code for a portal JWT."""
    provider = _get_discord_provider()
    redirect_uri = _get_redirect_uri("discord")
    try:
        profile = await provider.exchange_code(body.code, redirect_uri)
    except ValueError as e:
        raise HTTPException(401, str(e))
    return await _handle_oauth_callback(profile)


# ---------------------------------------------------------------------------
# Google OAuth2
# ---------------------------------------------------------------------------


@router.get("/google/url")
async def get_google_auth_url() -> dict:
    """Return the Google OAuth2 authorization URL."""
    provider = _get_google_provider()
    redirect_uri = _get_redirect_uri("google")
    return {"url": provider.get_auth_url(redirect_uri)}


@router.post("/google/callback")
async def google_callback(body: TokenExchangeRequest) -> dict:
    """Exchange a Google auth code for a portal JWT."""
    provider = _get_google_provider()
    redirect_uri = _get_redirect_uri("google")
    try:
        profile = await provider.exchange_code(body.code, redirect_uri)
    except ValueError as e:
        raise HTTPException(401, str(e))
    return await _handle_oauth_callback(profile)


# ---------------------------------------------------------------------------
# Slack OAuth2
# ---------------------------------------------------------------------------


@router.get("/slack/url")
async def get_slack_auth_url() -> dict:
    """Return the Slack OAuth2 authorization URL."""
    provider = _get_slack_provider()
    redirect_uri = _get_redirect_uri("slack")
    return {"url": provider.get_auth_url(redirect_uri)}


@router.post("/slack/callback")
async def slack_callback(body: TokenExchangeRequest) -> dict:
    """Exchange a Slack auth code for a portal JWT."""
    provider = _get_slack_provider()
    redirect_uri = _get_redirect_uri("slack")
    try:
        profile = await provider.exchange_code(body.code, redirect_uri)
    except ValueError as e:
        raise HTTPException(401, str(e))
    return await _handle_oauth_callback(profile)


# ---------------------------------------------------------------------------
# Current user
# ---------------------------------------------------------------------------


@router.get("/me")
async def get_current_user(user: PortalUser = Depends(require_auth)) -> dict:
    """Return the current user's info from the JWT."""
    return {
        "user_id": str(user.user_id),
        "username": user.username,
        "permission_level": user.permission_level,
    }
