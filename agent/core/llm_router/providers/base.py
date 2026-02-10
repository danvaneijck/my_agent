"""Abstract LLM provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel

from shared.schemas.tools import ToolCall


class LLMResponse(BaseModel):
    """Standardized response from any LLM provider."""

    content: str | None = None
    tool_calls: list[ToolCall] = []
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    stop_reason: str = ""  # end_turn, tool_use, max_tokens
    # Anthropic prompt caching metrics (0 for other providers)
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "",
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat completion request."""
        ...

    @abstractmethod
    async def embed(self, text: str, model: str = "") -> list[float]:
        """Generate an embedding vector for the given text."""
        ...
