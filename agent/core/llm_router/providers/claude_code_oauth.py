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
import re
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

        # Lead with the tool calling protocol so the model sees it FIRST,
        # before the 100K+ tokens of context and tool definitions.
        if tools:
            parts.append(
                "<system>\n"
                "YOU ARE AN AGENT WITH TOOL CALLING CAPABILITY.\n"
                "When you need to perform an action, output ONLY this JSON:\n"
                '{"tool_calls": [{"name": "tool_name", "arguments": {...}}]}\n'
                "RULES:\n"
                "- Output the JSON tool call, nothing else. No narration before or after.\n"
                "- NEVER write fake tool calls/results in your text. NEVER role-play calling tools.\n"
                "- NEVER describe what you would do — DO IT by outputting the JSON.\n"
                "- Only write plain text when you have completed ALL actions.\n"
                "</system>"
            )

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

        # If the conversation has tool results, add a clear instruction
        # for the model to continue acting on them.
        has_tool_results = any(
            msg.get("role") == "tool_result" for msg in messages
        )
        if has_tool_results and tools:
            parts.append(
                "<system>\n"
                "The tool results above are from YOUR previous tool calls. "
                "Based on these results, either call more tools to complete "
                "the task, or provide your final text response to the user. "
                "Do NOT re-describe what the tools returned — act on the results.\n"
                "</system>"
            )

        # Append tool definitions — use compact format to reduce token count.
        # Full JSON schemas bloat the prompt by ~40K tokens for 178 tools.
        if tools:
            tool_section = "\n<available_tools>\n"
            for tool in tools:
                func = tool.get("function", tool)
                name = func.get("name", "")
                desc = func.get("description", "")
                params = func.get("parameters", {})
                # Compact param summary: just names, types, and required flag
                props = params.get("properties", {})
                required = set(params.get("required", []))
                if props:
                    param_parts = []
                    for pname, pdef in props.items():
                        ptype = pdef.get("type", "string")
                        req = " (required)" if pname in required else ""
                        pdesc = pdef.get("description", "")
                        short_desc = f" - {pdesc[:80]}" if pdesc else ""
                        param_parts.append(f"    {pname}: {ptype}{req}{short_desc}")
                    param_str = "\n".join(param_parts)
                    tool_section += f"- {name}: {desc}\n{param_str}\n"
                else:
                    tool_section += f"- {name}: {desc}\n"
            tool_section += (
                "\nRemember: output ONLY {\"tool_calls\": [{\"name\": \"...\", \"arguments\": {...}}]} "
                "to call tools. No narration.\n"
                "</available_tools>\n"
            )
            parts.append(tool_section)

        return "\n\n".join(parts)

    @staticmethod
    def _strip_serialization_artifacts(text: str) -> str | None:
        """Remove echoed XML-like context blocks from the model's response.

        The CLI receives context serialized as ``<tool_call>...</tool_call>``,
        ``<tool_result>...</tool_result>``, ``<system>...</system>``, etc.
        The model sometimes echoes these blocks in its final answer.
        """
        # Remove <tag>...</tag> blocks for context-serialization tags
        cleaned = re.sub(
            r"<(tool_call|tool_result|system|available_tools)>.*?</\1>",
            "",
            text,
            flags=re.DOTALL,
        )
        # Collapse excessive whitespace left behind
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
        return cleaned or None

    def _extract_tool_calls(self, text: str) -> tuple[list[ToolCall], str]:
        """Extract tool call JSON from the model's text response.

        The CLI returns tool calls as text (since ``-p`` mode is one-shot).
        The model is instructed to output::

            {"tool_calls": [{"name": "tool_name", "arguments": {...}}]}

        Returns (tool_calls, remaining_text) where remaining_text is the
        content with the JSON block removed.
        """
        if not text or "tool_calls" not in text:
            return [], text

        # Try to find a JSON object containing "tool_calls" in the text.
        # The model may wrap it in markdown code fences or output it inline.
        # Strategy: find the outermost { } that contains "tool_calls".

        # Strip markdown code fences if present
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?\s*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

        # Try parsing the entire cleaned text as JSON
        try:
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict) and "tool_calls" in parsed:
                calls = []
                for tc in parsed["tool_calls"]:
                    calls.append(ToolCall(
                        tool_name=tc.get("name", ""),
                        arguments=tc.get("arguments", {}),
                    ))
                if calls:
                    # Extract any text before/after the JSON block
                    remaining = ""
                    return calls, remaining
        except (json.JSONDecodeError, TypeError):
            pass

        # Try to find JSON embedded in surrounding text
        # Look for {"tool_calls": ...} pattern
        brace_depth = 0
        start_idx = None
        for i, ch in enumerate(text):
            if ch == "{" and brace_depth == 0:
                # Check if this could be our tool_calls object
                start_idx = i
                brace_depth = 1
            elif ch == "{":
                brace_depth += 1
            elif ch == "}":
                brace_depth -= 1
                if brace_depth == 0 and start_idx is not None:
                    candidate = text[start_idx : i + 1]
                    try:
                        parsed = json.loads(candidate)
                        if isinstance(parsed, dict) and "tool_calls" in parsed:
                            calls = []
                            for tc in parsed["tool_calls"]:
                                calls.append(ToolCall(
                                    tool_name=tc.get("name", ""),
                                    arguments=tc.get("arguments", {}),
                                ))
                            if calls:
                                remaining = (
                                    text[:start_idx].strip()
                                    + " "
                                    + text[i + 1 :].strip()
                                ).strip()
                                return calls, remaining
                    except (json.JSONDecodeError, TypeError):
                        pass
                    start_idx = None

        return [], text

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

        # Check if the response text contains tool calls (CLI can't do
        # structured tool_use, so the model writes them as JSON text)
        tool_calls: list[ToolCall] = []
        if content:
            tool_calls, remaining_text = self._extract_tool_calls(content)
            if tool_calls:
                content = remaining_text or None
                stop_reason = "tool_use"
                logger.info(
                    "cli_tool_calls_extracted",
                    tool_count=len(tool_calls),
                    tools=[tc.tool_name for tc in tool_calls],
                )

        # Strip serialization artifacts the model may echo back.
        # The CLI gets context as XML-like blocks (<tool_call>, <tool_result>,
        # <system>, etc.) and sometimes echoes them in its response.
        if content:
            content = self._strip_serialization_artifacts(content)

        return LLMResponse(
            content=content or None,
            tool_calls=tool_calls,
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
