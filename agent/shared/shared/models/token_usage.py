"""Token usage tracking model."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class TokenLog(Base):
    __tablename__ = "token_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id")
    )
    model: Mapped[str]
    input_tokens: Mapped[int]
    output_tokens: Mapped[int]
    cost_estimate: Mapped[float | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
