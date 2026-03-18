"""Claude Code CLI LLM provider.

Uses the Claude Code CLI (``claude -p``) as the LLM backend, authenticated
via a user's Claude Code subscription OAuth credentials.  This allows users
with a Max plan to use the agent without a separate API key.

The CLI is installed in the core container and invoked as a subprocess.
Credentials are written to a temp directory per-call and cleaned up after.
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

# Timeout for CLI subprocess (seconds)
_CLI_TIMEOUT = 120

# Default model for CLI provider — use alias for best compatibility
_DEFAULT_CLI_MODEL = "opus"


class ClaudeCodeCLIProvider(LLMProvider):
    """LLM provider that uses the Claude Code CLI subprocess.

    Instead of calling the Anthropic API directly, this provider:
    1. Writes OAuth credentials to a temp ``~/.claude/.credentials.json``
    2. Serializes the conversation context into a single prompt
    3. Runs ``claude -p "<prompt>" --output-format json``
    4. Parses the JSON output into a standard ``LLMResponse``
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

        logger.info(
            "claude_code_cli_provider_initialized",
            user_id=user_id,
        )

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

    def _serialize_context(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        max_tokens: int,
    ) -> str:
        """Serialize conversation context into a single prompt for the CLI.

        The CLI processes a single prompt string.  We flatten the structured
        messages (system, user, assistant, tool_call, tool_result) into a
        readable prompt that preserves the conversation flow.
        """
        parts: list[str] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                parts.append(f"<system>\n{content}\n</system>")
            elif role == "user":
                if isinstance(content, list):
                    # Vision content blocks — extract text only for CLI
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

        # Append tool definitions if present
        if tools:
            tool_section = "\n<available_tools>\n"
            for tool in tools:
                func = tool.get("function", tool)
                name = func.get("name", "")
                desc = func.get("description", "")
                params = func.get("parameters", {})
                tool_section += (
                    f"- {name}: {desc}\n"
                    f"  Parameters: {json.dumps(params)}\n"
                )
            tool_section += (
                "\nTo use a tool, respond with a JSON object like:\n"
                '{"tool_calls": [{"name": "tool_name", "arguments": {...}}]}\n'
                "If you don't need a tool, respond normally with text.\n"
                "</available_tools>\n"
            )
            parts.append(tool_section)

        return "\n\n".join(parts)

    def _parse_cli_output(self, stdout: str, requested_model: str) -> LLMResponse:
        """Parse the CLI JSON output into an LLMResponse.

        The CLI with ``--output-format json`` returns a single JSON object
        with ``type: "result"`` containing the response text, usage, model
        info, and cost.

        Example output::

            {
              "type": "result",
              "subtype": "success",
              "result": "Hello! How can I help you?",
              "stop_reason": "end_turn",
              "usage": {"input_tokens": 3, "output_tokens": 12, ...},
              "modelUsage": {"claude-sonnet-4-6": {"inputTokens": 3, ...}},
              ...
            }
        """
        try:
            obj = json.loads(stdout.strip())
        except json.JSONDecodeError:
            # Try to find a JSON object in the output (might have extra lines)
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

        # Extract response text
        content = obj.get("result", "")

        # Extract usage
        usage = obj.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cache_creation = usage.get("cache_creation_input_tokens", 0)
        cache_read = usage.get("cache_read_input_tokens", 0)

        # Extract model name from modelUsage keys
        model_usage = obj.get("modelUsage", {})
        model = next(iter(model_usage), "") if model_usage else ""

        # Extract stop reason
        stop_reason = obj.get("stop_reason", "end_turn") or "end_turn"

        return LLMResponse(
            content=content or None,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_creation_input_tokens=cache_creation,
            cache_read_input_tokens=cache_read,
            model=model or requested_model,
            stop_reason=stop_reason,
        )

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "claude-opus-4-6",
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Run a chat completion via the Claude Code CLI."""
        await self._ensure_fresh_token()

        # Always use the CLI default model (Opus) — the CLI uses short aliases
        cli_model = _DEFAULT_CLI_MODEL
        prompt = self._serialize_context(messages, tools, max_tokens)

        # Write credentials to a temp directory
        tmp_dir = tempfile.mkdtemp(prefix="claude_creds_")
        claude_dir = os.path.join(tmp_dir, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        creds_file = os.path.join(claude_dir, ".credentials.json")

        try:
            with open(creds_file, "w") as f:
                f.write(self._credentials_json)
            os.chmod(creds_file, 0o600)

            # Build CLI command
            env = os.environ.copy()
            env["HOME"] = tmp_dir
            # Prevent CLI from picking up ANTHROPIC_API_KEY
            env.pop("ANTHROPIC_API_KEY", None)

            cmd = [
                "claude",
                "-p", prompt,
                "--output-format", "json",
                "--model", cli_model,
            ]

            logger.info(
                "claude_cli_call",
                user_id=self._user_id,
                model=cli_model,
                prompt_len=len(prompt),
            )

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                limit=10 * 1024 * 1024,  # 10 MB buffer
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(), timeout=_CLI_TIMEOUT,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                raise RuntimeError(
                    f"Claude CLI timed out after {_CLI_TIMEOUT}s"
                )

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
                raise RuntimeError(f"Claude CLI exited with code {proc.returncode}: {error_msg[:200]}")

            response = self._parse_cli_output(stdout, cli_model)
            logger.info(
                "claude_cli_response",
                user_id=self._user_id,
                model=response.model,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                stop_reason=response.stop_reason,
                has_tool_calls=len(response.tool_calls) > 0,
            )
            return response

        finally:
            # Clean up temp credentials
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
