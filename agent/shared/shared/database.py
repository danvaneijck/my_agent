"""Async SQLAlchemy engine and session factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from shared.config import get_settings


def create_engine(database_url: str | None = None):
    """Create an async SQLAlchemy engine."""
    url = database_url or get_settings().database_url
    return create_async_engine(
        url,
        echo=False,
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
    )


def create_session_factory(engine=None) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory."""
    if engine is None:
        engine = create_engine()
    return async_sessionmaker(engine, expire_on_commit=False)


# Default instances (lazy)
_engine = None
_session_factory = None


def get_engine():
    """Get or create the default engine."""
    global _engine
    if _engine is None:
        _engine = create_engine()
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create the default session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = create_session_factory(get_engine())
    return _session_factory
