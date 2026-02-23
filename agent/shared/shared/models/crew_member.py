"""Crew member model — tracks an individual agent within a crew session."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class CrewMember(Base):
    __tablename__ = "crew_members"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("crew_sessions.id", ondelete="CASCADE")
    )

    # Optional role specialisation
    role: Mapped[str | None] = mapped_column(String, default=None)

    # Git branch this member works on
    branch_name: Mapped[str] = mapped_column(String)

    # Claude Code task tracking
    claude_task_id: Mapped[str | None] = mapped_column(String, default=None)

    # Project task assignment
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("project_tasks.id"), default=None
    )
    task_title: Mapped[str | None] = mapped_column(String, default=None)

    # Lifecycle: idle → working → merging → completed | failed
    status: Mapped[str] = mapped_column(String, default="idle")

    # Which wave this member is working in
    wave_number: Mapped[int] = mapped_column(Integer, default=0)

    # Error details on failure
    error_message: Mapped[str | None] = mapped_column(Text, default=None)

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
