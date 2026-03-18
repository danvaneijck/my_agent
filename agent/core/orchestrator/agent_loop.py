"""Agent loop - the core reason/act/observe cycle."""

from __future__ import annotations

import asyncio
import base64
import json
import traceback
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm_router.providers.base import LLMResponse, PromptTooLongError
from core.llm_router.router import LLMRouter
from core.llm_router.token_counter import estimate_cost
from core.orchestrator.context_builder import ContextBuilder
from core.orchestrator.tool_registry import ToolRegistry
from shared.config import Settings, parse_list
from shared.error_capture import capture_error
from shared.utils.tokens import count_tokens, count_messages_tokens
from shared.llm_settings_resolver import get_user_llm_overrides, get_user_claude_code_oauth
from shared.models.conversation import Conversation, Message
from shared.models.file import FileRecord
from shared.models.persona import Persona
from shared.models.token_usage import TokenLog
from shared.models.user import User, UserPlatformLink
from shared.schemas.messages import (
    AgentResponse,
    IncomingMessage,
    StreamEvent,
    ToolCallsMetadata,
    ToolCallSummary,
)
from typing import AsyncGenerator

logger = structlog.get_logger()


class AgentLoop:
    """The core reasoning cycle for the AI agent."""

    def __init__(
        self,
        settings: Settings,
        llm_router: LLMRouter,
        tool_registry: ToolRegistry,
        context_builder: ContextBuilder,
        session_factory,
        credential_store=None,
    ):
        self.settings = settings
        self.llm_router = llm_router
        self.tool_registry = tool_registry
        self.context_builder = context_builder
        self.session_factory = session_factory
        self.credential_store = credential_store

        # MinIO client for downloading image attachments (vision support)
        self._minio = None
        try:
            from minio import Minio
            self._minio = Minio(
                settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=False,
            )
        except Exception as e:
            logger.warning("minio_client_init_failed", error=str(e))

    async def run(self, incoming: IncomingMessage) -> AgentResponse:
        """Execute the agent loop for an incoming message (non-streaming).

        Consumes the streaming generator and returns the final AgentResponse.
        """
        final_response = AgentResponse(
            content="I encountered an internal error. Please try again.",
            error="No response generated",
        )
        async for event in self.run_stream(incoming):
            if event.event == "done":
                final_response = AgentResponse(**event.data)
            elif event.event == "error":
                final_response = AgentResponse(
                    content="I encountered an internal error. Please try again.",
                    error=event.data.get("error", "Unknown error"),
                )
        return final_response

    async def run_stream(
        self, incoming: IncomingMessage
    ) -> AsyncGenerator[StreamEvent, None]:
        """Execute the agent loop, yielding StreamEvents as work progresses."""
        async with self.session_factory() as session:
            try:
                async for event in self._run_inner(session, incoming):
                    yield event
            except Exception as e:
                logger.error("agent_loop_error", error=str(e), exc_info=True)
                asyncio.create_task(
                    capture_error(
                        self.session_factory,
                        service="core",
                        error_type="agent_loop",
                        error_message=str(e),
                        stack_trace=traceback.format_exc(),
                    )
                )
                yield StreamEvent(event="error", data={"error": str(e)})

    async def _run_inner(
        self,
        session: AsyncSession,
        incoming: IncomingMessage,
    ) -> AsyncGenerator[StreamEvent, None]:
        # 1. Resolve user
        user = await self._resolve_user(session, incoming)

        # 2a. Check for user-configured LLM API keys.
        # If the user has stored personal keys we build a one-off LLMRouter
        # that uses those keys instead of the global env-var ones.
        user_overrides = await get_user_llm_overrides(
            session, user.id, self.credential_store
        )
        if user_overrides:
            user_settings = self.settings.model_copy(update=user_overrides)
            active_router = LLMRouter(user_settings)
            user_has_own_keys = True
            using_claude_oauth = False
            logger.info("using_user_llm_keys", user_id=str(user.id))
        else:
            # 2a-bis. Fall back to Claude Code CLI with OAuth credentials.
            # Users with a Claude Code subscription can use the CLI as
            # the LLM backend without a separate API key.
            oauth_json = await get_user_claude_code_oauth(
                session, user.id, self.credential_store
            )
            if oauth_json:
                from core.llm_router.providers.claude_code_oauth import (
                    ClaudeCodeCLIProvider,
                )

                cli_provider = ClaudeCodeCLIProvider(
                    credentials_json=oauth_json,
                    credential_store=self.credential_store,
                    user_id=str(user.id),
                    session_factory=self.session_factory,
                )
                active_router = LLMRouter.with_provider_override(
                    self.settings, "anthropic", cli_provider,
                )
                user_has_own_keys = True
                using_claude_oauth = True
                logger.info("using_claude_code_oauth", user_id=str(user.id))
            else:
                active_router = self.llm_router
                user_has_own_keys = False
                using_claude_oauth = False

        # 2b. Check token budget — skipped when user brings their own API keys.
        if not user_has_own_keys and not self._check_budget(user):
            yield StreamEvent(event="done", data=AgentResponse(
                content="You've exceeded your monthly token budget. Please contact an admin to increase your limit."
            ).model_dump())
            return

        # 3. Resolve persona
        persona = await self._resolve_persona(session, incoming)

        # 4. Resolve conversation
        conversation = await self._resolve_conversation(session, user, incoming, persona)

        # 4b. Commit so cross-container tool calls (scheduler, location)
        # can reference the conversation via FK
        await session.commit()

        # 5. Get available tools
        allowed_modules = json.loads(persona.allowed_modules) if persona else parse_list(self.settings.default_guest_modules)
        tools = self.tool_registry.get_tools_for_user(user.permission_level, allowed_modules)
        openai_tools = self.tool_registry.tools_to_openai_format(tools) if tools else None

        logger.info(
            "tools_available",
            user_permission=user.permission_level,
            allowed_modules=allowed_modules,
            discovered_modules=list(self.tool_registry.manifests.keys()),
            tool_count=len(tools),
            tool_names=[t.name for t in tools],
        )

        # 6. Determine model (None lets the router pick its effective default)
        # When using CLI provider, use its default (Opus) rather than persona model
        if using_claude_oauth:
            model = None  # CLI provider defaults to claude-opus-4-6
        else:
            model = persona.default_model if persona and persona.default_model else None
        max_tokens = persona.max_tokens_per_request if persona else 4000

        # 5b. Measure actual tool definition token overhead
        if openai_tools:
            tools_json = json.dumps(openai_tools)
            tool_overhead = int(count_tokens(tools_json, model or self.settings.default_model) * 1.2)
        else:
            tool_overhead = 0

        # 7. Register attachments as FileRecords and enrich content
        message_content: str | list = incoming.content
        if incoming.attachments:
            # Create FileRecord for each attachment now that we have the real user_id
            for att in incoming.attachments:
                file_id = uuid.uuid4()
                record = FileRecord(
                    id=file_id,
                    user_id=user.id,
                    filename=att.get("filename", "file"),
                    minio_key=att.get("minio_key", ""),
                    mime_type=att.get("mime_type"),
                    size_bytes=att.get("size_bytes"),
                    public_url=att.get("url", ""),
                    created_at=datetime.now(timezone.utc),
                )
                session.add(record)
                att["file_id"] = str(file_id)
            await session.commit()  # commit so other containers (code_executor) can see them

            # Separate images (for vision) from other files (for tool hints)
            _IMAGE_MIMES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
            image_atts = [a for a in incoming.attachments if a.get("mime_type") in _IMAGE_MIMES]
            other_atts = [a for a in incoming.attachments if a.get("mime_type") not in _IMAGE_MIMES]

            # Download images and build vision content blocks
            image_blocks: list[dict] = []
            for att in image_atts:
                try:
                    minio_key = att.get("minio_key", "")
                    if not minio_key or not self._minio:
                        other_atts.append(att)
                        continue
                    # Download from MinIO using authenticated client
                    resp = self._minio.get_object(
                        self.settings.minio_bucket, minio_key,
                    )
                    try:
                        img_bytes = resp.read()
                    finally:
                        resp.close()
                        resp.release_conn()

                    # Cap at 20 MB for vision (Anthropic API limit)
                    if len(img_bytes) > 20 * 1024 * 1024:
                        logger.info("image_too_large_for_vision", size=len(img_bytes))
                        other_atts.append(att)
                        continue

                    b64 = base64.standard_b64encode(img_bytes).decode("ascii")
                    image_blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": att["mime_type"],
                            "data": b64,
                        },
                    })
                    logger.info(
                        "image_attached_for_vision",
                        filename=att.get("filename"),
                        size=len(img_bytes),
                    )
                except Exception as e:
                    logger.warning(
                        "image_vision_prep_failed",
                        filename=att.get("filename"),
                        error=str(e),
                    )
                    other_atts.append(att)

            # Build file context hint for non-image attachments
            file_context = ""
            if other_atts:
                file_context = "\n\n[Attached files:]\n"
                for att in other_atts:
                    fname = att.get("filename", "file")
                    fid = att.get("file_id", "")
                    fsize = att.get("size_bytes", 0)
                    fmime = att.get("mime_type", "")
                    file_context += (
                        f"- {fname} (file_id: {fid}, {fsize} bytes, {fmime})\n"
                    )
                file_context += (
                    "Use file_manager.read_document(file_id) to read text files, "
                    "or code_executor.load_file(file_id) then run_python to process them."
                )

            # Build the message content — use content blocks if we have images
            if image_blocks:
                content_blocks: list[dict] = []
                text_content = incoming.content + file_context
                if text_content.strip():
                    content_blocks.append({"type": "text", "text": text_content})
                content_blocks.extend(image_blocks)
                # Also note the image file_ids for reference
                for att in image_atts:
                    if att.get("file_id"):
                        content_blocks.append({
                            "type": "text",
                            "text": f"[Image: {att.get('filename', 'image')} (file_id: {att['file_id']})]",
                        })
                message_content = content_blocks
            else:
                message_content = incoming.content + file_context

        # 7b. Vision fallback — the CLI provider can't pass images, so when
        # images are attached and we're on Claude OAuth, fall back to the
        # global LLM router (which uses the API key and supports vision).
        has_images = isinstance(message_content, list) and any(
            b.get("type") == "image" for b in message_content
        )
        if has_images and using_claude_oauth:
            if self.llm_router.providers:
                logger.info("vision_fallback_to_api", user_id=str(user.id))
                active_router = self.llm_router
                using_claude_oauth = False
            else:
                logger.warning("vision_no_api_fallback", user_id=str(user.id))

        # 8. Build context — pass the active router so semantic memory embeddings
        # also use the user's own keys when configured.
        context = await self.context_builder.build(
            session=session,
            user=user,
            conversation=conversation,
            persona=persona,
            incoming_message=message_content,
            model=model,
            tool_count=len(tools),
            llm_router=active_router,
            tool_overhead_tokens=tool_overhead,
        )

        # Save the incoming user message (text only — images are ephemeral)
        stored_content = (
            message_content if isinstance(message_content, str)
            else " ".join(
                b.get("text", "") for b in message_content if b.get("type") == "text"
            )
        )
        user_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="user",
            content=stored_content,
            created_at=datetime.now(timezone.utc),
        )
        session.add(user_msg)

        # 8. Agent loop
        # Pre-compute context budget for in-loop re-trimming
        target_model = model or self.settings.default_model
        context_budget = self.context_builder._get_context_budget(target_model) - tool_overhead

        final_content = ""
        files: list[dict] = []
        tool_call_summaries: list[ToolCallSummary] = []
        iteration = 0

        while iteration < self.settings.max_agent_iterations:
            iteration += 1

            # Emit thinking event before LLM call
            yield StreamEvent(event="thinking", data={
                "iteration": iteration,
            })

            # Call LLM — use per-user router when the user has personal API keys.
            try:
                llm_response: LLMResponse = await active_router.chat(
                    messages=context,
                    tools=openai_tools,
                    model=model,
                    max_tokens=max_tokens,
                )
            except PromptTooLongError:
                logger.warning(
                    "prompt_too_long_recovering",
                    context_messages=len(context),
                    iteration=iteration,
                )
                context = self._emergency_trim(context)
                llm_response = await active_router.chat(
                    messages=context,
                    tools=openai_tools,
                    model=model,
                    max_tokens=max_tokens,
                )

            # Log token usage (including Anthropic prompt cache tokens)
            cache_write = llm_response.cache_creation_input_tokens
            cache_read = llm_response.cache_read_input_tokens
            # Zero cost for Claude Code OAuth — billed to subscription, not API
            cost = (
                0.0 if using_claude_oauth
                else estimate_cost(
                    llm_response.model or model,
                    llm_response.input_tokens,
                    llm_response.output_tokens,
                    cache_creation_input_tokens=cache_write,
                    cache_read_input_tokens=cache_read,
                )
            )
            token_log = TokenLog(
                id=uuid.uuid4(),
                user_id=user.id,
                conversation_id=conversation.id,
                model=llm_response.model or model,
                input_tokens=llm_response.input_tokens,
                output_tokens=llm_response.output_tokens,
                cache_creation_input_tokens=cache_write,
                cache_read_input_tokens=cache_read,
                cost_estimate=cost,
                created_at=datetime.now(timezone.utc),
            )
            session.add(token_log)

            # Update user token usage — skip for Claude Code OAuth users
            # since their usage is billed to their subscription, not our API.
            if not using_claude_oauth:
                user.tokens_used_this_month += (
                    llm_response.input_tokens
                    + llm_response.output_tokens
                    + cache_write
                    + cache_read
                )

            # If LLM returns final text
            if llm_response.stop_reason != "tool_use" or not llm_response.tool_calls:
                final_content = llm_response.content or ""
                # Save assistant message
                assistant_msg = Message(
                    id=uuid.uuid4(),
                    conversation_id=conversation.id,
                    role="assistant",
                    content=final_content,
                    token_count=llm_response.output_tokens,
                    model_used=llm_response.model or model,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(assistant_msg)
                break

            # Handle tool calls
            if llm_response.content:
                # Some models return text alongside tool calls
                final_content = llm_response.content
                yield StreamEvent(event="content", data={
                    "text": llm_response.content,
                    "iteration": iteration,
                })

            # Insert an assistant turn into context so the CLI model understands
            # that IT made the tool calls (not the user).  Without this, the
            # serialized context shows tool_call/tool_result blocks with no
            # attribution, confusing the model on subsequent iterations.
            if using_claude_oauth:
                assistant_text = llm_response.content or ""
                if llm_response.tool_calls:
                    tool_names = ", ".join(tc.tool_name for tc in llm_response.tool_calls)
                    assistant_text += f"\n[Calling tools: {tool_names}]"
                context.append({"role": "assistant", "content": assistant_text.strip()})

            for tool_call in llm_response.tool_calls:
                tool_use_id = f"tool_{uuid.uuid4().hex[:12]}"

                # Save tool call message
                tc_msg = Message(
                    id=uuid.uuid4(),
                    conversation_id=conversation.id,
                    role="tool_call",
                    content=json.dumps({
                        "name": tool_call.tool_name,
                        "arguments": tool_call.arguments,
                        "tool_use_id": tool_use_id,
                    }),
                    created_at=datetime.now(timezone.utc),
                )
                session.add(tc_msg)

                # Inject user context so modules can associate resources
                tool_call.user_id = str(user.id)

                # Inject conversation context for modules that send
                # proactive notifications (scheduler, location reminders)
                if tool_call.tool_name.startswith(("scheduler.", "location.", "crew.")):
                    tool_call.arguments["platform"] = conversation.platform
                    tool_call.arguments["platform_channel_id"] = conversation.platform_channel_id
                    tool_call.arguments["platform_thread_id"] = conversation.platform_thread_id
                    tool_call.arguments["platform_server_id"] = incoming.platform_server_id
                    if tool_call.tool_name == "scheduler.add_job":
                        tool_call.arguments["conversation_id"] = str(conversation.id)

                # Emit tool_call event before execution
                yield StreamEvent(event="tool_call", data={
                    "tool": tool_call.tool_name,
                    "arguments": tool_call.arguments,
                })

                # Execute tool (with server-side permission check)
                result = await self.tool_registry.execute_tool(
                    tool_call, user_permission=user.permission_level,
                )

                # If first attempt fails, retry once
                if not result.success and "Permission denied" not in (result.error or ""):
                    logger.warning(
                        "tool_call_failed_retrying",
                        tool=tool_call.tool_name,
                        error=result.error,
                    )
                    result = await self.tool_registry.execute_tool(
                        tool_call, user_permission=user.permission_level,
                    )

                # Emit tool_result event
                yield StreamEvent(event="tool_result", data={
                    "tool": tool_call.tool_name,
                    "success": result.success,
                    "error": result.error if not result.success else None,
                })

                # Track tool call for metadata
                tool_call_summaries.append(
                    ToolCallSummary(
                        name=tool_call.tool_name,
                        success=result.success,
                        tool_use_id=tool_use_id,
                    )
                )

                # Save tool result message
                result_content = json.dumps({
                    "name": tool_call.tool_name,
                    "result": result.result if result.success else None,
                    "error": result.error,
                    "tool_use_id": tool_use_id,
                })
                tr_msg = Message(
                    id=uuid.uuid4(),
                    conversation_id=conversation.id,
                    role="tool_result",
                    content=result_content,
                    created_at=datetime.now(timezone.utc),
                )
                session.add(tr_msg)

                # Append to context for the LLM (truncate large results)
                context.append({
                    "role": "tool_call",
                    "name": tool_call.tool_name,
                    "arguments": tool_call.arguments,
                    "tool_use_id": tool_use_id,
                })
                result_text = str(result.result) if result.success else f"Error: {result.error}"
                max_chars = self.settings.tool_result_max_chars
                if len(result_text) > max_chars:
                    result_text = result_text[:max_chars] + "\n... [truncated — result too large]"
                context.append({
                    "role": "tool_result",
                    "name": tool_call.tool_name,
                    "content": result_text,
                    "tool_use_id": tool_use_id,
                })

                # Check for file URLs in results
                if result.success and isinstance(result.result, dict):
                    if "url" in result.result:
                        files.append({
                            "filename": result.result.get("filename", "file"),
                            "url": result.result["url"],
                        })
                    # Also handle nested files list (e.g. from code_executor)
                    for f in result.result.get("files", []):
                        if isinstance(f, dict) and "url" in f:
                            files.append({
                                "filename": f.get("filename", "file"),
                                "url": f["url"],
                            })

            # Re-trim context after tool results to prevent exceeding budget
            context = self._retrim_context(context, context_budget, target_model)

        else:
            # Max iterations reached
            if not final_content:
                final_content = "I wasn't able to complete the task within the allowed number of steps. Here's what I have so far."
            assistant_msg = Message(
                id=uuid.uuid4(),
                conversation_id=conversation.id,
                role="assistant",
                content=final_content,
                created_at=datetime.now(timezone.utc),
            )
            session.add(assistant_msg)

        # Update conversation timestamp
        conversation.last_active_at = datetime.now(timezone.utc)
        await session.commit()

        # Build tool calls metadata if any tools were called
        tool_metadata = None
        if tool_call_summaries:
            unique_tool_names = set(tc.name for tc in tool_call_summaries)
            tool_metadata = ToolCallsMetadata(
                total_count=len(tool_call_summaries),
                unique_tools=len(unique_tool_names),
                tools_sequence=tool_call_summaries,
            )

        # Guard: detect broken follow-up promises.
        # If the response mentions following up but no scheduler job was created,
        # strip the false promise and add a note.
        import re as _re
        _followup_pattern = _re.compile(
            r"I'?ll\s+(notify|update|check back|follow up|let you know|monitor|keep you|"
            r"get back to you|watch|ping you)",
            _re.IGNORECASE,
        )
        scheduler_was_called = any(
            tc.name.startswith("scheduler.") for tc in tool_call_summaries
        )
        if final_content and _followup_pattern.search(final_content) and not scheduler_was_called:
            logger.warning("false_followup_detected", content_snippet=final_content[:200])
            # Remove the false promise sentence(s)
            final_content = _followup_pattern.sub("", final_content).strip()
            # Clean up orphaned punctuation
            final_content = _re.sub(r"\s+[.!]\s*$", ".", final_content)

        yield StreamEvent(event="done", data=AgentResponse(
            content=final_content, files=files, tool_calls_metadata=tool_metadata
        ).model_dump())

    async def _resolve_user(
        self,
        session: AsyncSession,
        incoming: IncomingMessage,
    ) -> User:
        """Get or create a user from the platform ID."""
        result = await session.execute(
            select(UserPlatformLink).where(
                UserPlatformLink.platform == incoming.platform,
                UserPlatformLink.platform_user_id == incoming.platform_user_id,
            )
        )
        link = result.scalar_one_or_none()

        if link:
            # Update username if changed
            if incoming.platform_username and link.platform_username != incoming.platform_username:
                link.platform_username = incoming.platform_username

            # Lock the user row to prevent concurrent budget race conditions
            result = await session.execute(
                select(User).where(User.id == link.user_id).with_for_update()
            )
            user = result.scalar_one()

            # Check if budget needs reset (monthly)
            if user.budget_reset_at < datetime.now(timezone.utc) - timedelta(days=30):
                user.tokens_used_this_month = 0
                user.budget_reset_at = datetime.now(timezone.utc)

            return user

        # Create new guest user
        user = User(
            id=uuid.uuid4(),
            permission_level="guest",
            token_budget_monthly=self.settings.default_guest_token_budget,
            budget_reset_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
        )
        session.add(user)

        link = UserPlatformLink(
            id=uuid.uuid4(),
            user_id=user.id,
            platform=incoming.platform,
            platform_user_id=incoming.platform_user_id,
            platform_username=incoming.platform_username,
        )
        session.add(link)
        await session.flush()

        logger.info(
            "new_user_created",
            user_id=str(user.id),
            platform=incoming.platform,
        )
        return user

    def _check_budget(self, user: User) -> bool:
        """Check if user has remaining token budget."""
        if user.token_budget_monthly is None:
            return True  # Unlimited
        return user.tokens_used_this_month < user.token_budget_monthly

    @staticmethod
    def _retrim_context(context: list[dict], budget: int, model: str) -> list[dict]:
        """Re-trim context mid-loop to stay within token budget.

        Preserves system messages and the most recent non-system messages
        (the current reasoning chain), dropping older history from the
        middle when the budget is exceeded.
        """
        total = count_messages_tokens(context, model)
        if total <= budget:
            return context

        system = [m for m in context if m["role"] == "system"]
        non_system = [m for m in context if m["role"] != "system"]

        # Keep the tail (last 4 non-system messages) to preserve the
        # most recent tool_call/tool_result pair and current exchange.
        tail_count = min(4, len(non_system))
        middle = non_system[:-tail_count] if tail_count else non_system
        tail = non_system[-tail_count:] if tail_count else []

        while middle and count_messages_tokens(system + middle + tail, model) > budget:
            middle.pop(0)

        result = system + middle + tail
        return ContextBuilder._sanitize_tool_pairs(result)

    @staticmethod
    def _emergency_trim(context: list[dict]) -> list[dict]:
        """Aggressively trim context as a last resort for prompt-too-long recovery.

        Keeps only system messages, the last user message, and the 2 most
        recent tool_call/tool_result pairs.
        """
        system = [m for m in context if m["role"] == "system"]
        non_system = [m for m in context if m["role"] != "system"]

        # Find the last user message
        last_user = None
        for m in reversed(non_system):
            if m["role"] == "user":
                last_user = m
                break

        # Keep the last 4 non-system messages (2 tool pairs)
        tail = non_system[-4:] if len(non_system) >= 4 else non_system

        # Ensure the last user message is included
        if last_user and last_user not in tail:
            tail = [last_user] + tail

        result = system + tail
        return ContextBuilder._sanitize_tool_pairs(result)

    async def _resolve_persona(
        self,
        session: AsyncSession,
        incoming: IncomingMessage,
    ) -> Persona | None:
        """Find the appropriate persona for this message."""
        # Try server-specific persona first
        if incoming.platform_server_id:
            result = await session.execute(
                select(Persona).where(
                    Persona.platform == incoming.platform,
                    Persona.platform_server_id == incoming.platform_server_id,
                )
            )
            persona = result.scalar_one_or_none()
            if persona:
                return persona

        # Try platform-specific persona
        result = await session.execute(
            select(Persona).where(
                Persona.platform == incoming.platform,
                Persona.platform_server_id.is_(None),
            )
        )
        persona = result.scalar_one_or_none()
        if persona:
            return persona

        # Fall back to default persona
        result = await session.execute(
            select(Persona).where(Persona.is_default.is_(True))
        )
        return result.scalar_one_or_none()

    async def _resolve_conversation(
        self,
        session: AsyncSession,
        user: User,
        incoming: IncomingMessage,
        persona: Persona | None,
    ) -> Conversation:
        """Find an active conversation or create a new one."""
        timeout = datetime.now(timezone.utc) - timedelta(
            minutes=self.settings.conversation_timeout_minutes
        )

        # Look for an active conversation in the same channel/thread
        query = (
            select(Conversation)
            .where(
                Conversation.user_id == user.id,
                Conversation.platform == incoming.platform,
                Conversation.platform_channel_id == incoming.platform_channel_id,
                Conversation.last_active_at > timeout,
            )
        )
        if incoming.platform_thread_id:
            query = query.where(
                Conversation.platform_thread_id == incoming.platform_thread_id
            )
        else:
            query = query.where(Conversation.platform_thread_id.is_(None))

        result = await session.execute(query.order_by(Conversation.last_active_at.desc()))
        conversation = result.scalar_one_or_none()

        if conversation:
            return conversation

        # Create new conversation
        conversation = Conversation(
            id=uuid.uuid4(),
            user_id=user.id,
            persona_id=persona.id if persona else None,
            platform=incoming.platform,
            platform_channel_id=incoming.platform_channel_id,
            platform_thread_id=incoming.platform_thread_id,
            started_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
        )
        session.add(conversation)
        await session.flush()

        logger.info(
            "new_conversation",
            conversation_id=str(conversation.id),
            user_id=str(user.id),
        )
        return conversation
