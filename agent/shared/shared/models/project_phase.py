"""Project phase model for grouping tasks into milestones."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class ProjectPhase(Base):
    __tablename__ = "project_phases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))

    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    order_index: Mapped[int] = mapped_column(Integer, default=0)

    # Git branch for this phase (e.g. "phase/0/core-api-setup")
    branch_name: Mapped[str | None] = mapped_column(String, default=None)

    # Lifecycle: planned → in_progress → completed
    status: Mapped[str] = mapped_column(String, default="planned")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
