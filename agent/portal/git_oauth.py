"""OAuth providers for git platforms (GitHub, Bitbucket, GitLab, etc.)."""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from urllib.parse import urlencode

import httpx
import structlog

logger = structlog.get_logger()

# API endpoints
GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE = "https://api.github.com"

BITBUCKET_AUTH_URL = "https://bitbucket.org/site/oauth2/authorize"
BITBUCKET_TOKEN_URL = "https://bitbucket.org/site/oauth2/access_token"
BITBUCKET_API_BASE = "https://api.bitbucket.org/2.0"


@dataclass
class GitOAuthTokens:
    """Normalized OAuth tokens from git provider."""

    provider: str
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None  # seconds
    expires_at: int | None = None  # Unix timestamp (ms)
    scope: str | None = None
    token_type: str = "Bearer"


@dataclass
class GitUserInfo:
    """Normalized user info from git provider."""

    username: str
    email: str | None = None
    name: str | None = None


class GitOAuthProvider(ABC):
    """Abstract OAuth provider for git platforms."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (github, bitbucket, gitlab)."""
        ...

    @abstractmethod
    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        """Build authorization URL."""
        ...

    @abstractmethod
    async def exchange_code(
        self, code: str, redirect_uri: str
    ) -> GitOAuthTokens:
        """Exchange authorization code for tokens."""
        ...

    @abstractmethod
    async def refresh_access_token(
        self, refresh_token: str
    ) -> GitOAuthTokens | None:
        """Refresh expired access token. Returns None if not supported."""
        ...

    @abstractmethod
    async def get_user_info(self, access_token: str) -> GitUserInfo:
        """Get authenticated user info (username, email, etc.)."""
        ...


class GitHubOAuthProvider(GitOAuthProvider):
    """GitHub OAuth 2.0 provider.

    Note: GitHub OAuth tokens do not expire by default (unless using
    fine-grained tokens with expiration enabled). Refresh tokens are
    only issued if expiration is configured.
    """

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    @property
    def name(self) -> str:
        return "github"

    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        """Build GitHub OAuth authorization URL.

        Scopes requested:
        - repo: Full control of private repositories
        - user:email: Access to user email addresses
        - workflow: Update GitHub Actions workflow files
        """
        params = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": redirect_uri,
                "scope": "repo user:email workflow",
                "state": state,
                "allow_signup": "false",  # Don't allow new signups during OAuth
            }
        )
        return f"{GITHUB_AUTH_URL}?{params}"

    async def exchange_code(
        self, code: str, redirect_uri: str
    ) -> GitOAuthTokens:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                GITHUB_TOKEN_URL,
                data={
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                },
                headers={"Accept": "application/json"},
            )

            if resp.status_code != 200:
                logger.warning(
                    "github_token_exchange_failed",
                    status=resp.status_code,
                    body=resp.text[:500],
                )
                raise ValueError(
                    f"GitHub token exchange failed ({resp.status_code}): {resp.text[:200]}"
                )

            data = resp.json()

            if "error" in data:
                raise ValueError(
                    f"GitHub OAuth error: {data.get('error_description', data['error'])}"
                )

            # GitHub may return refresh_token if fine-grained token with expiration
            access_token = data["access_token"]
            refresh_token = data.get("refresh_token")
            expires_in = data.get("expires_in")  # Only if fine-grained with expiration
            scope = data.get("scope", "repo user:email workflow")

            # Calculate expires_at if expires_in is present
            expires_at = None
            if expires_in:
                expires_at = int(time.time() * 1000) + (expires_in * 1000)

            return GitOAuthTokens(
                provider="github",
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
                expires_at=expires_at,
                scope=scope,
                token_type="Bearer",
            )

    async def refresh_access_token(
        self, refresh_token: str
    ) -> GitOAuthTokens | None:
        """Refresh GitHub access token (only for fine-grained tokens with expiration).

        Standard GitHub OAuth tokens do not expire, so this returns None.
        Fine-grained tokens with refresh_token can be refreshed.
        """
        if not refresh_token:
            return None

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    GITHUB_TOKEN_URL,
                    data={
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                    headers={"Accept": "application/json"},
                )

                if resp.status_code != 200:
                    logger.warning(
                        "github_token_refresh_failed",
                        status=resp.status_code,
                        body=resp.text[:300],
                    )
                    return None

                data = resp.json()

                if "error" in data:
                    logger.warning(
                        "github_token_refresh_error", error=data.get("error")
                    )
                    return None

                access_token = data["access_token"]
                new_refresh_token = data.get("refresh_token", refresh_token)
                expires_in = data.get("expires_in")
                scope = data.get("scope")

                expires_at = None
                if expires_in:
                    expires_at = int(time.time() * 1000) + (expires_in * 1000)

                logger.info("github_token_refresh_success")
                return GitOAuthTokens(
                    provider="github",
                    access_token=access_token,
                    refresh_token=new_refresh_token,
                    expires_in=expires_in,
                    expires_at=expires_at,
                    scope=scope,
                    token_type="Bearer",
                )

        except Exception as e:
            logger.error("github_token_refresh_exception", error=str(e))
            return None

    async def get_user_info(self, access_token: str) -> GitUserInfo:
        """Get GitHub user information."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get user profile
            resp = await client.get(
                f"{GITHUB_API_BASE}/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )

            if resp.status_code != 200:
                raise ValueError(f"Failed to fetch GitHub user info: {resp.status_code}")

            user_data = resp.json()
            username = user_data.get("login", "")
            name = user_data.get("name")
            email = user_data.get("email")

            # If email is not public, fetch from /user/emails
            if not email:
                emails_resp = await client.get(
                    f"{GITHUB_API_BASE}/user/emails",
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
                if emails_resp.status_code == 200:
                    emails = emails_resp.json()
                    # Find primary email
                    for e in emails:
                        if e.get("primary"):
                            email = e.get("email")
                            break
                    # Fallback to first email
                    if not email and emails:
                        email = emails[0].get("email")

            return GitUserInfo(username=username, email=email, name=name)


class BitbucketOAuthProvider(GitOAuthProvider):
    """Bitbucket Cloud OAuth 2.0 provider.

    Bitbucket tokens expire after 2 hours. Refresh tokens are valid for 30 days.
    """

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret

    @property
    def name(self) -> str:
        return "bitbucket"

    def get_auth_url(self, redirect_uri: str, state: str) -> str:
        """Build Bitbucket OAuth authorization URL.

        Note: Bitbucket OAuth consumers have a fixed callback URL configured
        in the consumer settings. The redirect_uri parameter is not used.
        """
        params = urlencode(
            {
                "client_id": self.client_id,
                "response_type": "code",
                "state": state,
            }
        )
        return f"{BITBUCKET_AUTH_URL}?{params}"

    async def exchange_code(
        self, code: str, redirect_uri: str
    ) -> GitOAuthTokens:
        """Exchange authorization code for access token.

        Bitbucket uses HTTP Basic Auth for token exchange.
        """
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                BITBUCKET_TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                },
                auth=(self.client_id, self.client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

            if resp.status_code != 200:
                logger.warning(
                    "bitbucket_token_exchange_failed",
                    status=resp.status_code,
                    body=resp.text[:500],
                )
                raise ValueError(
                    f"Bitbucket token exchange failed ({resp.status_code}): {resp.text[:200]}"
                )

            data = resp.json()

            if "error" in data:
                raise ValueError(
                    f"Bitbucket OAuth error: {data.get('error_description', data['error'])}"
                )

            access_token = data["access_token"]
            refresh_token = data["refresh_token"]
            expires_in = data.get("expires_in", 7200)  # Default 2 hours
            scope = data.get("scope", "")

            # Calculate expires_at
            expires_at = int(time.time() * 1000) + (expires_in * 1000)

            logger.info("bitbucket_token_exchange_success", expires_in=expires_in)
            return GitOAuthTokens(
                provider="bitbucket",
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=expires_in,
                expires_at=expires_at,
                scope=scope,
                token_type="Bearer",
            )

    async def refresh_access_token(
        self, refresh_token: str
    ) -> GitOAuthTokens | None:
        """Refresh Bitbucket access token using refresh token."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    BITBUCKET_TOKEN_URL,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": refresh_token,
                    },
                    auth=(self.client_id, self.client_secret),
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

                if resp.status_code != 200:
                    logger.warning(
                        "bitbucket_token_refresh_failed",
                        status=resp.status_code,
                        body=resp.text[:300],
                    )
                    return None

                data = resp.json()

                if "error" in data:
                    logger.warning(
                        "bitbucket_token_refresh_error", error=data.get("error")
                    )
                    return None

                access_token = data["access_token"]
                new_refresh_token = data.get("refresh_token", refresh_token)
                expires_in = data.get("expires_in", 7200)
                scope = data.get("scope", "")

                expires_at = int(time.time() * 1000) + (expires_in * 1000)

                logger.info("bitbucket_token_refresh_success", expires_in=expires_in)
                return GitOAuthTokens(
                    provider="bitbucket",
                    access_token=access_token,
                    refresh_token=new_refresh_token,
                    expires_in=expires_in,
                    expires_at=expires_at,
                    scope=scope,
                    token_type="Bearer",
                )

        except Exception as e:
            logger.error("bitbucket_token_refresh_exception", error=str(e))
            return None

    async def get_user_info(self, access_token: str) -> GitUserInfo:
        """Get Bitbucket user information."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{BITBUCKET_API_BASE}/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )

            if resp.status_code != 200:
                raise ValueError(
                    f"Failed to fetch Bitbucket user info: {resp.status_code}"
                )

            user_data = resp.json()
            username = user_data.get("username", "")
            name = user_data.get("display_name")

            # Fetch email from /user/emails
            email = None
            emails_resp = await client.get(
                f"{BITBUCKET_API_BASE}/user/emails",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/json",
                },
            )
            if emails_resp.status_code == 200:
                emails_data = emails_resp.json()
                values = emails_data.get("values", [])
                # Find primary email
                for e in values:
                    if e.get("is_primary"):
                        email = e.get("email")
                        break
                # Fallback to first email
                if not email and values:
                    email = values[0].get("email")

            return GitUserInfo(username=username, email=email, name=name)
