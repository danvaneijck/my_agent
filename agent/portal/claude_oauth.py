"""Shared utilities for Anthropic/Claude CLI OAuth (PKCE flow)."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time

import httpx
import structlog

logger = structlog.get_logger()

# Claude Code CLI's public OAuth client ID
CLAUDE_CODE_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"

# Endpoints
CLAUDE_OAUTH_AUTHORIZE_URL = "https://claude.ai/oauth/authorize"
CLAUDE_OAUTH_TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"
CLAUDE_OAUTH_REDIRECT_URI = "https://console.anthropic.com/oauth/code/callback"
CLAUDE_OAUTH_SCOPES = "user:inference user:profile user:sessions:claude_code"


def generate_pkce() -> tuple[str, str]:
    """Generate a PKCE code verifier and S256 challenge.

    Returns (verifier, challenge).
    """
    verifier = secrets.token_urlsafe(64)  # ~86 chars, well within 43-128 range
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_authorize_url(challenge: str, state: str) -> str:
    """Build the full Anthropic OAuth authorization URL."""
    from urllib.parse import urlencode

    params = urlencode(
        {
            "code": "true",
            "client_id": CLAUDE_CODE_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": CLAUDE_OAUTH_REDIRECT_URI,
            "scope": CLAUDE_OAUTH_SCOPES,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    return f"{CLAUDE_OAUTH_AUTHORIZE_URL}?{params}"


async def exchange_code(code: str, verifier: str) -> dict:
    """Exchange an authorization code for tokens using PKCE.

    Returns the raw token response dict from Anthropic (access_token, refresh_token, etc.).
    Raises ValueError on failure.
    """
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            CLAUDE_OAUTH_TOKEN_URL,
            json={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": CLAUDE_CODE_CLIENT_ID,
                "redirect_uri": CLAUDE_OAUTH_REDIRECT_URI,
                "code_verifier": verifier,
            },
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code != 200:
            logger.warning(
                "claude_oauth_exchange_failed",
                status=resp.status_code,
                body=resp.text[:500],
            )
            raise ValueError(
                f"Token exchange failed ({resp.status_code}): {resp.text[:200]}"
            )
        return resp.json()


async def refresh_access_token(refresh_token: str) -> dict | None:
    """Refresh an expired access token. Returns new token dict or None on failure."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                CLAUDE_OAUTH_TOKEN_URL,
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": CLAUDE_CODE_CLIENT_ID,
                },
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code == 200:
                logger.info("claude_oauth_refresh_success")
                return resp.json()
            logger.warning(
                "claude_oauth_refresh_failed",
                status=resp.status_code,
                body=resp.text[:300],
            )
    except Exception as e:
        logger.error("claude_oauth_refresh_exception", error=str(e))
    return None


def build_credentials_json(token_data: dict) -> str:
    """Build the credentials JSON string in the format Claude CLI expects.

    Accepts the raw token response from Anthropic's token endpoint.
    """
    now_ms = int(time.time() * 1000)
    expires_in = token_data.get("expires_in", 28800)  # default 8h
    scopes = token_data.get("scope", CLAUDE_OAUTH_SCOPES).split()

    creds = {
        "claudeAiOauth": {
            "accessToken": token_data["access_token"],
            "refreshToken": token_data.get("refresh_token", ""),
            "expiresAt": now_ms + (expires_in * 1000),
            "scopes": scopes,
        }
    }
    # Preserve extra fields Anthropic may return (subscriptionType, rateLimitTier)
    for key in ("subscriptionType", "subscription_type"):
        if key in token_data:
            creds["claudeAiOauth"]["subscriptionType"] = token_data[key]
    for key in ("rateLimitTier", "rate_limit_tier"):
        if key in token_data:
            creds["claudeAiOauth"]["rateLimitTier"] = token_data[key]

    return json.dumps(creds)


def parse_credentials_json(creds_raw: str) -> dict | None:
    """Parse stored credentials JSON. Returns the claudeAiOauth dict or None."""
    try:
        creds = json.loads(creds_raw)
        oauth = creds.get("claudeAiOauth", {})
        if not oauth:
            return None
        return oauth
    except (json.JSONDecodeError, TypeError):
        return None


def get_token_expiry_info(oauth: dict) -> dict:
    """Extract expiry info from parsed OAuth credentials.

    Returns dict with expires_at (ISO), expires_in_seconds, is_expired, needs_refresh.
    """
    from datetime import datetime, timezone

    expires_at_ms = oauth.get("expiresAt") or oauth.get("expires_at", 0)
    if not expires_at_ms:
        return {
            "expires_at": None,
            "expires_in_seconds": None,
            "is_expired": True,
            "needs_refresh": True,
        }

    now_ms = int(time.time() * 1000)
    expires_in_ms = expires_at_ms - now_ms
    expires_in_seconds = max(0, int(expires_in_ms / 1000))

    expires_dt = datetime.fromtimestamp(expires_at_ms / 1000, tz=timezone.utc)

    return {
        "expires_at": expires_dt.isoformat(),
        "expires_in_seconds": expires_in_seconds,
        "is_expired": expires_in_seconds <= 0,
        "needs_refresh": expires_in_seconds < 1800,  # < 30 minutes
    }
