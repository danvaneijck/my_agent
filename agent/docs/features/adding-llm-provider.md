# Adding a New LLM Provider

> **Quick Context**: Add support for new LLM APIs (Claude alternatives, GPT alternatives, Gemini alternatives)

## Related Files

- `agent/core/llm_router/router.py` — Main router that registers providers
- `agent/core/llm_router/providers/base.py` — Base provider interface
- `agent/core/llm_router/providers/anthropic.py` — Anthropic provider example
- `agent/core/llm_router/providers/openai_provider.py` — OpenAI provider example
- `agent/core/llm_router/providers/google.py` — Google provider example
- `agent/shared/shared/config.py` — Configuration settings

## Related Documentation

- [LLM Router](../core/llm-router.md) — Router internals
- [Core Endpoints](../api-reference/core-endpoints.md) — `/message` endpoint
- [Code Standards](../development/code-standards.md) — Coding conventions

## When to Use This Guide

Read this when you need to:
- Add support for a new LLM API (Cohere, Mistral, Llama, etc.)
- Implement a custom LLM endpoint
- Add provider-specific features or optimizations

## Prerequisites

- Understanding of async Python
- Familiarity with the LLM API you're integrating
- Understanding of tool calling / function calling formats

---

## Overview

The LLM Router provides a provider abstraction layer that:
1. Normalizes different LLM API formats to a common interface
2. Handles fallback chains when primary models fail
3. Manages provider registration based on API key availability
4. Routes requests based on model name patterns

---

## Step-by-Step Implementation

### Step 1: Create Provider Class

Create a new file in `agent/core/llm_router/providers/`:

```python
# agent/core/llm_router/providers/my_provider.py

from __future__ import annotations

import structlog
from typing import Any

from core.llm_router.providers.base import BaseLLMProvider, LLMResponse, ToolCall

logger = structlog.get_logger()


class MyProvider(BaseLLMProvider):
    """Provider for My Custom LLM API."""

    def __init__(self, api_key: str):
        """Initialize provider with API key.

        Args:
            api_key: API key for authentication
        """
        self.api_key = api_key
        # Initialize your client here
        # self.client = MyLLMClient(api_key=api_key)

    def get_supported_models(self) -> list[str]:
        """Return list of model name patterns this provider handles.

        The router uses these patterns to determine which provider to use.
        Patterns can be:
        - Exact matches: "my-model-v1"
        - Prefix matches: "my-*" (matches "my-model-v1", "my-model-v2", etc.)

        Returns:
            List of model name patterns
        """
        return [
            "my-model-v1",
            "my-model-v2",
            "my-custom-*",  # Matches any model starting with "my-custom-"
        ]

    async def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 1.0,
        max_tokens: int = 4000,
    ) -> LLMResponse:
        """Send completion request to the LLM API.

        Args:
            messages: List of messages in format:
                [
                    {"role": "user", "content": "Hello"},
                    {"role": "assistant", "content": "Hi there"},
                    ...
                ]
            model: Model identifier (e.g., "my-model-v1")
            tools: Optional list of tool definitions (function calling schema)
            temperature: Sampling temperature (0.0 to 2.0)
            max_tokens: Maximum tokens in response

        Returns:
            LLMResponse object with normalized response
        """
        try:
            # Convert messages to provider-specific format if needed
            provider_messages = self._convert_messages(messages)

            # Convert tools to provider-specific format
            provider_tools = None
            if tools:
                provider_tools = self._convert_tools(tools)

            # Make API call
            # response = await self.client.complete(
            #     model=model,
            #     messages=provider_messages,
            #     tools=provider_tools,
            #     temperature=temperature,
            #     max_tokens=max_tokens,
            # )

            # For now, return a mock response
            # Replace this with actual API call
            response = {
                "content": "This is a mock response",
                "stop_reason": "end_turn",
                "tool_calls": [],
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 50,
                }
            }

            # Normalize response to LLMResponse format
            return self._normalize_response(response)

        except Exception as e:
            logger.error("llm_api_error", provider="my_provider", error=str(e))
            raise

    def _convert_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert standard message format to provider-specific format.

        Standard format:
            [{"role": "user", "content": "text"}, ...]

        Some providers may need different field names or structure.
        """
        # If your provider uses the same format, just return as-is
        return messages

        # Example conversion:
        # return [
        #     {
        #         "role": msg["role"],
        #         "text": msg["content"],  # Different field name
        #     }
        #     for msg in messages
        # ]

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert standard tool format to provider-specific format.

        Standard format (OpenAI function calling style):
            [{
                "type": "function",
                "function": {
                    "name": "tool_name",
                    "description": "What it does",
                    "parameters": {...JSON schema...}
                }
            }, ...]
        """
        # If your provider uses OpenAI format, return as-is
        return tools

        # Example conversion for provider with different format:
        # return [
        #     {
        #         "name": tool["function"]["name"],
        #         "description": tool["function"]["description"],
        #         "input_schema": tool["function"]["parameters"],
        #     }
        #     for tool in tools
        # ]

    def _normalize_response(self, response: dict[str, Any]) -> LLMResponse:
        """Normalize provider response to LLMResponse format.

        Args:
            response: Raw response from provider API

        Returns:
            LLMResponse with normalized fields
        """
        # Extract tool calls if present
        tool_calls: list[ToolCall] = []
        if response.get("tool_calls"):
            for tc in response["tool_calls"]:
                tool_calls.append(
                    ToolCall(
                        name=tc["name"],
                        arguments=tc["arguments"],
                    )
                )

        return LLMResponse(
            content=response.get("content", ""),
            stop_reason=response.get("stop_reason", "end_turn"),
            tool_calls=tool_calls,
            input_tokens=response.get("usage", {}).get("input_tokens", 0),
            output_tokens=response.get("usage", {}).get("output_tokens", 0),
        )
```

### Step 2: Register Provider in Router

Edit `agent/core/llm_router/router.py`:

```python
# agent/core/llm_router/router.py

from core.llm_router.providers.anthropic import AnthropicProvider
from core.llm_router.providers.openai_provider import OpenAIProvider
from core.llm_router.providers.google import GoogleProvider
from core.llm_router.providers.my_provider import MyProvider  # Add import

class LLMRouter:
    def __init__(self, settings):
        self.settings = settings
        self.providers: dict[str, BaseLLMProvider] = {}

        # Register providers based on available API keys
        if settings.anthropic_api_key:
            self.providers["anthropic"] = AnthropicProvider(settings.anthropic_api_key)

        if settings.openai_api_key:
            self.providers["openai"] = OpenAIProvider(settings.openai_api_key)

        if settings.google_api_key:
            self.providers["google"] = GoogleProvider(settings.google_api_key)

        # Add your provider
        if settings.my_provider_api_key:
            self.providers["my_provider"] = MyProvider(settings.my_provider_api_key)
```

### Step 3: Add Configuration

Edit `agent/shared/shared/config.py`:

```python
# agent/shared/shared/config.py

class Settings(BaseSettings):
    # Existing settings...
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None

    # Add your provider's API key
    my_provider_api_key: str | None = None
```

Update `agent/.env.example`:

```bash
# Existing entries...
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
GOOGLE_API_KEY=

# Add your provider
MY_PROVIDER_API_KEY=
```

### Step 4: Update Default Model and Fallback Chain

In `agent/shared/shared/config.py`, you can set your new model as default:

```python
class Settings(BaseSettings):
    # ...
    default_model: str = "my-model-v1"  # or keep existing default

    # Update fallback chain to include your models
    fallback_chain: str = "my-model-v1,claude-sonnet-4,gpt-4o,gemini-2.0-flash"
```

---

## Testing Your Provider

### Step 1: Unit Test

Create `agent/core/llm_router/providers/test_my_provider.py`:

```python
import pytest
from core.llm_router.providers.my_provider import MyProvider
from core.llm_router.providers.base import LLMResponse

@pytest.mark.asyncio
async def test_my_provider_basic():
    """Test basic completion."""
    provider = MyProvider(api_key="test-key")

    messages = [{"role": "user", "content": "Hello"}]

    response = await provider.complete(
        messages=messages,
        model="my-model-v1",
        max_tokens=100,
    )

    assert isinstance(response, LLMResponse)
    assert response.content
    assert response.stop_reason in ["end_turn", "max_tokens", "tool_use"]

@pytest.mark.asyncio
async def test_my_provider_with_tools():
    """Test completion with tool calling."""
    provider = MyProvider(api_key="test-key")

    messages = [{"role": "user", "content": "Search for Python tutorials"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"}
                    }
                }
            }
        }
    ]

    response = await provider.complete(
        messages=messages,
        model="my-model-v1",
        tools=tools,
        max_tokens=100,
    )

    assert isinstance(response, LLMResponse)
    # Check if tool was called (if your model supports it)
    # assert len(response.tool_calls) > 0
```

Run tests:
```bash
pytest agent/core/llm_router/providers/test_my_provider.py -v
```

### Step 2: Integration Test

Test through the core API:

```bash
# Start the system
make up

# Make a test request
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "test",
    "platform_user_id": "test-user",
    "platform_channel_id": "test-channel",
    "content": "Hello, test my new provider",
    "model": "my-model-v1"
  }'
```

### Step 3: Test Fallback

Test that fallback works if your provider fails:

1. Set an invalid API key in `.env`
2. Make a request with your model as primary but valid fallback:
   ```json
   {
     "content": "Test message",
     "model": "my-model-v1",
     // Router will fall back to next in chain
   }
   ```
3. Check logs to see fallback behavior

---

## Common Patterns

### Streaming Support

If your provider supports streaming:

```python
async def stream_complete(
    self,
    messages: list[dict[str, Any]],
    model: str,
    tools: list[dict[str, Any]] | None = None,
    temperature: float = 1.0,
    max_tokens: int = 4000,
) -> AsyncGenerator[str, None]:
    """Stream completion response."""
    async for chunk in self.client.stream(
        model=model,
        messages=messages,
        tools=tools,
        temperature=temperature,
        max_tokens=max_tokens,
    ):
        if chunk.get("delta"):
            yield chunk["delta"]
```

### Vision/Image Support

If your provider supports images:

```python
def _convert_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert messages, handling image content."""
    converted = []
    for msg in messages:
        if isinstance(msg["content"], list):
            # Message has mixed text and images
            converted.append({
                "role": msg["role"],
                "content": msg["content"],  # Keep as list
            })
        else:
            # Text-only message
            converted.append({
                "role": msg["role"],
                "content": msg["content"],
            })
    return converted
```

### Custom Token Counting

If your provider has specific token counting:

```python
def count_tokens(self, text: str, model: str) -> int:
    """Count tokens for this provider's models."""
    # Use provider-specific tokenizer
    # return self.client.count_tokens(text, model)

    # Or approximate
    return len(text) // 4
```

---

## Troubleshooting

### Provider Not Being Used

**Problem**: Requests still go to old provider

**Solutions**:
1. Check API key is set in `.env`
2. Restart services: `make restart-core`
3. Check model name matches patterns in `get_supported_models()`
4. Check logs for provider registration: `make logs-core | grep provider`

### Tool Calling Not Working

**Problem**: LLM doesn't call tools

**Solutions**:
1. Verify tool format conversion in `_convert_tools()`
2. Check if your LLM supports function calling
3. Verify tool definitions are valid JSON schema
4. Check response parsing in `_normalize_response()`

### Authentication Errors

**Problem**: 401 or 403 errors

**Solutions**:
1. Verify API key is correct
2. Check API key has required permissions
3. Verify API endpoint URL
4. Check for IP allowlisting requirements

---

## Best Practices

1. **Error Handling**: Catch provider-specific errors and raise descriptive exceptions
2. **Logging**: Log all API calls with `structlog` for debugging
3. **Token Counting**: Implement accurate token counting for budget tracking
4. **Testing**: Test with and without tools, with various message formats
5. **Documentation**: Document provider-specific quirks and limitations

---

## Example: Complete Cohere Provider

```python
# agent/core/llm_router/providers/cohere.py

import cohere
from core.llm_router.providers.base import BaseLLMProvider, LLMResponse, ToolCall

class CohereProvider(BaseLLMProvider):
    def __init__(self, api_key: str):
        self.client = cohere.AsyncClient(api_key=api_key)

    def get_supported_models(self) -> list[str]:
        return ["command-r", "command-r-plus", "command-*"]

    async def complete(
        self,
        messages: list[dict[str, Any]],
        model: str,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 1.0,
        max_tokens: int = 4000,
    ) -> LLMResponse:
        # Convert to Cohere's chat format
        chat_history = []
        for msg in messages[:-1]:
            chat_history.append({
                "role": "USER" if msg["role"] == "user" else "CHATBOT",
                "message": msg["content"],
            })

        # Last message is the current query
        message = messages[-1]["content"]

        # Convert tools
        cohere_tools = None
        if tools:
            cohere_tools = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"]["description"],
                    "parameter_definitions": t["function"]["parameters"]["properties"],
                }
                for t in tools
            ]

        # Make request
        response = await self.client.chat(
            model=model,
            message=message,
            chat_history=chat_history,
            tools=cohere_tools,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Normalize response
        tool_calls = []
        if response.tool_calls:
            for tc in response.tool_calls:
                tool_calls.append(
                    ToolCall(
                        name=tc.name,
                        arguments=tc.parameters,
                    )
                )

        return LLMResponse(
            content=response.text,
            stop_reason="tool_use" if tool_calls else "end_turn",
            tool_calls=tool_calls,
            input_tokens=response.meta.tokens.input_tokens,
            output_tokens=response.meta.tokens.output_tokens,
        )
```

---

## Next Steps

After implementing your provider:

1. Update [LLM Router Documentation](../core/llm-router.md) with provider details
2. Add provider to README.md provider list
3. Update CLAUDE.md with supported models
4. Create user-facing documentation for configuration
5. Add provider-specific troubleshooting to docs

---

**Related Documentation:**
- [LLM Router](../core/llm-router.md) — Router architecture
- [Code Standards](../development/code-standards.md) — Coding conventions
- [Testing](../development/testing.md) — Testing strategies

[Back to Documentation Index](../INDEX.md)
