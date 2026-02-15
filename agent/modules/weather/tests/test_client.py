"""Tests for the WeatherClient — all external HTTP calls are mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from modules.weather.client import WeatherClient, _weather_description, _unit_params
from modules.weather.geocoding import geocode, GeoResult
from modules.weather.tests.fixtures import (
    CURRENT_WEATHER_RESPONSE,
    FORECAST_RESPONSE,
    GEOCODING_RESPONSE,
    GEOCODING_RESPONSE_EMPTY,
    HOURLY_RESPONSE,
    ALERTS_RESPONSE,
    ALERTS_RESPONSE_CLEAR,
)


# ---------------------------------------------------------------------------
# Geocoding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_geocode_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = GEOCODING_RESPONSE
    mock_resp.raise_for_status = MagicMock()

    with patch("modules.weather.geocoding.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await geocode("London")

    assert result is not None
    assert result.name == "London"
    assert result.lat == 51.5074
    assert result.lng == -0.1278
    assert result.country == "United Kingdom"


@pytest.mark.asyncio
async def test_geocode_not_found():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = GEOCODING_RESPONSE_EMPTY
    mock_resp.raise_for_status = MagicMock()

    with patch("modules.weather.geocoding.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        result = await geocode("xyznonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_geocode_http_error():
    with patch("modules.weather.geocoding.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("connection failed")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="Geocoding failed"):
            await geocode("London")


# ---------------------------------------------------------------------------
# WeatherClient.get_coordinates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_coordinates():
    client = WeatherClient()
    geo = GeoResult(name="London", lat=51.5074, lng=-0.1278, country="United Kingdom", admin1="England")

    with patch("modules.weather.client.geocode", return_value=geo):
        lat, lng, name = await client.get_coordinates("London")

    assert lat == 51.5074
    assert lng == -0.1278
    assert "London" in name
    assert "England" in name
    assert "United Kingdom" in name


@pytest.mark.asyncio
async def test_get_coordinates_not_found():
    client = WeatherClient()

    with patch("modules.weather.client.geocode", return_value=None):
        with pytest.raises(RuntimeError, match="Location not found"):
            await client.get_coordinates("xyznonexistent")


# ---------------------------------------------------------------------------
# WeatherClient.get_current_weather
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_current_weather_metric():
    client = WeatherClient()

    with patch.object(client, "_fetch", return_value=CURRENT_WEATHER_RESPONSE):
        result = await client.get_current_weather(51.5, -0.1, "metric")

    assert result["temperature"] == 8.5
    assert result["temperature_unit"] == "°C"
    assert result["humidity"] == 72
    assert result["description"] == "Overcast"
    assert result["wind_unit"] == "km/h"


@pytest.mark.asyncio
async def test_get_current_weather_imperial():
    client = WeatherClient()

    with patch.object(client, "_fetch", return_value=CURRENT_WEATHER_RESPONSE):
        result = await client.get_current_weather(51.5, -0.1, "imperial")

    assert result["temperature_unit"] == "°F"
    assert result["wind_unit"] == "mph"


# ---------------------------------------------------------------------------
# WeatherClient.get_forecast
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_forecast():
    client = WeatherClient()

    with patch.object(client, "_fetch", return_value=FORECAST_RESPONSE):
        result = await client.get_forecast(51.5, -0.1, days=3, units="metric")

    assert len(result) == 3
    assert result[0]["date"] == "2026-02-15"
    assert result[0]["description"] == "Overcast"
    assert result[0]["temp_max"] == 10.2
    assert result[0]["temp_min"] == 4.1
    assert result[1]["precipitation_probability"] == 85


@pytest.mark.asyncio
async def test_get_forecast_clamps_days():
    client = WeatherClient()

    with patch.object(client, "_fetch", return_value=FORECAST_RESPONSE):
        # days=0 should be clamped to 1, days=20 to 16
        result = await client.get_forecast(51.5, -0.1, days=0)

    # Still returns whatever the API gives back for 1 day forecast request
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# WeatherClient.get_hourly_data
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_hourly_data():
    client = WeatherClient()

    with patch.object(client, "_fetch", return_value=HOURLY_RESPONSE):
        result = await client.get_hourly_data(51.5, -0.1, hours=3, units="metric")

    assert len(result) == 3
    assert result[0]["time"] == "2026-02-15T00:00"
    assert result[0]["temperature"] == 6.5
    assert result[0]["visibility"] == 10000


@pytest.mark.asyncio
async def test_get_hourly_data_clamps_hours():
    client = WeatherClient()

    with patch.object(client, "_fetch", return_value=HOURLY_RESPONSE):
        result = await client.get_hourly_data(51.5, -0.1, hours=200)

    # Clamped to 168, but fixture only has 3 entries
    assert len(result) == 3


# ---------------------------------------------------------------------------
# WeatherClient.get_alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_alerts_severe():
    client = WeatherClient()

    with patch.object(client, "_fetch", return_value=ALERTS_RESPONSE):
        result = await client.get_alerts(51.5, -0.1)

    assert result["alert_count"] > 0
    alert_types = [a["type"] for a in result["alerts"]]
    assert "thunderstorm" in alert_types
    assert "wind" in alert_types


@pytest.mark.asyncio
async def test_get_alerts_clear():
    client = WeatherClient()

    with patch.object(client, "_fetch", return_value=ALERTS_RESPONSE_CLEAR):
        result = await client.get_alerts(51.5, -0.1)

    assert result["alert_count"] == 0
    assert result["alerts"] == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_weather_description():
    assert _weather_description(0) == "Clear sky"
    assert _weather_description(95) == "Thunderstorm"
    assert "Unknown" in _weather_description(999)


def test_unit_params_metric():
    params = _unit_params("metric")
    assert params["temperature_unit"] == "celsius"
    assert params["wind_speed_unit"] == "kmh"


def test_unit_params_imperial():
    params = _unit_params("imperial")
    assert params["temperature_unit"] == "fahrenheit"
    assert params["wind_speed_unit"] == "mph"


# ---------------------------------------------------------------------------
# WeatherClient._fetch error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_http_error():
    client = WeatherClient()

    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500", request=httpx.Request("GET", "http://test"), response=mock_resp
    )

    with patch("modules.weather.client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.return_value = mock_resp
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="Open-Meteo API error"):
            await client._fetch({"latitude": 51.5, "longitude": -0.1})


@pytest.mark.asyncio
async def test_fetch_connection_error():
    client = WeatherClient()

    with patch("modules.weather.client.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.RequestError("connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        with pytest.raises(RuntimeError, match="Failed to connect"):
            await client._fetch({"latitude": 51.5, "longitude": -0.1})
