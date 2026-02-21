"""Error log model for capturing tool and core errors."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class ErrorLog(Base):
    __tablename__ = "error_logs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Source classification
    service: Mapped[str] = mapped_column(String)        # "core", "research", "code_executor", etc.
    error_type: Mapped[str] = mapped_column(String)     # "tool_execution", "llm_call", "agent_loop", "module_startup", "invalid_tool"

    # What failed
    tool_name: Mapped[str | None] = mapped_column(String, default=None)
    tool_arguments: Mapped[dict | None] = mapped_column(JSON, default=None)
    error_message: Mapped[str] = mapped_column(Text)
    stack_trace: Mapped[str | None] = mapped_column(Text, default=None)

    # Context for reproduction
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), nullable=True, default=None
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("conversations.id"), nullable=True, default=None
    )

    # Lifecycle
    status: Mapped[str] = mapped_column(String, default="open")  # "open" | "dismissed" | "resolved"

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
