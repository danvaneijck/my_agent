"""Crew session model for multi-agent collaboration."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class CrewSession(Base):
    __tablename__ = "crew_sessions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.id"), default=None
    )

    name: Mapped[str] = mapped_column(String)

    # Lifecycle: configuring → running → paused → completed | failed
    status: Mapped[str] = mapped_column(String, default="configuring")

    max_agents: Mapped[int] = mapped_column(Integer, default=4)

    # Git configuration
    repo_url: Mapped[str | None] = mapped_column(String, default=None)
    integration_branch: Mapped[str] = mapped_column(String, default="crew/integration")
    source_branch: Mapped[str] = mapped_column(String, default="main")

    # Wave tracking
    current_wave: Mapped[int] = mapped_column(Integer, default=0)
    total_waves: Mapped[int] = mapped_column(Integer, default=0)

    # Workflow tracking (groups related scheduler jobs)
    workflow_id: Mapped[uuid.UUID | None] = mapped_column(default=None)

    # Flexible config: auto_push, timeout, model, role_assignments, etc.
    config: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
