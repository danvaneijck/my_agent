"""Context builder - assembles LLM context for each request."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.conversation import Conversation, Message
from shared.models.memory import MemorySummary
from shared.models.persona import Persona
from shared.models.user import User
from shared.utils.tokens import count_messages_tokens

logger = structlog.get_logger()

# Approximate context window sizes for models
MODEL_CONTEXT_WINDOWS = {
    "claude": 200000,
    "gpt-4o": 128000,
    "gpt-4o-mini": 128000,
    "gemini": 1000000,
}

DEFAULT_CONTEXT_WINDOW = 128000


class ContextBuilder:
    """Assembles the LLM context for each request."""

    def __init__(self, settings, llm_router=None):
        self.settings = settings
        self.llm_router = llm_router

    def _get_context_budget(self, model: str) -> int:
        """Get 80% of the model's context window."""
        for prefix, window in MODEL_CONTEXT_WINDOWS.items():
            if model.startswith(prefix):
                return int(window * 0.8)
        return int(DEFAULT_CONTEXT_WINDOW * 0.8)

    async def build(
        self,
        session: AsyncSession,
        user: User,
        conversation: Conversation,
        persona: Persona | None,
        incoming_message: str,
        model: str | None = None,
    ) -> list[dict]:
        """Build the context messages list for an LLM call.

        Structure:
        1. System prompt (persona + tools + datetime)
        2. Relevant semantic memories (max 3)
        3. Conversation summary (if partially summarized)
        4. Recent working memory (last N messages)
        5. New user message
        """
        target_model = model or self.settings.default_model
        budget = self._get_context_budget(target_model)
        messages: list[dict] = []

        # 1. System prompt
        system_prompt = self._build_system_prompt(persona)
        messages.append({"role": "system", "content": system_prompt})

        # 2. Semantic memories (if embedding/llm_router is available)
        memories = await self._get_semantic_memories(session, user, incoming_message)
        if memories:
            memory_text = "Relevant context from past conversations:\n"
            for mem in memories:
                memory_text += f"- {mem.summary}\n"
            messages.append({"role": "system", "content": memory_text})

        # 3. Conversation summary
        if conversation.is_summarized:
            summary = await self._get_conversation_summary(session, conversation)
            if summary:
                messages.append({
                    "role": "system",
                    "content": f"Summary of earlier conversation:\n{summary}",
                })

        # 4. Working memory (recent messages)
        recent_messages = await self._get_recent_messages(session, conversation)
        for msg in recent_messages:
            if msg.role == "tool_call":
                try:
                    data = json.loads(msg.content)
                    messages.append({
                        "role": "tool_call",
                        "name": data.get("name", ""),
                        "arguments": data.get("arguments", {}),
                        "tool_use_id": data.get("tool_use_id", ""),
                    })
                except json.JSONDecodeError:
                    messages.append({"role": "assistant", "content": msg.content})
            elif msg.role == "tool_result":
                try:
                    data = json.loads(msg.content)
                    messages.append({
                        "role": "tool_result",
                        "name": data.get("name", ""),
                        "content": data.get("result", ""),
                        "tool_use_id": data.get("tool_use_id", ""),
                    })
                except json.JSONDecodeError:
                    messages.append({"role": "user", "content": msg.content})
            else:
                messages.append({"role": msg.role, "content": msg.content})

        # 5. New user message
        messages.append({"role": "user", "content": incoming_message})

        # Trim to fit within budget
        messages = self._trim_to_budget(messages, budget, target_model)

        return messages

    def _build_system_prompt(self, persona: Persona | None) -> str:
        """Build the system prompt from persona configuration."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if persona:
            return (
                f"{persona.system_prompt}\n\n"
                f"Current date and time: {now}\n"
                f"You have access to tools. Use them when needed to accomplish tasks."
            )
        return (
            "You are a helpful AI assistant with access to various tools. "
            "Be concise, accurate, and helpful. If you're unsure about something, say so.\n\n"
            f"Current date and time: {now}\n"
            "You have access to tools. Use them when needed to accomplish tasks."
        )

    async def _get_semantic_memories(
        self,
        session: AsyncSession,
        user: User,
        query: str,
        max_results: int = 3,
    ) -> list[MemorySummary]:
        """Retrieve semantically relevant memories via vector search."""
        if not self.llm_router:
            return []

        try:
            query_embedding = await self.llm_router.embed(query)
        except Exception as e:
            logger.warning("embedding_failed", error=str(e))
            return []

        # Vector similarity search using pgvector
        try:
            result = await session.execute(
                select(MemorySummary)
                .where(MemorySummary.user_id == user.id)
                .where(MemorySummary.embedding.isnot(None))
                .order_by(MemorySummary.embedding.cosine_distance(query_embedding))
                .limit(max_results)
            )
            return list(result.scalars().all())
        except Exception as e:
            logger.warning("semantic_search_failed", error=str(e))
            return []

    async def _get_conversation_summary(
        self,
        session: AsyncSession,
        conversation: Conversation,
    ) -> str | None:
        """Get the summary for a partially summarized conversation."""
        result = await session.execute(
            select(MemorySummary)
            .where(MemorySummary.conversation_id == conversation.id)
            .order_by(MemorySummary.created_at.desc())
            .limit(1)
        )
        summary = result.scalar_one_or_none()
        return summary.summary if summary else None

    async def _get_recent_messages(
        self,
        session: AsyncSession,
        conversation: Conversation,
    ) -> list[Message]:
        """Get the most recent messages from a conversation."""
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at.desc())
            .limit(self.settings.working_memory_messages)
        )
        messages = list(result.scalars().all())
        messages.reverse()  # Oldest first
        return messages

    def _trim_to_budget(
        self,
        messages: list[dict],
        budget: int,
        model: str,
    ) -> list[dict]:
        """Trim messages to fit within the token budget.

        Tool call/result pairs are treated as atomic groups so that
        trimming never produces an orphaned tool_result without its
        preceding tool_call (which causes API errors on all providers).
        """
        total = count_messages_tokens(messages, model)
        if total <= budget:
            return messages

        # Keep system messages and the latest user message, trim from the middle
        system_msgs = [m for m in messages if m["role"] == "system"]
        user_msg = messages[-1]  # The new user message
        middle_msgs = [m for m in messages if m["role"] != "system" and m is not user_msg]

        # Group messages so that consecutive tool_call/tool_result runs
        # are treated as a single removable unit.
        groups: list[list[dict]] = []
        for msg in middle_msgs:
            if msg["role"] in ("tool_call", "tool_result"):
                # Attach to the current tool group if one exists
                if groups and groups[-1][0]["role"] in ("tool_call", "tool_result"):
                    groups[-1].append(msg)
                else:
                    groups.append([msg])
            else:
                groups.append([msg])

        # Remove oldest groups until we fit
        while groups and count_messages_tokens(
            system_msgs + [m for g in groups for m in g] + [user_msg], model
        ) > budget:
            groups.pop(0)

        trimmed_middle = [m for g in groups for m in g]

        # Safety: strip any leading orphaned tool_result messages that
        # could remain if the DB already contained broken history.
        while trimmed_middle and trimmed_middle[0]["role"] == "tool_result":
            trimmed_middle.pop(0)

        return system_msgs + trimmed_middle + [user_msg]
