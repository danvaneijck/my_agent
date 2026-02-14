"""OAuth2 provider abstraction for multi-provider portal authentication."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import structlog

logger = structlog.get_logger()

DISCORD_API = "https://discord.com/api/v10"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@dataclass
class OAuthUserProfile:
    """Normalized user profile from an OAuth provider."""

    provider: str  # "discord" or "google"
    provider_user_id: str
    username: str
    email: str | None = None


class OAuthProvider(ABC):
    """Abstract OAuth2 provider."""

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    def get_auth_url(self, redirect_uri: str) -> str:
        ...

    @abstractmethod
    async def exchange_code(
        self, code: str, redirect_uri: str
    ) -> OAuthUserProfile:
        ...


class DiscordOAuthProvider(OAuthProvider):
    """Discord OAuth2 provider."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    @property
    def name(self) -> str:
        return "discord"

    def get_auth_url(self, redirect_uri: str) -> str:
        params = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "identify",
            }
        )
        return f"{DISCORD_API}/oauth2/authorize?{params}"

    async def exchange_code(
        self, code: str, redirect_uri: str
    ) -> OAuthUserProfile:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Exchange code for access token
            token_resp = await client.post(
                f"{DISCORD_API}/oauth2/token",
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_resp.status_code != 200:
                logger.warning(
                    "discord_token_exchange_failed",
                    status=token_resp.status_code,
                    body=token_resp.text,
                )
                raise ValueError("Discord authentication failed")
            access_token = token_resp.json()["access_token"]

            # Fetch user profile
            user_resp = await client.get(
                f"{DISCORD_API}/users/@me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_resp.status_code != 200:
                raise ValueError("Failed to fetch Discord profile")
            discord_user = user_resp.json()

        return OAuthUserProfile(
            provider="discord",
            provider_user_id=discord_user["id"],
            username=discord_user.get("global_name") or discord_user["username"],
            email=None,
        )


class GoogleOAuthProvider(OAuthProvider):
    """Google OAuth2 provider."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret

    @property
    def name(self) -> str:
        return "google"

    def get_auth_url(self, redirect_uri: str) -> str:
        params = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "access_type": "offline",
                "prompt": "select_account",
            }
        )
        return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

    async def exchange_code(
        self, code: str, redirect_uri: str
    ) -> OAuthUserProfile:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Exchange code for access token
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_resp.status_code != 200:
                logger.warning(
                    "google_token_exchange_failed",
                    status=token_resp.status_code,
                    body=token_resp.text,
                )
                raise ValueError("Google authentication failed")
            access_token = token_resp.json()["access_token"]

            # Fetch user profile
            user_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if user_resp.status_code != 200:
                raise ValueError("Failed to fetch Google profile")
            google_user = user_resp.json()

        return OAuthUserProfile(
            provider="google",
            provider_user_id=google_user["sub"],
            username=google_user.get("name") or google_user.get("email", ""),
            email=google_user.get("email"),
        )
