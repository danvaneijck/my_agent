"""Agent loop - the core reason/act/observe cycle."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm_router.providers.base import LLMResponse
from core.llm_router.router import LLMRouter
from core.llm_router.token_counter import estimate_cost
from core.orchestrator.context_builder import ContextBuilder
from core.orchestrator.tool_registry import ToolRegistry
from shared.config import Settings, parse_list
from shared.models.conversation import Conversation, Message
from shared.models.file import FileRecord
from shared.models.persona import Persona
from shared.models.token_usage import TokenLog
from shared.models.user import User, UserPlatformLink
from shared.schemas.messages import AgentResponse, IncomingMessage

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
    ):
        self.settings = settings
        self.llm_router = llm_router
        self.tool_registry = tool_registry
        self.context_builder = context_builder
        self.session_factory = session_factory

    async def run(self, incoming: IncomingMessage) -> AgentResponse:
        """Execute the agent loop for an incoming message."""
        async with self.session_factory() as session:
            try:
                return await self._run_inner(session, incoming)
            except Exception as e:
                logger.error("agent_loop_error", error=str(e), exc_info=True)
                return AgentResponse(
                    content="I encountered an internal error. Please try again.",
                    error=str(e),
                )

    async def _run_inner(
        self,
        session: AsyncSession,
        incoming: IncomingMessage,
    ) -> AgentResponse:
        # 1. Resolve user
        user = await self._resolve_user(session, incoming)

        # 2. Check token budget
        if not self._check_budget(user):
            return AgentResponse(
                content="You've exceeded your monthly token budget. Please contact an admin to increase your limit."
            )

        # 3. Resolve persona
        persona = await self._resolve_persona(session, incoming)

        # 4. Resolve conversation
        conversation = await self._resolve_conversation(session, user, incoming, persona)

        # 5. Get available tools
        allowed_modules = json.loads(persona.allowed_modules) if persona else parse_list(self.settings.default_guest_modules)
        tools = self.tool_registry.get_tools_for_user(user.permission_level, allowed_modules)
        openai_tools = self.tool_registry.tools_to_openai_format(tools) if tools else None

        # 6. Determine model (None lets the router pick its effective default)
        model = persona.default_model if persona and persona.default_model else None
        max_tokens = persona.max_tokens_per_request if persona else 4000

        # 7. Register attachments as FileRecords and enrich content
        message_content = incoming.content
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

            file_context = "\n\n[Attached files:]\n"
            for att in incoming.attachments:
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
            message_content += file_context

        # 8. Build context
        context = await self.context_builder.build(
            session=session,
            user=user,
            conversation=conversation,
            persona=persona,
            incoming_message=message_content,
            model=model,
        )

        # Save the incoming user message
        user_msg = Message(
            id=uuid.uuid4(),
            conversation_id=conversation.id,
            role="user",
            content=message_content,
            created_at=datetime.now(timezone.utc),
        )
        session.add(user_msg)

        # 8. Agent loop
        final_content = ""
        files: list[dict] = []
        iteration = 0

        while iteration < self.settings.max_agent_iterations:
            iteration += 1

            # Call LLM
            llm_response: LLMResponse = await self.llm_router.chat(
                messages=context,
                tools=openai_tools,
                model=model,
                max_tokens=max_tokens,
            )

            # Log token usage
            cost = estimate_cost(
                llm_response.model or model,
                llm_response.input_tokens,
                llm_response.output_tokens,
            )
            token_log = TokenLog(
                id=uuid.uuid4(),
                user_id=user.id,
                conversation_id=conversation.id,
                model=llm_response.model or model,
                input_tokens=llm_response.input_tokens,
                output_tokens=llm_response.output_tokens,
                cost_estimate=cost,
                created_at=datetime.now(timezone.utc),
            )
            session.add(token_log)

            # Update user token usage
            user.tokens_used_this_month += (
                llm_response.input_tokens + llm_response.output_tokens
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

                # Execute tool
                result = await self.tool_registry.execute_tool(tool_call)

                # If first attempt fails, retry once
                if not result.success:
                    logger.warning(
                        "tool_call_failed_retrying",
                        tool=tool_call.tool_name,
                        error=result.error,
                    )
                    result = await self.tool_registry.execute_tool(tool_call)

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

                # Append to context for the LLM
                context.append({
                    "role": "tool_call",
                    "name": tool_call.tool_name,
                    "arguments": tool_call.arguments,
                    "tool_use_id": tool_use_id,
                })
                context.append({
                    "role": "tool_result",
                    "name": tool_call.tool_name,
                    "content": str(result.result) if result.success else f"Error: {result.error}",
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

        return AgentResponse(content=final_content, files=files)

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

            result = await session.execute(
                select(User).where(User.id == link.user_id)
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
