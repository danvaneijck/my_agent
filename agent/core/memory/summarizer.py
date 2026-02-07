"""Background task that summarizes old conversations."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm_router.router import LLMRouter
from core.llm_router.token_counter import estimate_cost
from shared.config import Settings
from shared.models.conversation import Conversation, Message
from shared.models.memory import MemorySummary
from shared.models.token_usage import TokenLog

logger = structlog.get_logger()


class ConversationSummarizer:
    """Summarizes old conversations and stores embeddings for semantic recall."""

    def __init__(self, settings: Settings, llm_router: LLMRouter, session_factory):
        self.settings = settings
        self.llm_router = llm_router
        self.session_factory = session_factory

    async def summarize_old_conversations(self) -> int:
        """Find and summarize conversations that are old enough.

        Returns the number of conversations summarized.
        """
        count = 0
        async with self.session_factory() as session:
            # Find conversations that:
            # - Are not yet summarized
            # - Haven't been active for at least the timeout period
            timeout = datetime.now(timezone.utc) - timedelta(
                minutes=self.settings.conversation_timeout_minutes
            )
            result = await session.execute(
                select(Conversation)
                .where(
                    Conversation.is_summarized.is_(False),
                    Conversation.last_active_at < timeout,
                )
                .limit(10)  # Process in batches
            )
            conversations = result.scalars().all()

            for conv in conversations:
                try:
                    await self._summarize_conversation(session, conv)
                    count += 1
                except Exception as e:
                    logger.error(
                        "summarization_error",
                        conversation_id=str(conv.id),
                        error=str(e),
                    )

            await session.commit()
        return count

    async def _summarize_conversation(
        self,
        session: AsyncSession,
        conversation: Conversation,
    ) -> None:
        """Summarize a single conversation and store the summary with embedding."""
        # Get all messages in the conversation
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == conversation.id)
            .order_by(Message.created_at)
        )
        messages = result.scalars().all()

        if not messages:
            conversation.is_summarized = True
            return

        # Build conversation text for summarization
        text_parts = []
        for msg in messages:
            if msg.role in ("user", "assistant"):
                role_label = "User" if msg.role == "user" else "Assistant"
                text_parts.append(f"{role_label}: {msg.content}")

        conversation_text = "\n".join(text_parts)

        # Truncate if too long
        if len(conversation_text) > 6000:
            conversation_text = conversation_text[:6000] + "\n... [truncated]"

        # Generate summary using LLM
        summary_prompt = [
            {
                "role": "system",
                "content": (
                    "You are a conversation summarizer. Create a concise summary "
                    "of the following conversation that captures the key topics, "
                    "decisions, and any important information. The summary should "
                    "be useful for providing context in future conversations."
                ),
            },
            {
                "role": "user",
                "content": f"Summarize this conversation:\n\n{conversation_text}",
            },
        ]

        llm_response = await self.llm_router.chat(
            messages=summary_prompt,
            task_type="memory_summarization",
            max_tokens=500,
            temperature=0.3,
        )

        summary_text = llm_response.content or "No summary generated."

        # Track token usage for the summarization call
        model_used = llm_response.model or "unknown"
        cost = estimate_cost(
            model_used,
            llm_response.input_tokens,
            llm_response.output_tokens,
        )
        token_log = TokenLog(
            id=uuid.uuid4(),
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            model=model_used,
            input_tokens=llm_response.input_tokens,
            output_tokens=llm_response.output_tokens,
            cost_estimate=cost,
            created_at=datetime.now(timezone.utc),
        )
        session.add(token_log)

        # Generate embedding for the summary
        embedding = None
        try:
            embedding = await self.llm_router.embed(summary_text)
        except Exception as e:
            logger.warning("embedding_generation_failed", error=str(e))

        # Store the summary
        memory = MemorySummary(
            id=uuid.uuid4(),
            user_id=conversation.user_id,
            conversation_id=conversation.id,
            summary=summary_text,
            embedding=embedding,
            created_at=datetime.now(timezone.utc),
        )
        session.add(memory)

        # Mark conversation as summarized
        conversation.is_summarized = True

        logger.info(
            "conversation_summarized",
            conversation_id=str(conversation.id),
            summary_length=len(summary_text),
        )
