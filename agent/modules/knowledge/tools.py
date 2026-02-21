"""Knowledge module tool implementations — persistent user memory."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.auth import get_service_auth_headers
from shared.config import Settings
from shared.models.memory import MemorySummary

logger = structlog.get_logger()


class KnowledgeTools:
    """Tools for user-facing knowledge storage and retrieval."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], settings: Settings):
        self.session_factory = session_factory
        self.settings = settings

    async def _get_embedding(self, text: str) -> list[float] | None:
        """Get embedding from the core orchestrator's LLM router."""
        try:
            async with httpx.AsyncClient(timeout=15.0, headers=get_service_auth_headers()) as client:
                resp = await client.post(
                    f"{self.settings.orchestrator_url}/embed",
                    json={"text": text},
                )
                if resp.status_code == 200:
                    return resp.json().get("embedding")
        except Exception as e:
            logger.warning("embedding_request_failed", error=str(e))
        return None

    async def remember(self, content: str, user_id: str | None = None) -> dict:
        """Store a fact with its embedding for later semantic recall."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        embedding = await self._get_embedding(content)

        async with self.session_factory() as session:
            memory = MemorySummary(
                id=uuid.uuid4(),
                user_id=uid,
                conversation_id=None,
                summary=content,
                embedding=embedding,
                created_at=datetime.now(timezone.utc),
            )
            session.add(memory)
            await session.commit()

        logger.info("knowledge_stored", user_id=user_id, has_embedding=embedding is not None)
        return {
            "memory_id": str(memory.id),
            "content": content,
            "stored": True,
        }

    async def recall(self, query: str, max_results: int = 5, user_id: str | None = None) -> list[dict]:
        """Semantic search over the user's stored knowledge."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        embedding = await self._get_embedding(query)

        async with self.session_factory() as session:
            if embedding:
                # Semantic search via pgvector cosine distance
                result = await session.execute(
                    select(MemorySummary)
                    .where(MemorySummary.user_id == uid)
                    .where(MemorySummary.embedding.isnot(None))
                    .order_by(MemorySummary.embedding.cosine_distance(embedding))
                    .limit(max_results)
                )
            else:
                # Fallback: most recent memories
                result = await session.execute(
                    select(MemorySummary)
                    .where(MemorySummary.user_id == uid)
                    .order_by(MemorySummary.created_at.desc())
                    .limit(max_results)
                )

            memories = list(result.scalars().all())

        return [
            {
                "memory_id": str(m.id),
                "content": m.summary,
                "conversation_id": str(m.conversation_id) if m.conversation_id else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in memories
        ]

    async def list_memories(self, limit: int = 50, offset: int = 0, user_id: str | None = None) -> list[dict]:
        """List all stored memories for the user."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(MemorySummary)
                .where(MemorySummary.user_id == uid)
                .order_by(MemorySummary.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            memories = list(result.scalars().all())

        return [
            {
                "memory_id": str(m.id),
                "content": m.summary,
                "conversation_id": str(m.conversation_id) if m.conversation_id else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in memories
        ]

    async def forget(self, memory_id: str, user_id: str | None = None) -> dict:
        """Delete a specific memory."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        mid = uuid.UUID(memory_id)

        async with self.session_factory() as session:
            result = await session.execute(
                delete(MemorySummary)
                .where(MemorySummary.id == mid, MemorySummary.user_id == uid)
            )
            await session.commit()

            if result.rowcount == 0:
                raise ValueError(f"Memory not found: {memory_id}")

        return {"memory_id": memory_id, "deleted": True}
