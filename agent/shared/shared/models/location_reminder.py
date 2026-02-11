"""Location reminder model — geofence-based reminders."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class LocationReminder(Base):
    __tablename__ = "location_reminders"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id"), default=None
    )

    # What to remind
    message: Mapped[str] = mapped_column(String, nullable=False)

    # Where to trigger
    place_name: Mapped[str] = mapped_column(String, nullable=False)
    place_lat: Mapped[float] = mapped_column(Float, nullable=False)
    place_lng: Mapped[float] = mapped_column(Float, nullable=False)
    radius_m: Mapped[int] = mapped_column(Integer, default=30)

    # Where to notify
    platform: Mapped[str | None] = mapped_column(String, default=None)
    platform_channel_id: Mapped[str | None] = mapped_column(String, default=None)
    platform_thread_id: Mapped[str | None] = mapped_column(String, default=None)

    # OwnTracks sync
    owntracks_rid: Mapped[str] = mapped_column(String, nullable=False)
    synced_to_device: Mapped[bool] = mapped_column(Boolean, default=False)

    # Lifecycle
    status: Mapped[str] = mapped_column(String, default="active")
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    cooldown_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
