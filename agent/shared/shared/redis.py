"""Redis connection helper."""

from __future__ import annotations

import redis.asyncio as redis

from shared.config import get_settings

_redis_client: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    """Get or create a Redis client."""
    global _redis_client
    if _redis_client is None:
        settings = get_settings()
        _redis_client = redis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


async def close_redis() -> None:
    """Close the Redis connection."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None
