"""Claude Code OAuth LLM provider.

Uses a Claude Code subscription's OAuth access token to authenticate with
the Anthropic API via Bearer auth, instead of an ``x-api-key`` header.

This lets users with a Claude Code subscription (e.g. Max plan) use the
agent system for regular chat without a separate Anthropic API key.
"""

from __future__ import annotations

import asyncio
import os

import structlog
from anthropic import AsyncAnthropic

from core.llm_router.providers.anthropic import AnthropicProvider
from core.llm_router.providers.base import LLMResponse
from shared.oauth_refresh import get_access_token, refresh_oauth_token

logger = structlog.get_logger()

# Lock to serialize env var manipulation during client creation
_env_lock = asyncio.Lock()


def _create_oauth_client(access_token: str) -> AsyncAnthropic:
    """Create an AsyncAnthropic client using only OAuth Bearer auth.

    The SDK auto-resolves ``ANTHROPIC_API_KEY`` from the environment.
    If both ``api_key`` and ``auth_token`` are set, the API bills to
    the API key.  We temporarily remove the env var so only the OAuth
    token is sent.
    """
    saved = os.environ.pop("ANTHROPIC_API_KEY", None)
    try:
        client = AsyncAnthropic(auth_token=access_token)
    finally:
        if saved is not None:
            os.environ["ANTHROPIC_API_KEY"] = saved
    return client


class ClaudeCodeOAuthProvider(AnthropicProvider):
    """Anthropic provider authenticated via Claude Code OAuth tokens.

    Subclasses :class:`AnthropicProvider` — all tool conversion, message
    formatting, and prompt caching logic is inherited unchanged.  The only
    difference is how the HTTP client authenticates (Bearer token vs API key)
    and the proactive token refresh before each ``chat()`` call.
    """

    def __init__(
        self,
        credentials_json: str,
        credential_store=None,
        user_id: str | None = None,
        session_factory=None,
    ) -> None:
        self._credentials_json = credentials_json
        self._credential_store = credential_store
        self._user_id = user_id
        self._session_factory = session_factory
        self._refresh_lock = asyncio.Lock()

        access_token = get_access_token(credentials_json)
        if not access_token:
            raise ValueError("No OAuth access token found in credentials_json")

        # Use auth_token= for Bearer auth (not api_key= which sets x-api-key).
        # Temporarily remove ANTHROPIC_API_KEY from env so the SDK doesn't
        # pick it up and send both x-api-key AND Authorization headers —
        # if both are present the API bills to the API key, not the subscription.
        self.client = _create_oauth_client(access_token)
        logger.info(
            "claude_code_oauth_provider_initialized",
            user_id=user_id,
            has_credential_store=credential_store is not None,
        )

    async def _ensure_fresh_token(self) -> None:
        """Refresh the OAuth token if it's about to expire.

        Uses a lock to prevent concurrent refresh attempts when multiple
        agent loop iterations run in quick succession.
        """
        async with self._refresh_lock:
            access_token, updated_json, was_refreshed = await refresh_oauth_token(
                self._credentials_json,
                threshold_ms=5 * 60 * 1000,  # 5 min threshold
                user_id=self._user_id,
            )

            if was_refreshed:
                self._credentials_json = updated_json
                self.client = _create_oauth_client(access_token)
                logger.info(
                    "claude_code_oauth_token_refreshed",
                    user_id=self._user_id,
                )

                # Persist refreshed token to DB for future requests
                if self._credential_store and self._session_factory:
                    try:
                        async with self._session_factory() as session:
                            await self._credential_store.set(
                                session,
                                self._user_id,
                                "claude_code",
                                "credentials_json",
                                updated_json,
                            )
                    except Exception as e:
                        logger.warning(
                            "oauth_token_persist_failed",
                            user_id=self._user_id,
                            error=str(e),
                        )

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Chat with proactive token refresh before each call."""
        await self._ensure_fresh_token()

        try:
            return await super().chat(
                messages=messages,
                tools=tools,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
        except Exception as e:
            # On auth failure, try one more refresh and retry
            err_str = str(e).lower()
            status = getattr(e, "status_code", None)
            if status in (401, 403) or "unauthorized" in err_str or "forbidden" in err_str:
                logger.warning(
                    "oauth_auth_failure_retrying",
                    user_id=self._user_id,
                    error=str(e),
                )
                # Force refresh by using 0 threshold
                async with self._refresh_lock:
                    access_token, updated_json, was_refreshed = await refresh_oauth_token(
                        self._credentials_json,
                        threshold_ms=0,  # force refresh
                        user_id=self._user_id,
                    )
                    if was_refreshed:
                        self._credentials_json = updated_json
                        self.client = _create_oauth_client(access_token)

                        if self._credential_store and self._session_factory:
                            try:
                                async with self._session_factory() as session:
                                    await self._credential_store.set(
                                        session,
                                        self._user_id,
                                        "claude_code",
                                        "credentials_json",
                                        updated_json,
                                    )
                            except Exception:
                                pass

                        return await super().chat(
                            messages=messages,
                            tools=tools,
                            model=model,
                            max_tokens=max_tokens,
                            temperature=temperature,
                        )
            raise
