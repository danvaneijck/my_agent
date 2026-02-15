#!/usr/bin/env python3
"""End-to-end tests for the weather module.

Requires the weather service to be running (e.g. via docker compose).
Default: http://localhost:8001

Usage:
    # Start the service first:
    cd agent/modules/weather && docker compose up --build -d

    # Run E2E tests:
    python3 test_e2e.py                           # default localhost:8001
    python3 test_e2e.py http://localhost:8001      # explicit URL

    # Cleanup:
    docker compose down
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"

passed = 0
failed = 0


def _post(path: str, body: dict) -> dict:
    """POST JSON and return parsed response."""
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _get(path: str) -> dict:
    """GET and return parsed response."""
    req = urllib.request.Request(f"{BASE_URL}{path}")
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def test(name: str, fn):
    global passed, failed
    try:
        fn()
        print(f"  PASS  {name}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  {name}: {e}")
        failed += 1


# ---------------------------------------------------------------------------
# Wait for service readiness
# ---------------------------------------------------------------------------

def wait_for_service(max_wait: int = 60):
    """Poll /health until the service is ready."""
    print(f"Waiting for service at {BASE_URL} ...")
    deadline = time.time() + max_wait
    while time.time() < deadline:
        try:
            data = _get("/health")
            if data.get("status") == "ok":
                print("  Service is ready.\n")
                return
        except Exception:
            pass
        time.sleep(2)
    print("  ERROR: Service did not become ready in time.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_health():
    data = _get("/health")
    assert data == {"status": "ok"}, f"Unexpected: {data}"


def test_manifest():
    data = _get("/manifest")
    assert data["module_name"] == "weather", f"module_name: {data.get('module_name')}"
    names = [t["name"] for t in data["tools"]]
    for expected in ["weather.weather_current", "weather.weather_forecast",
                     "weather.weather_hourly", "weather.weather_alerts"]:
        assert expected in names, f"Missing tool: {expected}"
    assert len(data["tools"]) == 4


def test_weather_current():
    data = _post("/execute", {
        "tool_name": "weather.weather_current",
        "arguments": {"location": "London", "units": "metric"},
    })
    assert data["success"] is True, f"Error: {data.get('error')}"
    result = data["result"]
    assert "temperature" in result, f"Missing temperature: {result}"
    assert "description" in result
    assert result["temperature_unit"] == "°C"
    assert "London" in result["location"]


def test_weather_current_imperial():
    data = _post("/execute", {
        "tool_name": "weather.weather_current",
        "arguments": {"location": "New York", "units": "imperial"},
    })
    assert data["success"] is True, f"Error: {data.get('error')}"
    result = data["result"]
    assert result["temperature_unit"] == "°F"
    assert result["wind_unit"] == "mph"


def test_weather_forecast():
    data = _post("/execute", {
        "tool_name": "weather.weather_forecast",
        "arguments": {"location": "Tokyo", "days": 3},
    })
    assert data["success"] is True, f"Error: {data.get('error')}"
    result = data["result"]
    assert result["days"] == 3, f"Expected 3 days, got {result['days']}"
    assert len(result["forecast"]) == 3
    day = result["forecast"][0]
    assert "temp_max" in day
    assert "temp_min" in day
    assert "description" in day


def test_weather_hourly():
    data = _post("/execute", {
        "tool_name": "weather.weather_hourly",
        "arguments": {"location": "Berlin", "hours": 6},
    })
    assert data["success"] is True, f"Error: {data.get('error')}"
    result = data["result"]
    assert result["hours"] == 6, f"Expected 6 hours, got {result['hours']}"
    assert len(result["hourly"]) == 6
    hour = result["hourly"][0]
    assert "temperature" in hour
    assert "wind_speed" in hour


def test_weather_alerts():
    data = _post("/execute", {
        "tool_name": "weather.weather_alerts",
        "arguments": {"location": "Sydney"},
    })
    assert data["success"] is True, f"Error: {data.get('error')}"
    result = data["result"]
    assert "alert_count" in result
    assert isinstance(result["alerts"], list)
    assert "Sydney" in result["location"]


def test_invalid_location():
    data = _post("/execute", {
        "tool_name": "weather.weather_current",
        "arguments": {"location": "xyzzy_nonexistent_99999"},
    })
    assert data["success"] is False, "Expected failure for invalid location"
    assert data["error"] is not None


def test_unknown_tool():
    data = _post("/execute", {
        "tool_name": "weather.nonexistent_tool",
        "arguments": {},
    })
    assert data["success"] is False
    assert "Unknown tool" in data["error"]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    wait_for_service()

    print("Running E2E tests:")
    test("health", test_health)
    test("manifest", test_manifest)
    test("weather_current (metric)", test_weather_current)
    test("weather_current (imperial)", test_weather_current_imperial)
    test("weather_forecast", test_weather_forecast)
    test("weather_hourly", test_weather_hourly)
    test("weather_alerts", test_weather_alerts)
    test("invalid location", test_invalid_location)
    test("unknown tool", test_unknown_tool)

    print(f"\n{'='*40}")
    print(f"  {passed} passed, {failed} failed")
    print(f"{'='*40}")

    sys.exit(1 if failed else 0)
