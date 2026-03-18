"""Shared Claude Code OAuth token refresh utility.

Used by both the ``claude_code`` module (container credential mounts) and the
``ClaudeCodeOAuthProvider`` (LLM provider using subscription tokens).
"""

from __future__ import annotations

import json
import time

import httpx
import structlog

logger = structlog.get_logger()

# Anthropic OAuth constants (same as Claude Code CLI uses)
CLAUDE_CODE_CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
CLAUDE_OAUTH_TOKEN_URL = "https://console.anthropic.com/v1/oauth/token"


def parse_oauth_credentials(credentials_json: str) -> dict | None:
    """Parse and validate Claude Code OAuth credentials.

    Returns the ``claudeAiOauth`` dict if valid, or ``None``.
    """
    try:
        creds = json.loads(credentials_json)
        oauth = creds.get("claudeAiOauth", {})
        if oauth and (oauth.get("accessToken") or oauth.get("access_token")):
            return oauth
    except (json.JSONDecodeError, TypeError):
        pass
    return None


def get_access_token(credentials_json: str) -> str | None:
    """Extract the current access token from credentials JSON."""
    oauth = parse_oauth_credentials(credentials_json)
    if not oauth:
        return None
    return oauth.get("accessToken") or oauth.get("access_token")


def is_token_fresh(credentials_json: str, threshold_ms: int = 5 * 60 * 1000) -> bool:
    """Check whether the OAuth access token has more than *threshold_ms* remaining."""
    oauth = parse_oauth_credentials(credentials_json)
    if not oauth:
        return False
    expires_at_ms = oauth.get("expiresAt") or oauth.get("expires_at", 0)
    if not expires_at_ms:
        return False  # unknown expiry — treat as stale
    now_ms = int(time.time() * 1000)
    return (expires_at_ms - now_ms) > threshold_ms


async def refresh_oauth_token(
    credentials_json: str,
    threshold_ms: int = 5 * 60 * 1000,
    user_id: str | None = None,
) -> tuple[str, str, bool]:
    """Proactively refresh Claude OAuth tokens if expiring within *threshold_ms*.

    Returns ``(access_token, updated_credentials_json, was_refreshed)``.

    On refresh failure the original credentials are returned so the caller can
    still attempt to use the (possibly still valid) token.
    """
    try:
        creds = json.loads(credentials_json)
        oauth = creds.get("claudeAiOauth", {})
        if not oauth:
            token = oauth.get("accessToken") or oauth.get("access_token", "")
            return token, credentials_json, False

        access_token = oauth.get("accessToken") or oauth.get("access_token", "")
        expires_at_ms = oauth.get("expiresAt") or oauth.get("expires_at", 0)
        now_ms = int(time.time() * 1000)

        if expires_at_ms and (expires_at_ms - now_ms) > threshold_ms:
            # Token is still fresh — no refresh needed
            return access_token, credentials_json, False

        refresh_tok = oauth.get("refreshToken") or oauth.get("refresh_token")
        if not refresh_tok:
            logger.warning("token_expiring_no_refresh_token", user_id=user_id)
            return access_token, credentials_json, False

        logger.info(
            "proactive_token_refresh",
            user_id=user_id,
            expires_in_ms=max(0, expires_at_ms - now_ms) if expires_at_ms else 0,
        )

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                CLAUDE_OAUTH_TOKEN_URL,
                json={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_tok,
                    "client_id": CLAUDE_CODE_CLIENT_ID,
                },
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code != 200:
                logger.warning(
                    "proactive_token_refresh_failed",
                    user_id=user_id,
                    status=resp.status_code,
                )
                return access_token, credentials_json, False

            new_tokens = resp.json()

        # Update the credentials structure
        new_now_ms = int(time.time() * 1000)
        expires_in = new_tokens.get("expires_in", 28800)
        new_access_token = new_tokens["access_token"]
        oauth["accessToken"] = new_access_token
        if new_tokens.get("refresh_token"):
            oauth["refreshToken"] = new_tokens["refresh_token"]
        oauth["expiresAt"] = new_now_ms + (expires_in * 1000)
        creds["claudeAiOauth"] = oauth
        updated_json = json.dumps(creds)

        logger.info("proactive_token_refresh_success", user_id=user_id)
        return new_access_token, updated_json, True

    except Exception as e:
        logger.warning("proactive_token_refresh_error", user_id=user_id, error=str(e))
        # Return whatever token we have — caller decides whether to proceed
        try:
            creds = json.loads(credentials_json)
            token = creds.get("claudeAiOauth", {}).get("accessToken", "")
            return token, credentials_json, False
        except Exception:
            return "", credentials_json, False


async def refresh_and_persist(
    credentials_json: str,
    user_id: str,
    threshold_ms: int = 5 * 60 * 1000,
    credential_store=None,
    session_factory=None,
) -> str:
    """Refresh OAuth tokens and persist to DB if refreshed.

    Convenience wrapper that combines :func:`refresh_oauth_token` with
    database persistence.  Falls back gracefully on any failure.

    Returns the (possibly updated) credentials JSON string.
    """
    access_token, updated_json, was_refreshed = await refresh_oauth_token(
        credentials_json, threshold_ms=threshold_ms, user_id=user_id,
    )

    if was_refreshed and credential_store and session_factory:
        try:
            async with session_factory() as session:
                await credential_store.set(
                    session, user_id, "claude_code", "credentials_json",
                    updated_json,
                )
            logger.info("proactive_token_refresh_persisted", user_id=user_id)
        except Exception as e:
            logger.warning("proactive_token_refresh_persist_failed", error=str(e))

    return updated_json
