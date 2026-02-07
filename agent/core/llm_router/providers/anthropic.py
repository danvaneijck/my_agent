"""Anthropic (Claude) LLM provider."""

from __future__ import annotations

import asyncio
import re

import structlog
from anthropic import AsyncAnthropic

from core.llm_router.providers.base import LLMProvider, LLMResponse
from shared.schemas.tools import ToolCall

logger = structlog.get_logger()


class AnthropicProvider(LLMProvider):
    """Provider for Anthropic Claude models."""

    def __init__(self, api_key: str):
        self.client = AsyncAnthropic(api_key=api_key)

    def _convert_tools(
        self, tools: list[dict] | None
    ) -> tuple[list[dict] | None, dict[str, str]]:
        """
        Convert OpenAI-style tool definitions to Anthropic format.

        Returns:
            Tuple containing:
            1. List of Anthropic tool definitions
            2. Dictionary mapping sanitized_names -> original_names
        """
        if not tools:
            return None, {}

        anthropic_tools = []
        name_mapping = {}

        for tool in tools:
            func = tool.get("function", tool)

            original_name = func["name"]
            # Anthropic enforces ^[a-zA-Z0-9_-]{1,128}$.
            # Replace any character that is NOT alphanumeric/underscore/hyphen with an underscore.
            sanitized_name = re.sub(r"[^a-zA-Z0-9_-]", "_", original_name)
            # Ensure it doesn't exceed 64 chars (safe limit, though error allows 128)
            sanitized_name = sanitized_name[:64]

            # Store mapping to restore original name in response
            name_mapping[sanitized_name] = original_name

            properties = {}
            required = []
            for param in func.get("parameters", {}).get("properties", {}):
                prop = func["parameters"]["properties"][param]
                properties[param] = {
                    "type": prop.get("type", "string"),
                    "description": prop.get("description", ""),
                }
                if prop.get("enum"):
                    properties[param]["enum"] = prop["enum"]
            if "required" in func.get("parameters", {}):
                required = func["parameters"]["required"]

            anthropic_tools.append(
                {
                    "name": sanitized_name,
                    "description": func.get("description", ""),
                    "input_schema": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                }
            )
        return anthropic_tools, name_mapping

    def _convert_messages(self, messages: list[dict]) -> tuple[str | None, list[dict]]:
        """Extract system message and convert to Anthropic format."""
        system = None
        converted = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            elif msg["role"] == "tool_call":
                # Convert to assistant message with tool_use block
                # Ensure name is sanitized here as well if needed, though strictly
                # we should match what the model effectively 'outputted' previously.
                tool_name = msg.get("name", "")
                sanitized_name = re.sub(r"[^a-zA-Z0-9_-]", "_", tool_name)[:64]

                converted.append(
                    {
                        "role": "assistant",
                        "content": [
                            {
                                "type": "tool_use",
                                "id": msg.get("tool_use_id", "tool_" + sanitized_name),
                                "name": sanitized_name,
                                "input": msg.get("arguments", {}),
                            }
                        ],
                    }
                )
            elif msg["role"] == "tool_result":
                converted.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": msg.get("tool_use_id", ""),
                                "content": str(msg.get("content", "")),
                            }
                        ],
                    }
                )
            else:
                role = "assistant" if msg["role"] == "assistant" else "user"
                converted.append(
                    {
                        "role": role,
                        "content": msg["content"],
                    }
                )
        return system, converted

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat completion to Anthropic."""
        system, converted_messages = self._convert_messages(messages)
        # Get tools AND the name mapping
        anthropic_tools, tool_name_mapping = self._convert_tools(tools)

        kwargs: dict = {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": converted_messages,
        }
        if system:
            kwargs["system"] = system
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        last_error = None
        for attempt in range(3):
            try:
                response = await self.client.messages.create(**kwargs)
                break
            except Exception as e:
                last_error = e
                logger.warning("anthropic_api_error", attempt=attempt, error=str(e))
                if attempt < 2:
                    await asyncio.sleep(2**attempt)
        else:
            raise last_error  # type: ignore[misc]

        # Parse response
        content = None
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content = block.text
            elif block.type == "tool_use":
                # Convert the sanitized name back to the original name
                # so the router knows which function to execute
                original_name = tool_name_mapping.get(block.name, block.name)

                tool_calls.append(
                    ToolCall(
                        tool_name=original_name,
                        arguments=block.input,
                    )
                )

        stop_reason = "end_turn"
        if response.stop_reason == "tool_use":
            stop_reason = "tool_use"
        elif response.stop_reason == "max_tokens":
            stop_reason = "max_tokens"

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
            stop_reason=stop_reason,
        )

    async def embed(self, text: str, model: str = "") -> list[float]:
        """Anthropic does not natively support embeddings. Raise an error."""
        raise NotImplementedError(
            "Anthropic does not provide an embedding API. Use OpenAI or Google."
        )
