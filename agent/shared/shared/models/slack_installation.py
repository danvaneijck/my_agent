"""Slack workspace installation model for multi-workspace OAuth."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from shared.models.base import Base


class SlackInstallation(Base):
    __tablename__ = "slack_installations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    client_id: Mapped[str] = mapped_column(String(64))
    app_id: Mapped[str] = mapped_column(String(64))

    enterprise_id: Mapped[str | None] = mapped_column(String(64), default=None)
    enterprise_name: Mapped[str | None] = mapped_column(String(200), default=None)
    team_id: Mapped[str] = mapped_column(String(64))
    team_name: Mapped[str | None] = mapped_column(String(200), default=None)

    bot_token: Mapped[str] = mapped_column(Text)
    bot_id: Mapped[str | None] = mapped_column(String(64), default=None)
    bot_user_id: Mapped[str | None] = mapped_column(String(64), default=None)
    bot_scopes: Mapped[str | None] = mapped_column(Text, default=None)

    installed_by_user_id: Mapped[str | None] = mapped_column(String(64), default=None)
    is_enterprise_install: Mapped[bool] = mapped_column(default=False)

    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("client_id", "team_id", name="uq_slack_installation_client_team"),
        Index("ix_slack_installations_team_id", "team_id"),
    )
