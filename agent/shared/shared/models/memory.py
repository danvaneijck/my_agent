"""Memory summary model with vector embeddings."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class MemorySummary(Base):
    __tablename__ = "memory_summaries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id"), default=None
    )
    summary: Mapped[str] = mapped_column(Text)
    embedding = Column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
