"""Semantic recall — vector search over past conversations and summaries."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.llm_router.router import LLMRouter
from shared.models.memory import MemorySummary

logger = structlog.get_logger()


class SemanticRecall:
    """Performs vector similarity search over stored memory summaries."""

    def __init__(self, llm_router: LLMRouter):
        self.llm_router = llm_router

    async def search(
        self,
        session: AsyncSession,
        user_id,
        query: str,
        max_results: int = 3,
    ) -> list[MemorySummary]:
        """Search for relevant memories using embedding similarity.

        Args:
            session: Database session
            user_id: UUID of the user
            query: The query text to search for
            max_results: Maximum number of results

        Returns:
            List of relevant MemorySummary objects, ordered by relevance
        """
        try:
            query_embedding = await self.llm_router.embed(query)
        except Exception as e:
            logger.warning("embedding_failed_for_recall", error=str(e))
            return []

        try:
            result = await session.execute(
                select(MemorySummary)
                .where(
                    MemorySummary.user_id == user_id,
                    MemorySummary.embedding.isnot(None),
                )
                .order_by(
                    MemorySummary.embedding.cosine_distance(query_embedding)
                )
                .limit(max_results)
            )
            return list(result.scalars().all())
        except Exception as e:
            logger.warning("semantic_recall_error", error=str(e))
            return []

    async def get_recent_summaries(
        self,
        session: AsyncSession,
        user_id,
        limit: int = 5,
    ) -> list[MemorySummary]:
        """Get the most recent summaries for a user (fallback when no embedding)."""
        result = await session.execute(
            select(MemorySummary)
            .where(MemorySummary.user_id == user_id)
            .order_by(MemorySummary.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
