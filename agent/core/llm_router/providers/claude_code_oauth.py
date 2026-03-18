"""Claude Code OAuth LLM provider.

Uses the Anthropic SDK directly with the user's Claude Code subscription
OAuth access token (``auth_token``).  This gives proper structured tool
calling, vision support, and prompt caching — identical to the regular
Anthropic provider but billed to the user's Max plan instead of an API key.
"""

from __future__ import annotations

import asyncio

import structlog
from anthropic import AsyncAnthropic, BadRequestError

from core.llm_router.providers.anthropic import AnthropicProvider
from core.llm_router.providers.base import LLMProvider, LLMResponse, PromptTooLongError
from shared.oauth_refresh import refresh_and_persist, get_access_token
from shared.schemas.tools import ToolCall

logger = structlog.get_logger()

# Default model for OAuth provider
_DEFAULT_MODEL = "claude-opus-4-6"


class ClaudeCodeCLIProvider(AnthropicProvider):
    """LLM provider using the Anthropic SDK with Claude Code OAuth tokens.

    Inherits all tool conversion, message conversion, and caching logic
    from ``AnthropicProvider``.  The only difference is authentication
    (``auth_token`` instead of ``api_key``) and automatic token refresh.
    """

    def __init__(
        self,
        credentials_json: str,
        credential_store=None,
        user_id: str | None = None,
        session_factory=None,
    ) -> None:
        # Don't call super().__init__ — we manage the client ourselves
        LLMProvider.__init__(self)

        self._credentials_json = credentials_json
        self._credential_store = credential_store
        self._user_id = user_id
        self._session_factory = session_factory

        token = get_access_token(credentials_json)
        if not token:
            raise ValueError("No OAuth access token found in credentials_json")

        self.client = self._make_client(token)

        logger.info(
            "claude_code_cli_provider_initialized",
            user_id=user_id,
        )

    @staticmethod
    def _make_client(token: str) -> AsyncAnthropic:
        """Create an AsyncAnthropic client that uses ONLY the OAuth token.

        The SDK auto-detects ``ANTHROPIC_API_KEY`` from the environment and
        sends both ``X-Api-Key`` and ``Authorization: Bearer`` headers.
        We must prevent the env var from being used so that requests are
        billed to the user's subscription, not the global API key.
        """
        import os
        # Temporarily hide the env var during client construction
        saved = os.environ.pop("ANTHROPIC_API_KEY", None)
        try:
            client = AsyncAnthropic(auth_token=token)
        finally:
            if saved is not None:
                os.environ["ANTHROPIC_API_KEY"] = saved
        return client

    async def _ensure_fresh_token(self) -> None:
        """Refresh the OAuth token if expiring soon and rebuild the client."""
        updated_json = await refresh_and_persist(
            self._credentials_json,
            user_id=self._user_id or "",
            threshold_ms=5 * 60 * 1000,
            credential_store=self._credential_store,
            session_factory=self._session_factory,
        )
        if updated_json != self._credentials_json:
            self._credentials_json = updated_json
            new_token = get_access_token(updated_json)
            if new_token:
                self.client = self._make_client(new_token)
            logger.info("claude_code_cli_token_refreshed", user_id=self._user_id)

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "claude-opus-4-6",
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat completion using the Anthropic SDK with OAuth token.

        Refreshes the token if needed, then delegates to the parent class
        which handles tool conversion, message conversion, caching, and
        response parsing.
        """
        await self._ensure_fresh_token()

        # Always use the best model available on the subscription
        effective_model = model if model and model != "None" else _DEFAULT_MODEL

        logger.info(
            "claude_oauth_sdk_call",
            user_id=self._user_id,
            model=effective_model,
        )

        return await super().chat(
            messages=messages,
            tools=tools,
            model=effective_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
