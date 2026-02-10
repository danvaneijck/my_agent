"""Scheduled job model for background task monitoring."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id"), default=None
    )

    # Where to send the notification
    platform: Mapped[str]
    platform_channel_id: Mapped[str]
    platform_thread_id: Mapped[str | None] = mapped_column(default=None)

    # What to check
    job_type: Mapped[str]  # "poll_module" | "delay" | "poll_url"
    check_config: Mapped[dict] = mapped_column(JSON)

    # Schedule
    interval_seconds: Mapped[int] = mapped_column(Integer, default=30)
    max_attempts: Mapped[int] = mapped_column(Integer, default=120)
    attempts: Mapped[int] = mapped_column(Integer, default=0)

    # What to say when done
    on_success_message: Mapped[str] = mapped_column(Text)
    on_failure_message: Mapped[str | None] = mapped_column(Text, default=None)

    # Lifecycle
    status: Mapped[str] = mapped_column(default="active")  # active | completed | failed | cancelled
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
