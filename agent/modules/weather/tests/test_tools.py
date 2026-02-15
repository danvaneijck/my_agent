"""Tests for WeatherTools — verifies caching and delegation to WeatherClient."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from modules.weather.cache import CacheManager
from modules.weather.tools import WeatherTools


@pytest.fixture
def mock_cache():
    cache = CacheManager(redis_client=None)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    return cache


@pytest.fixture
def tools(mock_cache):
    return WeatherTools(cache=mock_cache)


# ---------------------------------------------------------------------------
# weather_current
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weather_current(tools, mock_cache):
    with patch.object(tools.client, "get_coordinates", return_value=(51.5, -0.1, "London, England, UK")):
        with patch.object(tools.client, "get_current_weather", return_value={"temperature": 8.5, "description": "Overcast"}):
            result = await tools.weather_current("London", "metric")

    assert result["location"] == "London, England, UK"
    assert result["temperature"] == 8.5
    mock_cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_weather_current_cache_hit(tools, mock_cache):
    mock_cache.get.return_value = {
        "location": "London, England, UK",
        "temperature": 8.5,
        "_units": "metric",
    }

    result = await tools.weather_current("London", "metric")

    assert result["location"] == "London, England, UK"
    assert result["temperature"] == 8.5
    assert "_units" not in result


@pytest.mark.asyncio
async def test_weather_current_cache_miss_wrong_units(tools, mock_cache):
    # Cache has metric but we want imperial
    mock_cache.get.return_value = {
        "location": "London, England, UK",
        "temperature": 8.5,
        "_units": "metric",
    }

    with patch.object(tools.client, "get_coordinates", return_value=(51.5, -0.1, "London, England, UK")):
        with patch.object(tools.client, "get_current_weather", return_value={"temperature": 47.3}):
            result = await tools.weather_current("London", "imperial")

    assert result["temperature"] == 47.3


# ---------------------------------------------------------------------------
# weather_forecast
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weather_forecast(tools, mock_cache):
    forecast_data = [
        {"date": "2026-02-15", "temp_max": 10.0},
        {"date": "2026-02-16", "temp_max": 8.0},
    ]

    with patch.object(tools.client, "get_coordinates", return_value=(51.5, -0.1, "London, England, UK")):
        with patch.object(tools.client, "get_forecast", return_value=forecast_data):
            result = await tools.weather_forecast("London", days=2)

    assert result["days"] == 2
    assert len(result["forecast"]) == 2


@pytest.mark.asyncio
async def test_weather_forecast_cache_hit(tools, mock_cache):
    mock_cache.get.return_value = {
        "location": "London, England, UK",
        "days": 7,
        "forecast": [{"date": f"2026-02-{15+i}"} for i in range(7)],
        "_units": "metric",
        "_days": 7,
    }

    result = await tools.weather_forecast("London", days=3)

    # Should trim cached 7-day to 3-day
    assert len(result["forecast"]) == 3


# ---------------------------------------------------------------------------
# weather_hourly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weather_hourly(tools, mock_cache):
    hourly_data = [{"time": f"2026-02-15T{i:02d}:00", "temperature": 6.0 + i * 0.5} for i in range(6)]

    with patch.object(tools.client, "get_coordinates", return_value=(51.5, -0.1, "London, England, UK")):
        with patch.object(tools.client, "get_hourly_data", return_value=hourly_data):
            result = await tools.weather_hourly("London", hours=6)

    assert result["hours"] == 6


@pytest.mark.asyncio
async def test_weather_hourly_cache_hit(tools, mock_cache):
    mock_cache.get.return_value = {
        "location": "London, England, UK",
        "hours": 24,
        "hourly": [{"time": f"T{i:02d}:00"} for i in range(24)],
        "_units": "metric",
        "_hours": 24,
    }

    result = await tools.weather_hourly("London", hours=6)

    assert len(result["hourly"]) == 6


# ---------------------------------------------------------------------------
# weather_alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_weather_alerts(tools, mock_cache):
    with patch.object(tools.client, "get_coordinates", return_value=(51.5, -0.1, "London, England, UK")):
        with patch.object(tools.client, "get_alerts", return_value={"alert_count": 0, "alerts": []}):
            result = await tools.weather_alerts("London")

    assert result["alert_count"] == 0
    assert result["location"] == "London, England, UK"


@pytest.mark.asyncio
async def test_weather_alerts_cache_hit(tools, mock_cache):
    mock_cache.get.return_value = {
        "location": "London, England, UK",
        "alert_count": 1,
        "alerts": [{"type": "wind", "severity": "advisory"}],
    }

    result = await tools.weather_alerts("London")

    assert result["alert_count"] == 1


# ---------------------------------------------------------------------------
# _normalize_units
# ---------------------------------------------------------------------------


def test_normalize_units():
    assert WeatherTools._normalize_units("metric") == "metric"
    assert WeatherTools._normalize_units("imperial") == "imperial"
    assert WeatherTools._normalize_units("fahrenheit") == "imperial"
    assert WeatherTools._normalize_units("f") == "imperial"
    assert WeatherTools._normalize_units("celsius") == "metric"
    assert WeatherTools._normalize_units("anything") == "metric"
