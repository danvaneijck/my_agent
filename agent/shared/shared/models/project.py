"""Project model for project planning and tracking."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    name: Mapped[str] = mapped_column(String)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    design_document: Mapped[str | None] = mapped_column(Text, default=None)

    # Git repository info
    repo_owner: Mapped[str | None] = mapped_column(String, default=None)
    repo_name: Mapped[str | None] = mapped_column(String, default=None)
    default_branch: Mapped[str] = mapped_column(String, default="main")
    project_branch: Mapped[str | None] = mapped_column(String, default=None)

    # Execution settings
    auto_merge: Mapped[bool] = mapped_column(Boolean, default=False)

    # Claude Code planning task tracking
    planning_task_id: Mapped[str | None] = mapped_column(String, default=None)

    # Workflow tracking for automated sequential phase execution
    workflow_id: Mapped[str | None] = mapped_column(String, default=None)

    # Lifecycle: planning → active → paused → completed → archived
    status: Mapped[str] = mapped_column(String, default="planning")

    # Plan application state: idle → applying → applied | failed
    plan_apply_status: Mapped[str] = mapped_column(String, default="idle")
    plan_apply_error: Mapped[str | None] = mapped_column(Text, default=None)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_project_name"),
    )
