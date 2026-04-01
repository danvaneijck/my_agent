"""Claude Code CLI LLM provider — containerized execution via claude-code module.

Delegates Claude CLI execution to the claude-code module's ``/chat/stream``
endpoint, which runs each session in an isolated Docker container.  OAuth
credentials are sent over the internal network and never touch the core
container's filesystem.

Tools are exposed through an MCP bridge inside the worker container that
calls back to core's ``/execute`` endpoint with proper user permissions.
"""

from __future__ import annotations

import json
import os
from typing import AsyncGenerator

import httpx
import structlog

from core.llm_router.providers.base import LLMProvider, LLMResponse, PromptTooLongError
from shared.oauth_refresh import refresh_and_persist, get_access_token
from shared.schemas.messages import StreamEvent

logger = structlog.get_logger()

# Timeout for the HTTP streaming connection — matches container-level timeout
_STREAM_TIMEOUT = 360  # slightly longer than container's 300s to catch timeout errors

# Default model alias for the CLI
_DEFAULT_CLI_MODEL = "opus"


class ClaudeCodeCLIProvider(LLMProvider):
    """LLM provider that runs Claude CLI in isolated Docker containers.

    Instead of running the CLI as a subprocess in the core container
    (which leaks env vars and shares the filesystem), this provider
    delegates to the claude-code module's ``/chat/stream`` endpoint.
    Each user's session runs in its own ephemeral container with:

    - No access to host secrets (DATABASE_URL, REDIS_PASSWORD, etc.)
    - No access to other users' data
    - Permission-gated tool access via MCP bridge
    - Automatic cleanup after completion
    """

    def __init__(
        self,
        credentials_json: str,
        credential_store=None,
        user_id: str | None = None,
        session_factory=None,
        user_permission: str = "guest",
        claude_code_url: str = "http://claude-code:8000",
    ) -> None:
        self._credentials_json = credentials_json
        self._credential_store = credential_store
        self._user_id = user_id
        self._session_factory = session_factory
        self._user_permission = user_permission
        self._claude_code_url = claude_code_url

        # Set by the agent loop before each call so the MCP bridge
        # can save tool calls and inject platform context.
        self.conversation_id: str | None = None
        self.platform: str | None = None
        self.platform_channel_id: str | None = None
        self.platform_thread_id: str | None = None
        self.platform_server_id: str | None = None
        self.allowed_modules: list[str] | None = None

        if not get_access_token(credentials_json):
            raise ValueError("No OAuth access token found in credentials_json")

        logger.info("claude_code_cli_provider_initialized", user_id=user_id)

    async def _ensure_fresh_token(self) -> None:
        """Refresh the OAuth token if expiring soon."""
        updated_json = await refresh_and_persist(
            self._credentials_json,
            user_id=self._user_id or "",
            threshold_ms=5 * 60 * 1000,
            credential_store=self._credential_store,
            session_factory=self._session_factory,
        )
        if updated_json != self._credentials_json:
            self._credentials_json = updated_json
            logger.info("claude_code_cli_token_refreshed", user_id=self._user_id)

    def _serialize_context(self, messages: list[dict]) -> str:
        """Serialize conversation context into a prompt for the CLI.

        Tools are NOT included — they come via the MCP bridge.
        """
        parts: list[str] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                parts.append(f"<system>\n{content}\n</system>")
            elif role == "user":
                if isinstance(content, list):
                    text_parts = [
                        b.get("text", "") for b in content
                        if b.get("type") == "text"
                    ]
                    parts.append(f"<user>\n{' '.join(text_parts)}\n</user>")
                else:
                    parts.append(f"<user>\n{content}\n</user>")
            elif role == "assistant":
                parts.append(f"<assistant>\n{content}\n</assistant>")
            elif role == "tool_call":
                name = msg.get("name", "")
                args = msg.get("arguments", {})
                parts.append(
                    f"<tool_call>\nTool: {name}\n"
                    f"Arguments: {json.dumps(args, indent=2)}\n</tool_call>"
                )
            elif role == "tool_result":
                name = msg.get("name", "")
                result = msg.get("content", "")
                parts.append(
                    f"<tool_result>\nTool: {name}\nResult: {result}\n</tool_result>"
                )

        return "\n\n".join(parts)

    @staticmethod
    def _parse_result_obj(obj: dict, requested_model: str) -> LLMResponse:
        """Parse a stream-json result object into LLMResponse."""
        content = obj.get("result", "")
        usage = obj.get("usage", {})
        model_usage = obj.get("modelUsage", {})
        model = next(iter(model_usage), "") if model_usage else ""

        return LLMResponse(
            content=content or None,
            tool_calls=[],
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            cache_creation_input_tokens=usage.get("cache_creation_input_tokens", 0),
            cache_read_input_tokens=usage.get("cache_read_input_tokens", 0),
            model=model or requested_model,
            stop_reason="end_turn",
        )

    def _get_auth_headers(self) -> dict[str, str]:
        """Build service auth headers for internal HTTP calls."""
        token = os.environ.get("SERVICE_AUTH_TOKEN", "")
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "claude-opus-4-6",
        max_tokens: int = 4000,
        temperature: float = 0.7,
        max_turns: int | None = None,
    ) -> AsyncGenerator[StreamEvent | LLMResponse, None]:
        """Run a streaming chat completion via containerized CLI.

        Sends the request to the claude-code module's ``/chat/stream``
        endpoint, which runs the CLI in an isolated Docker container.
        Yields ``StreamEvent`` objects as the CLI produces output, then
        yields the final ``LLMResponse`` as the last item.
        """
        await self._ensure_fresh_token()
        cli_model = _DEFAULT_CLI_MODEL
        prompt = self._serialize_context(messages)

        # Build request for the claude-code module
        payload = {
            "prompt": prompt,
            "credentials_json": self._credentials_json,
            "user_id": self._user_id or "",
            "user_permission": self._user_permission,
            "model": cli_model,
            "max_turns": max_turns or 10,
            "tools": tools,
            "conversation_id": self.conversation_id,
            "platform": self.platform,
            "platform_channel_id": self.platform_channel_id,
            "platform_thread_id": self.platform_thread_id,
            "platform_server_id": self.platform_server_id,
            "allowed_modules": self.allowed_modules,
        }

        logger.info(
            "claude_cli_stream_call",
            user_id=self._user_id,
            model=cli_model,
            prompt_len=len(prompt),
            has_tools=bool(tools),
            containerized=True,
        )

        url = f"{self._claude_code_url}/chat/stream"
        final_response: LLMResponse | None = None
        # Accumulate text from assistant content blocks — the final "result"
        # event may have an empty result field when the CLI did tool calls.
        accumulated_text: list[str] = []

        async with httpx.AsyncClient(timeout=httpx.Timeout(_STREAM_TIMEOUT, connect=30.0)) as client:
            async with client.stream(
                "POST", url,
                json=payload,
                headers=self._get_auth_headers(),
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    raise RuntimeError(
                        f"claude-code /chat/stream returned {resp.status_code}: "
                        f"{body.decode('utf-8', errors='replace')[:500]}"
                    )

                async for line in resp.aiter_lines():
                    line = line.strip()
                    if not line:
                        continue

                    # Parse SSE data lines
                    if line.startswith("data: "):
                        line = line[6:]

                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    msg_type = obj.get("type", "")

                    # Handle error events from the container
                    if msg_type == "error":
                        error = obj.get("error", "")
                        message = obj.get("message", "")
                        if error == "prompt_too_long":
                            raise PromptTooLongError(message)
                        raise RuntimeError(f"Container error: {message or error}")

                    if msg_type == "system":
                        mcp_servers = obj.get("mcp_servers", [])
                        tool_count = len(obj.get("tools", []))
                        yield StreamEvent(event="thinking", data={
                            "iteration": 1,
                            "mcp_servers": mcp_servers,
                            "built_in_tools": tool_count,
                        })

                    elif msg_type == "assistant":
                        message = obj.get("message", {})
                        content_blocks = message.get("content", [])
                        for block in content_blocks:
                            if block.get("type") == "text":
                                text = block.get("text", "")
                                if text:
                                    accumulated_text.append(text)
                                    yield StreamEvent(event="content", data={
                                        "text": text,
                                    })
                            elif block.get("type") == "tool_use":
                                tool_name = block.get("name", "")
                                if not tool_name.startswith("mcp__agent-tools__"):
                                    continue
                                tool_name = tool_name[len("mcp__agent-tools__"):]
                                display_name = tool_name.replace("_", ".", 1)
                                yield StreamEvent(event="tool_call", data={
                                    "tool": display_name,
                                    "arguments": block.get("input", {}),
                                })

                    elif msg_type == "tool_result":
                        tool_name = obj.get("tool_name", "")
                        if not tool_name.startswith("mcp__agent-tools__"):
                            continue
                        tool_name = tool_name[len("mcp__agent-tools__"):]
                        display_name = tool_name.replace("_", ".", 1)
                        is_error = obj.get("is_error", False)
                        yield StreamEvent(event="tool_result", data={
                            "tool": display_name,
                            "success": not is_error,
                        })

                    elif msg_type == "result":
                        final_response = self._parse_result_obj(obj, cli_model)
                        logger.info(
                            "claude_cli_response",
                            user_id=self._user_id,
                            model=final_response.model,
                            input_tokens=final_response.input_tokens,
                            output_tokens=final_response.output_tokens,
                            stop_reason=final_response.stop_reason,
                        )

        if final_response is None:
            final_response = LLMResponse(
                content="No response received from CLI.",
                model=cli_model,
                stop_reason="end_turn",
            )

        # If the result field was empty but we accumulated text from
        # assistant content blocks during streaming, use that instead.
        if not final_response.content and accumulated_text:
            final_response = LLMResponse(
                content="\n\n".join(accumulated_text),
                tool_calls=final_response.tool_calls,
                input_tokens=final_response.input_tokens,
                output_tokens=final_response.output_tokens,
                cache_creation_input_tokens=final_response.cache_creation_input_tokens,
                cache_read_input_tokens=final_response.cache_read_input_tokens,
                model=final_response.model,
                stop_reason=final_response.stop_reason,
            )

        yield final_response

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "claude-opus-4-6",
        max_tokens: int = 4000,
        temperature: float = 0.7,
        max_turns: int | None = None,
    ) -> LLMResponse:
        """Non-streaming chat — wraps chat_stream and returns final response."""
        final_response = LLMResponse(
            content="No response received.",
            model=_DEFAULT_CLI_MODEL,
            stop_reason="end_turn",
        )
        async for event in self.chat_stream(
            messages=messages,
            tools=tools,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            max_turns=max_turns,
        ):
            if isinstance(event, LLMResponse):
                final_response = event
        return final_response

    async def embed(self, text: str, model: str = "") -> list[float]:
        """Claude Code CLI does not support embeddings."""
        raise NotImplementedError(
            "Claude Code CLI does not provide an embedding API. Use OpenAI or Google."
        )
