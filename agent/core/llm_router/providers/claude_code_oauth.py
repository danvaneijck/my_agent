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

    def _parse_cli_output(self, stdout: str) -> LLMResponse:
        """Parse the CLI JSON output into an LLMResponse."""
        # CLI with --output-format json returns newline-delimited JSON objects
        json_objects = []
        for line in stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                json_objects.append(json.loads(line))
            except json.JSONDecodeError:
                continue

        content = None
        tool_calls: list[ToolCall] = []
        input_tokens = 0
        output_tokens = 0
        model = ""
        stop_reason = "end_turn"

        for obj in json_objects:
            obj_type = obj.get("type", "")

            if obj_type == "assistant":
                msg = obj.get("message", {})
                # Extract usage
                usage = msg.get("usage", {})
                input_tokens += usage.get("input_tokens", 0)
                output_tokens += usage.get("output_tokens", 0)
                model = msg.get("model", model)

                # Extract stop reason
                sr = msg.get("stop_reason", "")
                if sr:
                    stop_reason = sr

            elif obj_type == "content_block_start":
                block = obj.get("content_block", {})
                if block.get("type") == "text":
                    content = block.get("text", "")
                elif block.get("type") == "tool_use":
                    # Will be populated by content_block_delta
                    pass

            elif obj_type == "content_block_delta":
                delta = obj.get("delta", {})
                if delta.get("type") == "text_delta":
                    if content is None:
                        content = ""
                    content += delta.get("text", "")

            elif obj_type == "result":
                # Final result object from CLI
                result_text = obj.get("result", "")
                if result_text and content is None:
                    content = result_text
                # Check for tool use in the result
                sub = obj.get("subtype", "")
                if sub == "tool_use":
                    stop_reason = "tool_use"

            elif obj_type == "message":
                # Some CLI versions output a message object
                msg_content = obj.get("content", [])
                if isinstance(msg_content, list):
                    for block in msg_content:
                        if block.get("type") == "text":
                            content = block.get("text", content)
                        elif block.get("type") == "tool_use":
                            tool_calls.append(ToolCall(
                                tool_name=block.get("name", ""),
                                arguments=block.get("input", {}),
                            ))
                            stop_reason = "tool_use"

        # If no structured output, use raw stdout as content
        if content is None and not tool_calls:
            content = stdout.strip() if stdout.strip() else None

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=model,
            stop_reason=stop_reason,
        )

    async def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4000,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """Run a chat completion via the Claude Code CLI."""
        await self._ensure_fresh_token()

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
                "--model", model,
            ]

            logger.info(
                "claude_cli_call",
                user_id=self._user_id,
                model=model,
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

            response = self._parse_cli_output(stdout)
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
