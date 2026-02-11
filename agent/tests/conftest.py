"""Shared test fixtures for the agent test suite.

Provides mock database sessions, Redis clients, and factory helpers
so module tests can run without Docker infrastructure.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.models.conversation import Conversation
from shared.models.location_reminder import LocationReminder
from shared.models.user import User
from shared.models.user_location import UserLocation


# ---------------------------------------------------------------------------
# Database mocks
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_db_session():
    """Mock async SQLAlchemy session.

    Supports the common patterns used in tool code:
        session.execute(stmt) -> result
        session.add(obj)
        session.commit()
        session.refresh(obj)
    """
    session = AsyncMock()
    # Default: execute returns a result with no rows
    default_result = MagicMock()
    default_result.scalar_one_or_none.return_value = None
    default_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=default_result)
    return session


@pytest.fixture
def mock_session_factory(mock_db_session):
    """Mock async session factory compatible with ``async with factory() as session:``.

    The tools use ``async with self.session_factory() as session:`` which
    requires the factory to return an async context manager.
    """

    @asynccontextmanager
    async def _session_ctx():
        yield mock_db_session

    factory = MagicMock(side_effect=lambda: _session_ctx())
    return factory


# ---------------------------------------------------------------------------
# Redis mock
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_redis():
    """Mock async Redis client with common operations."""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    redis.publish = AsyncMock()
    return redis


# ---------------------------------------------------------------------------
# Model factories
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_user_id():
    """Return a stable UUID string for test user."""
    return str(uuid.uuid4())


@pytest.fixture
def make_user():
    """Factory for creating User instances."""

    def _make(
        user_id: uuid.UUID | None = None,
        permission_level: str = "user",
    ) -> User:
        return User(
            id=user_id or uuid.uuid4(),
            permission_level=permission_level,
            tokens_used_this_month=0,
            created_at=datetime.now(timezone.utc),
        )

    return _make


@pytest.fixture
def make_conversation():
    """Factory for creating Conversation instances."""

    def _make(
        user_id: uuid.UUID | None = None,
        platform: str = "discord",
        channel_id: str = "123456789",
        thread_id: str | None = None,
    ) -> Conversation:
        return Conversation(
            id=uuid.uuid4(),
            user_id=user_id or uuid.uuid4(),
            platform=platform,
            platform_channel_id=channel_id,
            platform_thread_id=thread_id,
            started_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
            is_summarized=False,
        )

    return _make


@pytest.fixture
def make_location_reminder():
    """Factory for creating LocationReminder instances."""

    def _make(
        user_id: uuid.UUID | None = None,
        message: str = "Test reminder",
        place_name: str = "Test Place",
        place_lat: float = -41.28,
        place_lng: float = 174.77,
        radius_m: int = 150,
        platform: str | None = "discord",
        platform_channel_id: str | None = "123456789",
        platform_thread_id: str | None = None,
        status: str = "active",
        owntracks_rid: str | None = None,
    ) -> LocationReminder:
        return LocationReminder(
            id=uuid.uuid4(),
            user_id=user_id or uuid.uuid4(),
            message=message,
            place_name=place_name,
            place_lat=place_lat,
            place_lng=place_lng,
            radius_m=radius_m,
            platform=platform,
            platform_channel_id=platform_channel_id,
            platform_thread_id=platform_thread_id,
            owntracks_rid=owntracks_rid or str(uuid.uuid4())[:8],
            status=status,
            cooldown_until=None,
            expires_at=None,
            created_at=datetime.now(timezone.utc),
        )

    return _make


@pytest.fixture
def make_user_location():
    """Factory for creating UserLocation instances."""

    def _make(
        user_id: uuid.UUID | None = None,
        latitude: float = -41.28,
        longitude: float = 174.77,
        updated_at: datetime | None = None,
    ) -> UserLocation:
        now = datetime.now(timezone.utc)
        return UserLocation(
            user_id=user_id or uuid.uuid4(),
            latitude=latitude,
            longitude=longitude,
            source="owntracks",
            updated_at=updated_at or now,
            created_at=now,
        )

    return _make


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_execute_side_effect(*results):
    """Create an execute side_effect that returns different results per call.

    Usage::

        session.execute = AsyncMock(
            side_effect=make_execute_side_effect(result1, result2)
        )

    Each result should be a MagicMock with the appropriate return values
    (e.g. scalar_one_or_none, scalars().all()).
    """
    call_idx = 0

    async def _side_effect(stmt, *args, **kwargs):
        nonlocal call_idx
        if call_idx < len(results):
            r = results[call_idx]
            call_idx += 1
            return r
        # Fallback: return empty result
        fallback = MagicMock()
        fallback.scalar_one_or_none.return_value = None
        fallback.scalars.return_value.all.return_value = []
        return fallback

    return _side_effect
