"""Claude Code CLI LLM provider with MCP tool bridge.

Uses the Claude Code CLI as the LLM backend, authenticated via OAuth.
Tools are exposed through an MCP server (``mcp_bridge.py``) so the CLI
handles tool calling natively with structured tool_use blocks — no
text-based JSON parsing needed.

The CLI runs the full tool calling loop internally (reason → call tool
via MCP → observe result → repeat).  We get only the final text response.
"""

from __future__ import annotations

import asyncio
import json
import os
import tempfile

import structlog

from core.llm_router.providers.base import LLMProvider, LLMResponse, PromptTooLongError
from shared.oauth_refresh import refresh_and_persist, get_access_token
from shared.schemas.tools import ToolCall

logger = structlog.get_logger()

# Timeout for CLI subprocess (seconds) — longer now because CLI runs
# its own multi-step tool calling loop internally
_CLI_TIMEOUT = 300

# Default model alias for the CLI
_DEFAULT_CLI_MODEL = "opus"


class ClaudeCodeCLIProvider(LLMProvider):
    """LLM provider using Claude Code CLI with MCP-based tool calling.

    The CLI spawns an MCP bridge server that proxies tool calls to the
    agent's module services.  This gives native structured tool calling
    without text-based JSON parsing.
    """

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

        Tools are NOT included here — they come via the MCP bridge.
        Only conversation messages are serialized.
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
                    f"<tool_call>\n"
                    f"Tool: {name}\n"
                    f"Arguments: {json.dumps(args, indent=2)}\n"
                    f"</tool_call>"
                )
            elif role == "tool_result":
                name = msg.get("name", "")
                result = msg.get("content", "")
                parts.append(
                    f"<tool_result>\n"
                    f"Tool: {name}\n"
                    f"Result: {result}\n"
                    f"</tool_result>"
                )

        return "\n\n".join(parts)

    def _build_mcp_config(self) -> str:
        """Build the --mcp-config JSON for the MCP bridge server."""
        # The bridge runs inside the same container, calling core's HTTP API
        settings_env = {
            "CORE_URL": "http://localhost:8000",
            "MCP_USER_ID": self._user_id or "",
            "MCP_USER_PERMISSION": "owner",
        }

        # Pass service auth token if set
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

    def _parse_cli_output(self, stdout: str, requested_model: str) -> LLMResponse:
        """Parse the CLI JSON output into an LLMResponse.

        With MCP tool calling, the CLI handles the entire tool loop
        internally.  The response is always the final text — no tool
        calls to extract.
        """
        try:
            obj = json.loads(stdout.strip())
        except json.JSONDecodeError:
            obj = None
            for line in stdout.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                try:
                    parsed = json.loads(line)
                    if isinstance(parsed, dict) and parsed.get("type") == "result":
                        obj = parsed
                        break
                except json.JSONDecodeError:
                    continue

        if not obj:
            return LLMResponse(
                content=stdout.strip() or None,
                model=requested_model,
                stop_reason="end_turn",
            )

        content = obj.get("result", "")
        usage = obj.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cache_creation = usage.get("cache_creation_input_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)

        model_usage = obj.get("modelUsage", {})
        model = next(iter(model_usage), "") if model_usage else ""
        stop_reason = obj.get("stop_reason", "end_turn") or "end_turn"

        return LLMResponse(
            content=content or None,
            tool_calls=[],  # CLI handles tools internally via MCP
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_creation,
            cache_read_input_tokens=cache_read,
            model=model or requested_model,
            stop_reason="end_turn",  # Always end_turn — CLI completed the loop
        )

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "claude-opus-4-6",
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Run a chat completion via the Claude Code CLI with MCP tools."""
        await self._ensure_fresh_token()

        cli_model = _DEFAULT_CLI_MODEL
        # Don't pass tools to serialization — MCP bridge provides them
        prompt = self._serialize_context(messages)

        tmp_dir = tempfile.mkdtemp(prefix="claude_creds_")
        claude_dir = os.path.join(tmp_dir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        creds_file = os.path.join(claude_dir, ".credentials.json")

        try:
            with open(creds_file, "w") as f:
                f.write(self._credentials_json)
            os.chmod(creds_file, 0o600)

            env = os.environ.copy()
            env["HOME"] = tmp_dir
            env.pop("ANTHROPIC_API_KEY", None)

            cmd = [
                "claude",
                "-p", prompt,
                "--output-format", "json",
                "--model", cli_model,
                # Disable built-in tools (Bash, Edit, etc.) — we only want MCP tools
                "--tools", "",
                # Auto-approve all MCP tools from our agent-tools server
                "--allowedTools", "mcp__agent-tools__*",
            ]

            # Add MCP config if tools are available
            if tools:
                mcp_config = self._build_mcp_config()
                cmd.extend(["--mcp-config", mcp_config])

            logger.info(
                "claude_cli_call",
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

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=_CLI_TIMEOUT,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise RuntimeError(f"Claude CLI timed out after {_CLI_TIMEOUT}s")

            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                error_msg = stderr.strip() or stdout.strip()
                if "prompt is too long" in error_msg.lower():
                    raise PromptTooLongError(error_msg)
                logger.error(
                    "claude_cli_error",
                    returncode=proc.returncode,
                    stderr=error_msg[:500],
                    user_id=self._user_id,
                )
                raise RuntimeError(
                    f"Claude CLI exited with code {proc.returncode}: {error_msg[:200]}"
                )

            response = self._parse_cli_output(stdout, cli_model)
            logger.info(
                "claude_cli_response",
                user_id=self._user_id,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                stop_reason=response.stop_reason,
            )
            return response

        finally:
            import shutil
            try:
                shutil.rmtree(tmp_dir)
            except Exception:
                pass

    async def embed(self, text: str, model: str = "") -> list[float]:
        """Claude Code CLI does not support embeddings."""
        raise NotImplementedError(
            "Claude Code CLI does not provide an embedding API. Use OpenAI or Google."
        )
