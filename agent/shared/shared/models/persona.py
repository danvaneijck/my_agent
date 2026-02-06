"""Persona model."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class Persona(Base):
    __tablename__ = "personas"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
    system_prompt: Mapped[str] = mapped_column(Text)
    platform: Mapped[str | None] = mapped_column(default=None)
    platform_server_id: Mapped[str | None] = mapped_column(default=None)
    allowed_modules: Mapped[str] = mapped_column(
        default='["research", "file_manager", "code_executor"]'
    )  # JSON list
    default_model: Mapped[str | None] = mapped_column(default=None)
    max_tokens_per_request: Mapped[int] = mapped_column(default=4000)
    is_default: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
