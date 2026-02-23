"""Crew context entry — shared scratchpad for inter-agent communication."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class CrewContextEntry(Base):
    __tablename__ = "crew_context_entries"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crew_sessions.id", ondelete="CASCADE")
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("crew_members.id"), default=None
    )

    # Entry classification
    entry_type: Mapped[str] = mapped_column(String)  # decision|api_contract|interface|note|blocker|merge_result

    title: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
