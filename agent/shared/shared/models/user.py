"""User and platform link models."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shared.models.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    permission_level: Mapped[str]  # owner, admin, user, guest
    token_budget_monthly: Mapped[int | None] = mapped_column(default=None)
    tokens_used_this_month: Mapped[int] = mapped_column(default=0)
    budget_reset_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc)
    )

    platform_links: Mapped[list[UserPlatformLink]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserPlatformLink(Base):
    __tablename__ = "user_platform_links"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    platform: Mapped[str]  # discord, telegram, slack
    platform_user_id: Mapped[str]
    platform_username: Mapped[str | None] = mapped_column(default=None)

    user: Mapped[User] = relationship(back_populates="platform_links")

    __table_args__ = (
        UniqueConstraint("platform", "platform_user_id", name="uq_platform_user"),
    )
