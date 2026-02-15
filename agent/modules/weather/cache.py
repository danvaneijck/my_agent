"""Redis caching layer for weather data."""

from __future__ import annotations

import json

import structlog

logger = structlog.get_logger()

# Default TTLs in seconds
DEFAULT_TTLS: dict[str, int] = {
    "current": 600,     # 10 minutes
    "forecast": 3600,   # 1 hour
    "hourly": 1800,     # 30 minutes
    "alerts": 600,      # 10 minutes
    "geocode": 86400,   # 24 hours
}


def _cache_key(location: str, data_type: str) -> str:
    """Build a cache key."""
    return f"weather:{location.lower().strip()}:{data_type}"


class CacheManager:
    """Redis-backed cache with graceful fallback when Redis is unavailable."""

    def __init__(self, redis_client=None):
        self._redis = redis_client

    async def get(self, location: str, data_type: str) -> dict | list | None:
        """Retrieve cached data, or None if miss/unavailable."""
        if self._redis is None:
            return None

        key = _cache_key(location, data_type)
        try:
            raw = await self._redis.get(key)
            if raw is None:
                return None
            logger.debug("cache_hit", key=key)
            return json.loads(raw)
        except Exception as e:
            logger.warning("cache_get_error", key=key, error=str(e))
            return None

    async def set(
        self, location: str, data_type: str, value: dict | list, ttl: int | None = None
    ) -> None:
        """Store data with a TTL. Silently fails if Redis is unavailable."""
        if self._redis is None:
            return

        key = _cache_key(location, data_type)
        if ttl is None:
            ttl = DEFAULT_TTLS.get(data_type, 600)

        try:
            await self._redis.set(key, json.dumps(value), ex=ttl)
            logger.debug("cache_set", key=key, ttl=ttl)
        except Exception as e:
            logger.warning("cache_set_error", key=key, error=str(e))

    async def delete(self, location: str, data_type: str) -> None:
        """Remove a cached entry. Silently fails if Redis is unavailable."""
        if self._redis is None:
            return

        key = _cache_key(location, data_type)
        try:
            await self._redis.delete(key)
            logger.debug("cache_delete", key=key)
        except Exception as e:
            logger.warning("cache_delete_error", key=key, error=str(e))
