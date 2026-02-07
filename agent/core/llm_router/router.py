"""LLM Router - routes requests to appropriate providers with fallback."""

from __future__ import annotations

import structlog

from core.llm_router.providers.base import LLMProvider, LLMResponse
from shared.config import Settings, parse_list

logger = structlog.get_logger()


def _is_bad_request(exc: Exception) -> bool:
    """Return True if the exception is a 400-class client error.

    These indicate a malformed payload (e.g. orphaned tool_result) that
    will never succeed regardless of how many providers or retries we try.
    """
    status = getattr(exc, "status_code", None)
    if isinstance(status, int) and 400 <= status < 500:
        return True
    # Some SDKs use .code instead of .status_code
    code = getattr(exc, "code", None)
    if code in (400, "400", "INVALID_ARGUMENT"):
        return True
    return False


class LLMRouter:
    """Routes LLM requests to the appropriate provider based on model name."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.providers: dict[str, LLMProvider] = {}
        self.model_map: dict[str, str] = {}  # model prefix -> provider name
        self._setup_providers()

    def _setup_providers(self) -> None:
        """Register providers based on available API keys."""
        if self.settings.anthropic_api_key:
            from core.llm_router.providers.anthropic import AnthropicProvider

            self.providers["anthropic"] = AnthropicProvider(
                self.settings.anthropic_api_key
            )
            logger.info("registered_provider", provider="anthropic")

        if self.settings.openai_api_key:
            from core.llm_router.providers.openai_provider import OpenAIProvider

            self.providers["openai"] = OpenAIProvider(self.settings.openai_api_key)
            logger.info("registered_provider", provider="openai")

        if self.settings.google_api_key:
            from core.llm_router.providers.google import GoogleProvider

            self.providers["google"] = GoogleProvider(self.settings.google_api_key)
            logger.info("registered_provider", provider="google")

        # Map model prefixes to providers
        self.model_map = {
            "claude": "anthropic",
            "gpt": "openai",
            "o1": "openai",
            "o3": "openai",
            "gemini": "google",
            "text-embedding": "openai",
        }

        # Auto-select a working default model if the configured one has no provider
        self._resolve_effective_defaults()

    def _resolve_effective_defaults(self) -> None:
        """Pick a default model and embedding model that match available providers."""
        # Default chat model: provider-aware fallback
        provider_defaults = {
            "anthropic": "claude-sonnet-4-20250514",
            "openai": "gpt-4o",
            "google": "gemini-2.0-flash",
        }
        if not self._has_provider_for(self.settings.default_model):
            for prov_name, model in provider_defaults.items():
                if prov_name in self.providers:
                    logger.info(
                        "auto_default_model",
                        configured=self.settings.default_model,
                        resolved=model,
                    )
                    self.effective_default_model = model
                    break
            else:
                self.effective_default_model = self.settings.default_model
        else:
            self.effective_default_model = self.settings.default_model

        # Embedding model: provider-aware fallback
        embed_defaults = {
            "openai": "text-embedding-3-small",
            "google": "gemini-embedding-001",
        }
        if not self._has_provider_for(self.settings.embedding_model):
            for prov_name, model in embed_defaults.items():
                if prov_name in self.providers:
                    self.effective_embedding_model = model
                    break
            else:
                self.effective_embedding_model = self.settings.embedding_model
        else:
            self.effective_embedding_model = self.settings.embedding_model

    def _has_provider_for(self, model: str) -> bool:
        """Check if a registered provider can handle this model."""
        for prefix, provider_name in self.model_map.items():
            if model.startswith(prefix):
                return provider_name in self.providers
        return False

    def _get_provider_for_model(self, model: str) -> tuple[str, LLMProvider]:
        """Find the provider that handles a given model."""
        for prefix, provider_name in self.model_map.items():
            if model.startswith(prefix):
                if provider_name in self.providers:
                    return provider_name, self.providers[provider_name]
                raise RuntimeError(
                    f"Model '{model}' requires the '{provider_name}' provider, "
                    f"but no API key is set for it."
                )

        # If no prefix match, try first available provider
        if self.providers:
            name = next(iter(self.providers))
            return name, self.providers[name]

        raise RuntimeError("No LLM providers configured. Set at least one API key.")

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str | None = None,
        task_type: str | None = None,
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Route a chat request to the appropriate provider.

        If model is specified, use it directly.
        If task_type is specified, use the configured model for that type.
        Otherwise use the default model.
        On failure, try the fallback chain.
        """
        # Determine which model to use
        if model:
            target_model = model
        elif task_type and task_type in self.settings.model_routing:
            target_model = self.settings.model_routing[task_type]
        else:
            target_model = self.effective_default_model

        # Try the target model first
        try:
            _, provider = self._get_provider_for_model(target_model)
            response = await provider.chat(
                messages=messages,
                tools=tools,
                model=target_model,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response
        except Exception as e:
            # 400-class errors mean the payload is broken — fallback won't help
            if _is_bad_request(e):
                logger.error(
                    "bad_request_no_fallback",
                    model=target_model,
                    error=str(e),
                )
                raise
            logger.warning(
                "primary_model_failed",
                model=target_model,
                error=str(e),
            )

        # Try fallback chain
        for fallback_model in parse_list(self.settings.fallback_chain):
            if fallback_model == target_model:
                continue
            try:
                _, provider = self._get_provider_for_model(fallback_model)
                response = await provider.chat(
                    messages=messages,
                    tools=tools,
                    model=fallback_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                logger.info("fallback_succeeded", model=fallback_model)
                return response
            except Exception as e:
                logger.warning(
                    "fallback_model_failed",
                    model=fallback_model,
                    error=str(e),
                )
                continue

        raise RuntimeError("All LLM providers failed. Check API keys and service status.")

    async def embed(self, text: str) -> list[float]:
        """Generate an embedding using the configured embedding model."""
        model = self.effective_embedding_model

        # Try to find a provider that supports embeddings
        try:
            _, provider = self._get_provider_for_model(model)
            return await provider.embed(text, model)
        except NotImplementedError:
            pass

        # Fall back to OpenAI if available (most common embedding provider)
        if "openai" in self.providers:
            return await self.providers["openai"].embed(text, model)

        # Try Google
        if "google" in self.providers:
            return await self.providers["google"].embed(text, "gemini-embedding-001")

        raise RuntimeError("No embedding provider available.")
