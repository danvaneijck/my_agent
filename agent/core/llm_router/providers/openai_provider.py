"""OpenAI LLM provider."""

from __future__ import annotations

import asyncio
import json
import re

import structlog
from openai import AsyncOpenAI, BadRequestError

from core.llm_router.providers.base import LLMProvider, LLMResponse
from shared.schemas.tools import ToolCall

logger = structlog.get_logger()


class OpenAIProvider(LLMProvider):
    """Provider for OpenAI models (GPT-4o, etc.)."""

    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)

    def _sanitize_name(self, name: str) -> str:
        """
        Sanitize tool name to match OpenAI pattern '^[a-zA-Z0-9_-]+$'.
        Truncate to 64 chars to be safe.
        """
        return re.sub(r"[^a-zA-Z0-9_-]", "_", name)[:64]

    def _convert_tools(
        self, tools: list[dict] | None
    ) -> tuple[list[dict] | None, dict[str, str]]:
        """
        Ensure tools are in OpenAI function calling format and sanitize names.

        Returns:
            Tuple containing:
            1. List of OpenAI tool definitions
            2. Dictionary mapping sanitized_names -> original_names
        """
        if not tools:
            return None, {}

        openai_tools = []
        name_mapping = {}

        for tool in tools:
            # Determine original name based on input format
            if "function" in tool:
                original_name = tool["function"]["name"]
            else:
                original_name = tool["name"]

            # Sanitize
            sanitized_name = self._sanitize_name(original_name)
            name_mapping[sanitized_name] = original_name

            if "function" in tool:
                # It's already in (or close to) OpenAI format
                # We need to copy and modify the name to be safe
                import copy

                new_tool = copy.deepcopy(tool)
                new_tool["function"]["name"] = sanitized_name
                openai_tools.append(new_tool)
            else:
                # Convert from internal format
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

                openai_tools.append(
                    {
                        "type": "function",
                        "function": {
                            "name": sanitized_name,
                            "description": tool.get("description", ""),
                            "parameters": {
                                "type": "object",
                                "properties": properties,
                                "required": required,
                            },
                        },
                    }
                )
        return openai_tools, name_mapping

    def _convert_messages(self, messages: list[dict]) -> list[dict]:
        """Convert messages to OpenAI format, sanitizing tool calls in history."""
        converted = []
        for msg in messages:
            if msg["role"] == "tool_call":
                # Sanitize the name for the history to match the schema requirements
                tool_name = msg.get("name", "")
                sanitized_name = self._sanitize_name(tool_name)

                # We also assume the ID might need to be clean if we generated it via fallback
                tool_id = msg.get("tool_use_id", "call_" + sanitized_name)

                converted.append(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": tool_id,
                                "type": "function",
                                "function": {
                                    "name": sanitized_name,
                                    "arguments": json.dumps(msg.get("arguments", {})),
                                },
                            }
                        ],
                    }
                )
            elif msg["role"] == "tool_result":
                converted.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.get("tool_use_id", ""),
                        "content": str(msg.get("content", "")),
                    }
                )
            else:
                converted.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                    }
                )
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
        openai_tools, tool_name_mapping = self._convert_tools(tools)

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
            except BadRequestError:
                raise  # 400 = bad payload, retrying won't help
            except Exception as e:
                last_error = e
                logger.warning("openai_api_error", attempt=attempt, error=str(e))
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
        else:
            raise last_error  # type: ignore[misc]

        choice = response.choices[0]
        content = choice.message.content
        tool_calls = []

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                # Map the sanitized name back to the original name
                # so the system knows which internal function to call
                sanitized_name = tc.function.name
                original_name = tool_name_mapping.get(sanitized_name, sanitized_name)

                tool_calls.append(
                    ToolCall(
                        tool_name=original_name,
                        arguments=json.loads(tc.function.arguments),
                    )
                )

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

    async def embed(
        self, text: str, model: str = "text-embedding-3-small"
    ) -> list[float]:
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
                    await asyncio.sleep(2**attempt)
        raise last_error  # type: ignore[misc]
