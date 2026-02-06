"""Google (Gemini) LLM provider."""

from __future__ import annotations

import asyncio

import structlog
from google import genai
from google.genai import types

from core.llm_router.providers.base import LLMProvider, LLMResponse
from shared.schemas.tools import ToolCall

logger = structlog.get_logger()


class GoogleProvider(LLMProvider):
    """Provider for Google Gemini models."""

    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def _convert_tools(self, tools: list[dict] | None) -> list[types.Tool] | None:
        """Convert to Google's tool format."""
        if not tools:
            return None
        declarations = []
        for tool in tools:
            func = tool.get("function", tool)
            properties = {}
            required = []
            for param_name, param_def in func.get("parameters", {}).get("properties", {}).items():
                type_map = {
                    "string": "STRING",
                    "integer": "INTEGER",
                    "number": "NUMBER",
                    "boolean": "BOOLEAN",
                    "array": "ARRAY",
                    "object": "OBJECT",
                }
                schema_type = type_map.get(param_def.get("type", "string"), "STRING")
                properties[param_name] = types.Schema(
                    type=schema_type,
                    description=param_def.get("description", ""),
                )
            if "required" in func.get("parameters", {}):
                required = func["parameters"]["required"]

            declarations.append(types.FunctionDeclaration(
                name=func["name"],
                description=func.get("description", ""),
                parameters=types.Schema(
                    type="OBJECT",
                    properties=properties,
                    required=required,
                ),
            ))
        return [types.Tool(function_declarations=declarations)]

    def _convert_messages(self, messages: list[dict]) -> tuple[str | None, list[types.Content]]:
        """Convert messages to Google format."""
        system = None
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                system = msg["content"]
            elif msg["role"] == "tool_call":
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part(function_call=types.FunctionCall(
                        name=msg.get("name", ""),
                        args=msg.get("arguments", {}),
                    ))],
                ))
            elif msg["role"] == "tool_result":
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(function_response=types.FunctionResponse(
                        name=msg.get("name", ""),
                        response={"result": msg.get("content", "")},
                    ))],
                ))
            elif msg["role"] == "assistant":
                contents.append(types.Content(
                    role="model",
                    parts=[types.Part(text=msg["content"])],
                ))
            else:
                contents.append(types.Content(
                    role="user",
                    parts=[types.Part(text=msg["content"])],
                ))
        return system, contents

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "gemini-2.0-flash",
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Send a chat completion to Google Gemini."""
        system, contents = self._convert_messages(messages)
        google_tools = self._convert_tools(tools)

        config = types.GenerateContentConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        )
        if system:
            config.system_instruction = system
        if google_tools:
            config.tools = google_tools

        last_error = None
        for attempt in range(3):
            try:
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=model,
                    contents=contents,
                    config=config,
                )
                break
            except Exception as e:
                last_error = e
                logger.warning("google_api_error", attempt=attempt, error=str(e))
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        else:
            raise last_error  # type: ignore[misc]

        content = None
        tool_calls = []

        if response.candidates:
            candidate = response.candidates[0]
            for part in candidate.content.parts:
                if part.text:
                    content = (content or "") + part.text
                if part.function_call:
                    tool_calls.append(ToolCall(
                        tool_name=part.function_call.name,
                        arguments=dict(part.function_call.args) if part.function_call.args else {},
                    ))

        stop_reason = "end_turn"
        if tool_calls:
            stop_reason = "tool_use"

        input_tokens = 0
        output_tokens = 0
        if response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            stop_reason=stop_reason,
        )

    async def embed(self, text: str, model: str = "text-embedding-004") -> list[float]:
        """Generate embeddings using Google."""
        last_error = None
        for attempt in range(3):
            try:
                response = await asyncio.to_thread(
                    self.client.models.embed_content,
                    model=model,
                    content=text,
                )
                return response.embedding.values
            except Exception as e:
                last_error = e
                logger.warning("google_embed_error", attempt=attempt, error=str(e))
                if attempt < 2:
                    await asyncio.sleep(2 ** attempt)
        raise last_error  # type: ignore[misc]
