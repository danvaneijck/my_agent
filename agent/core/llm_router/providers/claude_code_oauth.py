"""Claude Code CLI LLM provider with MCP tool bridge and streaming.

Uses the Claude Code CLI as the LLM backend, authenticated via OAuth.
Tools are exposed through an MCP server (``mcp_bridge.py``) so the CLI
handles tool calling natively with structured tool_use blocks.

Supports streaming via ``--output-format stream-json --verbose`` which
yields real-time events (tool calls, text chunks, results) that can be
forwarded to Discord/Slack for progressive updates.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile
from typing import AsyncGenerator

import structlog

from core.llm_router.providers.base import LLMProvider, LLMResponse, PromptTooLongError
from shared.oauth_refresh import refresh_and_persist, get_access_token
from shared.schemas.messages import StreamEvent
from shared.schemas.tools import ToolCall

logger = structlog.get_logger()

# Timeout for CLI subprocess — longer because CLI runs multi-step tool loops
_CLI_TIMEOUT = 300

# Default model alias for the CLI
_DEFAULT_CLI_MODEL = "opus"


class ClaudeCodeCLIProvider(LLMProvider):
    """LLM provider using Claude Code CLI with MCP-based tool calling."""

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

        # Set by the agent loop before each call so the MCP bridge
        # can save tool calls and inject platform context.
        self.conversation_id: str | None = None
        self.platform: str | None = None
        self.platform_channel_id: str | None = None
        self.platform_thread_id: str | None = None
        self.platform_server_id: str | None = None

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

    def _build_mcp_config(self) -> str:
        """Build the --mcp-config JSON for the MCP bridge server."""
        settings_env = {
            "CORE_URL": "http://localhost:8000",
            "MCP_USER_ID": self._user_id or "",
            "MCP_USER_PERMISSION": "owner",
            "MCP_CONVERSATION_ID": self.conversation_id or "",
            "MCP_PLATFORM": self.platform or "",
            "MCP_PLATFORM_CHANNEL_ID": self.platform_channel_id or "",
            "MCP_PLATFORM_THREAD_ID": self.platform_thread_id or "",
            "MCP_PLATFORM_SERVER_ID": self.platform_server_id or "",
        }
        service_token = os.environ.get("SERVICE_AUTH_TOKEN", "")
        if service_token:
            settings_env["SERVICE_AUTH_TOKEN"] = service_token

        config = {
            "mcpServers": {
                "agent-tools": {
                    "type": "stdio",
                    "command": "python",
                    "args": ["/app/core/mcp_bridge.py"],
                    "env": settings_env,
                }
            }
        }
        return json.dumps(config)

    def _build_cmd(
        self, prompt: str, cli_model: str, tools: list[dict] | None, streaming: bool
    ) -> list[str]:
        """Build the CLI command."""
        output_format = "stream-json" if streaming else "json"
        cmd = [
            "claude",
            "-p", prompt,
            "--output-format", output_format,
            "--model", cli_model,
            "--allowedTools", "mcp__agent-tools__*",
        ]
        if streaming:
            cmd.append("--verbose")
        if tools:
            cmd.extend(["--mcp-config", self._build_mcp_config()])
        return cmd

    def _prepare_env(self, tmp_dir: str) -> dict[str, str]:
        """Prepare a clean environment for the CLI subprocess."""
        env = os.environ.copy()
        env["HOME"] = tmp_dir
        env.pop("ANTHROPIC_API_KEY", None)
        return env

    def _write_credentials(self, tmp_dir: str) -> None:
        """Write OAuth credentials to a temp directory."""
        claude_dir = os.path.join(tmp_dir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        creds_file = os.path.join(claude_dir, ".credentials.json")
        with open(creds_file, "w") as f:
            f.write(self._credentials_json)
        os.chmod(creds_file, 0o600)

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

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "claude-opus-4-6",
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> AsyncGenerator[StreamEvent | LLMResponse, None]:
        """Run a streaming chat completion via the CLI.

        Yields ``StreamEvent`` objects as the CLI produces output, then
        yields the final ``LLMResponse`` as the last item.
        """
        await self._ensure_fresh_token()
        cli_model = _DEFAULT_CLI_MODEL
        prompt = self._serialize_context(messages)

        tmp_dir = tempfile.mkdtemp(prefix="claude_creds_")
        try:
            self._write_credentials(tmp_dir)
            env = self._prepare_env(tmp_dir)
            cmd = self._build_cmd(prompt, cli_model, tools, streaming=True)

            logger.info(
                "claude_cli_stream_call",
                user_id=self._user_id,
                model=cli_model,
                prompt_len=len(prompt),
                has_mcp=bool(tools),
            )

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                limit=10 * 1024 * 1024,
            )

            final_response: LLMResponse | None = None

            try:
                # Read stdout line-by-line for streaming events
                while True:
                    try:
                        line = await asyncio.wait_for(
                            proc.stdout.readline(), timeout=_CLI_TIMEOUT,
                        )
                    except asyncio.TimeoutError:
                        proc.kill()
                        await proc.wait()
                        raise RuntimeError(f"Claude CLI timed out after {_CLI_TIMEOUT}s")

                    if not line:
                        break  # EOF

                    line_str = line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        continue

                    try:
                        obj = json.loads(line_str)
                    except json.JSONDecodeError:
                        continue

                    msg_type = obj.get("type", "")

                    if msg_type == "system":
                        # Init event — MCP servers, tools loaded
                        mcp_servers = obj.get("mcp_servers", [])
                        tool_count = len(obj.get("tools", []))
                        yield StreamEvent(event="thinking", data={
                            "iteration": 1,
                            "mcp_servers": mcp_servers,
                            "built_in_tools": tool_count,
                        })

                    elif msg_type == "assistant":
                        # Assistant message — may contain text and/or tool_use blocks
                        message = obj.get("message", {})
                        content_blocks = message.get("content", [])
                        for block in content_blocks:
                            if block.get("type") == "text":
                                text = block.get("text", "")
                                if text:
                                    yield StreamEvent(event="content", data={
                                        "text": text,
                                    })
                            elif block.get("type") == "tool_use":
                                tool_name = block.get("name", "")
                                # Only stream MCP tool calls — skip built-in
                                # tools (Read, Glob, Bash, Edit, etc.) which
                                # are internal CLI operations.
                                if not tool_name.startswith("mcp__agent-tools__"):
                                    continue
                                tool_name = tool_name[len("mcp__agent-tools__"):]
                                display_name = tool_name.replace("_", ".", 1)
                                yield StreamEvent(event="tool_call", data={
                                    "tool": display_name,
                                    "arguments": block.get("input", {}),
                                })

                    elif msg_type == "tool_result":
                        # Tool execution result — only for MCP tools
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
                        # Final result
                        final_response = self._parse_result_obj(obj, cli_model)
                        logger.info(
                            "claude_cli_response",
                            user_id=self._user_id,
                            model=final_response.model,
                            input_tokens=final_response.input_tokens,
                            output_tokens=final_response.output_tokens,
                            stop_reason=final_response.stop_reason,
                        )

            except Exception:
                proc.kill()
                await proc.wait()
                raise

            await proc.wait()

            if proc.returncode != 0 and final_response is None:
                stderr = await proc.stderr.read()
                error_msg = stderr.decode("utf-8", errors="replace").strip()
                if "prompt is too long" in error_msg.lower():
                    raise PromptTooLongError(error_msg)
                raise RuntimeError(
                    f"Claude CLI exited with code {proc.returncode}: {error_msg[:200]}"
                )

            if final_response is None:
                final_response = LLMResponse(
                    content="No response received from CLI.",
                    model=cli_model,
                    stop_reason="end_turn",
                )

            yield final_response

        finally:
            import shutil
            try:
                shutil.rmtree(tmp_dir)
            except Exception:
                pass

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "claude-opus-4-6",
        max_tokens: int = 4000,
        temperature: float = 0.7,
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
        ):
            if isinstance(event, LLMResponse):
                final_response = event
        return final_response

    async def embed(self, text: str, model: str = "") -> list[float]:
        """Claude Code CLI does not support embeddings."""
        raise NotImplementedError(
            "Claude Code CLI does not provide an embedding API. Use OpenAI or Google."
        )
