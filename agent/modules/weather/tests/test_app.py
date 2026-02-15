"""Tests for weather module FastAPI endpoints."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from modules.weather.main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    """Create an async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_manifest(client):
    resp = await client.get("/manifest")
    assert resp.status_code == 200
    data = resp.json()
    assert data["module_name"] == "weather"
    tool_names = [t["name"] for t in data["tools"]]
    assert "weather.weather_current" in tool_names
    assert "weather.weather_forecast" in tool_names
    assert "weather.weather_hourly" in tool_names
    assert "weather.weather_alerts" in tool_names


# ---------------------------------------------------------------------------
# Execute — weather_current
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_weather_current(client):
    mock_result = {
        "location": "London, England, United Kingdom",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "temperature": 8.5,
        "temperature_unit": "°C",
        "description": "Overcast",
    }

    with patch("modules.weather.main.tools") as mock_tools:
        mock_tools.weather_current = AsyncMock(return_value=mock_result)

        resp = await client.post(
            "/execute",
            json={
                "tool_name": "weather.weather_current",
                "arguments": {"location": "London"},
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["result"]["location"] == "London, England, United Kingdom"
    assert data["result"]["temperature"] == 8.5


# ---------------------------------------------------------------------------
# Execute — weather_forecast
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_weather_forecast(client):
    mock_result = {
        "location": "London, England, United Kingdom",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "days": 3,
        "forecast": [
            {"date": "2026-02-15", "temp_max": 10.2, "temp_min": 4.1},
            {"date": "2026-02-16", "temp_max": 8.5, "temp_min": 3.2},
            {"date": "2026-02-17", "temp_max": 11.0, "temp_min": 5.5},
        ],
    }

    with patch("modules.weather.main.tools") as mock_tools:
        mock_tools.weather_forecast = AsyncMock(return_value=mock_result)

        resp = await client.post(
            "/execute",
            json={
                "tool_name": "weather.weather_forecast",
                "arguments": {"location": "London", "days": 3},
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["result"]["days"] == 3
    assert len(data["result"]["forecast"]) == 3


# ---------------------------------------------------------------------------
# Execute — weather_hourly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_weather_hourly(client):
    mock_result = {
        "location": "London, England, United Kingdom",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "hours": 3,
        "hourly": [
            {"time": "2026-02-15T00:00", "temperature": 6.5},
            {"time": "2026-02-15T01:00", "temperature": 6.2},
            {"time": "2026-02-15T02:00", "temperature": 5.8},
        ],
    }

    with patch("modules.weather.main.tools") as mock_tools:
        mock_tools.weather_hourly = AsyncMock(return_value=mock_result)

        resp = await client.post(
            "/execute",
            json={
                "tool_name": "weather.weather_hourly",
                "arguments": {"location": "London", "hours": 3},
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["result"]["hours"] == 3


# ---------------------------------------------------------------------------
# Execute — weather_alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_weather_alerts(client):
    mock_result = {
        "location": "London, England, United Kingdom",
        "latitude": 51.5074,
        "longitude": -0.1278,
        "alert_count": 1,
        "alerts": [
            {"type": "wind", "severity": "advisory", "message": "Strong wind gusts: 65 km/h"}
        ],
    }

    with patch("modules.weather.main.tools") as mock_tools:
        mock_tools.weather_alerts = AsyncMock(return_value=mock_result)

        resp = await client.post(
            "/execute",
            json={
                "tool_name": "weather.weather_alerts",
                "arguments": {"location": "London"},
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["result"]["alert_count"] == 1


# ---------------------------------------------------------------------------
# Execute — unknown tool
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_unknown_tool(client):
    with patch("modules.weather.main.tools") as mock_tools:
        # tools is not None but tool name is invalid
        mock_tools.__bool__ = lambda self: True

        resp = await client.post(
            "/execute",
            json={
                "tool_name": "weather.nonexistent",
                "arguments": {},
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "Unknown tool" in data["error"]


# ---------------------------------------------------------------------------
# Execute — tool raises exception
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_tool_error(client):
    with patch("modules.weather.main.tools") as mock_tools:
        mock_tools.weather_current = AsyncMock(
            side_effect=RuntimeError("Location not found: 'xyznonexistent'")
        )

        resp = await client.post(
            "/execute",
            json={
                "tool_name": "weather.weather_current",
                "arguments": {"location": "xyznonexistent"},
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "Location not found" in data["error"]


# ---------------------------------------------------------------------------
# Execute — module not ready
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_module_not_ready(client):
    with patch("modules.weather.main.tools", None):
        resp = await client.post(
            "/execute",
            json={
                "tool_name": "weather.weather_current",
                "arguments": {"location": "London"},
            },
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is False
    assert "not ready" in data["error"]
