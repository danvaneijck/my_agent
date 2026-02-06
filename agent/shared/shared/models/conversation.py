"""Conversation and message models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    persona_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("personas.id"), default=None
    )
    platform: Mapped[str]
    platform_channel_id: Mapped[str]
    platform_thread_id: Mapped[str | None] = mapped_column(default=None)
    started_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    last_active_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    is_summarized: Mapped[bool] = mapped_column(default=False)

    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id")
    )
    role: Mapped[str]  # user, assistant, system, tool_call, tool_result
    content: Mapped[str] = mapped_column(Text)  # JSON string for tool calls/results
    token_count: Mapped[int | None] = mapped_column(default=None)
    model_used: Mapped[str | None] = mapped_column(default=None)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
