"""Tests for the CacheManager."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from modules.weather.cache import CacheManager, _cache_key, DEFAULT_TTLS


def test_cache_key():
    assert _cache_key("London", "current") == "weather:london:current"
    assert _cache_key("  New York  ", "forecast") == "weather:new york:forecast"


def test_default_ttls():
    assert DEFAULT_TTLS["current"] == 600
    assert DEFAULT_TTLS["forecast"] == 3600
    assert DEFAULT_TTLS["hourly"] == 1800
    assert DEFAULT_TTLS["alerts"] == 600
    assert DEFAULT_TTLS["geocode"] == 86400


# ---------------------------------------------------------------------------
# CacheManager with no Redis (graceful fallback)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_no_redis():
    cache = CacheManager(redis_client=None)
    result = await cache.get("London", "current")
    assert result is None


@pytest.mark.asyncio
async def test_set_no_redis():
    cache = CacheManager(redis_client=None)
    # Should not raise
    await cache.set("London", "current", {"temp": 10})


@pytest.mark.asyncio
async def test_delete_no_redis():
    cache = CacheManager(redis_client=None)
    # Should not raise
    await cache.delete("London", "current")


# ---------------------------------------------------------------------------
# CacheManager with mock Redis
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_cache_hit():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = '{"temperature": 10.5}'

    cache = CacheManager(redis_client=mock_redis)
    result = await cache.get("London", "current")

    assert result == {"temperature": 10.5}
    mock_redis.get.assert_called_once_with("weather:london:current")


@pytest.mark.asyncio
async def test_get_cache_miss():
    mock_redis = AsyncMock()
    mock_redis.get.return_value = None

    cache = CacheManager(redis_client=mock_redis)
    result = await cache.get("London", "current")

    assert result is None


@pytest.mark.asyncio
async def test_get_redis_error():
    mock_redis = AsyncMock()
    mock_redis.get.side_effect = ConnectionError("Redis down")

    cache = CacheManager(redis_client=mock_redis)
    result = await cache.get("London", "current")

    # Should gracefully return None
    assert result is None


@pytest.mark.asyncio
async def test_set_with_default_ttl():
    mock_redis = AsyncMock()

    cache = CacheManager(redis_client=mock_redis)
    await cache.set("London", "current", {"temp": 10})

    mock_redis.set.assert_called_once_with(
        "weather:london:current", '{"temp": 10}', ex=600
    )


@pytest.mark.asyncio
async def test_set_with_custom_ttl():
    mock_redis = AsyncMock()

    cache = CacheManager(redis_client=mock_redis)
    await cache.set("London", "current", {"temp": 10}, ttl=120)

    mock_redis.set.assert_called_once_with(
        "weather:london:current", '{"temp": 10}', ex=120
    )


@pytest.mark.asyncio
async def test_set_redis_error():
    mock_redis = AsyncMock()
    mock_redis.set.side_effect = ConnectionError("Redis down")

    cache = CacheManager(redis_client=mock_redis)
    # Should not raise
    await cache.set("London", "current", {"temp": 10})


@pytest.mark.asyncio
async def test_delete_success():
    mock_redis = AsyncMock()

    cache = CacheManager(redis_client=mock_redis)
    await cache.delete("London", "current")

    mock_redis.delete.assert_called_once_with("weather:london:current")


@pytest.mark.asyncio
async def test_delete_redis_error():
    mock_redis = AsyncMock()
    mock_redis.delete.side_effect = ConnectionError("Redis down")

    cache = CacheManager(redis_client=mock_redis)
    # Should not raise
    await cache.delete("London", "current")
