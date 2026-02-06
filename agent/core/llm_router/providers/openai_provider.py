"""OpenAI LLM provider."""

from __future__ import annotations

import asyncio

import structlog
from openai import AsyncOpenAI

from core.llm_router.providers.base import LLMProvider, LLMResponse
from shared.schemas.tools import ToolCall

logger = structlog.get_logger()


class OpenAIProvider(LLMProvider):
    """Provider for OpenAI models (GPT-4o, etc.)."""

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    def _convert_tools(self, tools: list[dict] | None) -> list[dict] | None:
        """Ensure tools are in OpenAI function calling format."""
        if not tools:
            return None
        openai_tools = []
        for tool in tools:
            if "function" in tool:
                openai_tools.append(tool)
            else:
                # Convert from our internal format
                properties = {}
                required = []
                for param in tool.get("parameters", []):
                    prop: dict = {
                        "type": param.get("type", "string"),
                        "description": param.get("description", ""),
                    }
                    if param.get("enum"):
                        prop["enum"] = param["enum"]
                    properties[param["name"]] = prop
                    if param.get("required", True):
                        required.append(param["name"])

                openai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": {
                            "type": "object",
                            "properties": properties,
                            "required": required,
                        },
                    },
                })
        return openai_tools

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """Convert messages to OpenAI format."""
        converted = []
        for msg in messages:
            if msg["role"] == "tool_call":
                import json
                converted.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": msg.get("tool_use_id", "call_" + msg.get("name", "unknown")),
                        "type": "function",
                        "function": {
                            "name": msg.get("name", ""),
                            "arguments": json.dumps(msg.get("arguments", {})),
                        },
                    }],
                })
            elif msg["role"] == "tool_result":
                converted.append({
                    "role": "tool",
                    "tool_call_id": msg.get("tool_use_id", ""),
                    "content": str(msg.get("content", "")),
                })
            else:
                converted.append({
                    "role": msg["role"],
                    "content": msg["content"],
                })
        return converted

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "gpt-4o",
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat completion to OpenAI."""
        converted_messages = self._convert_messages(messages)
        openai_tools = self._convert_tools(tools)

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": converted_messages,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools

        last_error = None
        for attempt in range(3):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                break
            except Exception as e:
                last_error = e
                logger.warning("openai_api_error", attempt=attempt, error=str(e))
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        else:
            raise last_error  # type: ignore[misc]

        choice = response.choices[0]
        content = choice.message.content
        tool_calls = []

        if choice.message.tool_calls:
            import json
            for tc in choice.message.tool_calls:
                tool_calls.append(ToolCall(
                    tool_name=tc.function.name,
                    arguments=json.loads(tc.function.arguments),
                ))

        stop_reason = "end_turn"
        if choice.finish_reason == "tool_calls":
            stop_reason = "tool_use"
        elif choice.finish_reason == "length":
            stop_reason = "max_tokens"

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=response.usage.prompt_tokens if response.usage else 0,
            output_tokens=response.usage.completion_tokens if response.usage else 0,
            model=response.model,
            stop_reason=stop_reason,
        )

    async def embed(self, text: str, model: str = "text-embedding-3-small") -> list[float]:
        """Generate an embedding using OpenAI."""
        last_error = None
        for attempt in range(3):
            try:
                response = await self.client.embeddings.create(
                    input=text,
                    model=model,
                )
                return response.data[0].embedding
            except Exception as e:
                last_error = e
                logger.warning("openai_embed_error", attempt=attempt, error=str(e))
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        raise last_error  # type: ignore[misc]
