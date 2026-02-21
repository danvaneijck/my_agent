"""ScheduledWorkflow model — first-class grouping for multi-step scheduler jobs."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class ScheduledWorkflow(Base):
    __tablename__ = "scheduled_workflows"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))

    name: Mapped[str]
    description: Mapped[str | None] = mapped_column(Text, default=None)

    # Notification routing (mirrors ScheduledJob — used for workflow-level notifications)
    platform: Mapped[str]
    platform_channel_id: Mapped[str]
    platform_thread_id: Mapped[str | None] = mapped_column(default=None)
    platform_server_id: Mapped[str | None] = mapped_column(default=None)

    # Lifecycle: "active" | "completed" | "failed" | "cancelled"
    status: Mapped[str] = mapped_column(default="active")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
