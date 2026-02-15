"""Open-Meteo weather API client."""

from __future__ import annotations

import httpx
import structlog

from modules.weather.geocoding import geocode

logger = structlog.get_logger()

WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"

# WMO weather interpretation codes
WMO_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _weather_description(code: int) -> str:
    """Convert a WMO weather code to a human-readable description."""
    return WMO_CODES.get(code, f"Unknown ({code})")


def _unit_params(units: str) -> dict[str, str]:
    """Return Open-Meteo unit parameters based on metric/imperial preference."""
    if units == "imperial":
        return {
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
        }
    return {
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }


def _temp_unit(units: str) -> str:
    return "°F" if units == "imperial" else "°C"


def _wind_unit(units: str) -> str:
    return "mph" if units == "imperial" else "km/h"


def _precip_unit(units: str) -> str:
    return "in" if units == "imperial" else "mm"


class WeatherClient:
    """Async client for the Open-Meteo weather API."""

    async def get_coordinates(self, location: str) -> tuple[float, float, str]:
        """Resolve a location name to (lat, lng, display_name).

        Returns:
            Tuple of (latitude, longitude, display_name).

        Raises:
            RuntimeError: If the location cannot be found.
        """
        result = await geocode(location)
        if result is None:
            raise RuntimeError(f"Location not found: '{location}'")

        parts = [result.name]
        if result.admin1:
            parts.append(result.admin1)
        if result.country:
            parts.append(result.country)
        display_name = ", ".join(parts)

        return result.lat, result.lng, display_name

    async def get_current_weather(
        self, lat: float, lng: float, units: str = "metric"
    ) -> dict:
        """Fetch current weather conditions for the given coordinates."""
        params = {
            "latitude": lat,
            "longitude": lng,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,wind_speed_10m,wind_direction_10m,"
                "wind_gusts_10m,pressure_msl,cloud_cover,uv_index"
            ),
            **_unit_params(units),
        }

        data = await self._fetch(params)
        current = data["current"]

        return {
            "temperature": current["temperature_2m"],
            "temperature_unit": _temp_unit(units),
            "feels_like": current["apparent_temperature"],
            "humidity": current["relative_humidity_2m"],
            "weather_code": current["weather_code"],
            "description": _weather_description(current["weather_code"]),
            "wind_speed": current["wind_speed_10m"],
            "wind_unit": _wind_unit(units),
            "wind_direction": current["wind_direction_10m"],
            "wind_gusts": current["wind_gusts_10m"],
            "pressure_msl": current["pressure_msl"],
            "cloud_cover": current["cloud_cover"],
            "uv_index": current.get("uv_index"),
            "time": current["time"],
        }

    async def get_forecast(
        self, lat: float, lng: float, days: int = 7, units: str = "metric"
    ) -> list[dict]:
        """Fetch daily forecast for the given coordinates.

        Args:
            days: Number of forecast days (1-16). Defaults to 7.
        """
        days = max(1, min(days, 16))

        params = {
            "latitude": lat,
            "longitude": lng,
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "apparent_temperature_max,apparent_temperature_min,"
                "precipitation_sum,precipitation_probability_max,"
                "wind_speed_10m_max,wind_gusts_10m_max,uv_index_max,"
                "sunrise,sunset"
            ),
            "forecast_days": days,
            **_unit_params(units),
        }

        data = await self._fetch(params)
        daily = data["daily"]

        forecast = []
        for i in range(len(daily["time"])):
            forecast.append({
                "date": daily["time"][i],
                "weather_code": daily["weather_code"][i],
                "description": _weather_description(daily["weather_code"][i]),
                "temp_max": daily["temperature_2m_max"][i],
                "temp_min": daily["temperature_2m_min"][i],
                "temperature_unit": _temp_unit(units),
                "feels_like_max": daily["apparent_temperature_max"][i],
                "feels_like_min": daily["apparent_temperature_min"][i],
                "precipitation": daily["precipitation_sum"][i],
                "precipitation_unit": _precip_unit(units),
                "precipitation_probability": daily["precipitation_probability_max"][i],
                "wind_speed_max": daily["wind_speed_10m_max"][i],
                "wind_unit": _wind_unit(units),
                "wind_gusts_max": daily["wind_gusts_10m_max"][i],
                "uv_index_max": daily["uv_index_max"][i],
                "sunrise": daily["sunrise"][i],
                "sunset": daily["sunset"][i],
            })

        return forecast

    async def get_hourly_data(
        self, lat: float, lng: float, hours: int = 24, units: str = "metric"
    ) -> list[dict]:
        """Fetch hourly forecast data.

        Args:
            hours: Number of hours to return (1-168). Defaults to 24.
        """
        hours = max(1, min(hours, 168))

        # Open-Meteo returns hourly data in daily chunks, so we request
        # enough forecast days to cover the requested hours.
        forecast_days = min((hours // 24) + 1, 16)

        params = {
            "latitude": lat,
            "longitude": lng,
            "hourly": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "weather_code,wind_speed_10m,wind_direction_10m,"
                "precipitation_probability,precipitation,visibility,"
                "cloud_cover,uv_index"
            ),
            "forecast_days": forecast_days,
            **_unit_params(units),
        }

        data = await self._fetch(params)
        hourly = data["hourly"]

        results = []
        count = min(hours, len(hourly["time"]))
        for i in range(count):
            results.append({
                "time": hourly["time"][i],
                "temperature": hourly["temperature_2m"][i],
                "temperature_unit": _temp_unit(units),
                "feels_like": hourly["apparent_temperature"][i],
                "humidity": hourly["relative_humidity_2m"][i],
                "weather_code": hourly["weather_code"][i],
                "description": _weather_description(hourly["weather_code"][i]),
                "wind_speed": hourly["wind_speed_10m"][i],
                "wind_unit": _wind_unit(units),
                "wind_direction": hourly["wind_direction_10m"][i],
                "precipitation": hourly["precipitation"][i],
                "precipitation_unit": _precip_unit(units),
                "precipitation_probability": hourly["precipitation_probability"][i],
                "visibility": hourly["visibility"][i],
                "cloud_cover": hourly["cloud_cover"][i],
                "uv_index": hourly["uv_index"][i],
            })

        return results

    async def get_alerts(self, lat: float, lng: float) -> dict:
        """Check for severe weather conditions based on current and forecast data.

        Open-Meteo doesn't have a dedicated alerts endpoint, so we analyze
        the current and forecast data to identify severe conditions.
        """
        # Fetch current + next 2 days of hourly data for analysis
        params = {
            "latitude": lat,
            "longitude": lng,
            "current": (
                "temperature_2m,weather_code,wind_speed_10m,wind_gusts_10m"
            ),
            "hourly": (
                "temperature_2m,weather_code,wind_speed_10m,wind_gusts_10m,"
                "precipitation,precipitation_probability,visibility"
            ),
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max,"
                "uv_index_max"
            ),
            "forecast_days": 2,
            "temperature_unit": "celsius",
            "wind_speed_unit": "kmh",
            "precipitation_unit": "mm",
        }

        data = await self._fetch(params)
        alerts = []

        current = data.get("current", {})
        hourly = data.get("hourly", {})
        daily = data.get("daily", {})

        # Check current severe weather codes
        current_code = current.get("weather_code", 0)
        if current_code >= 95:
            alerts.append({
                "type": "thunderstorm",
                "severity": "warning",
                "message": f"Active thunderstorm: {_weather_description(current_code)}",
            })

        # Check for high winds (current)
        wind_gusts = current.get("wind_gusts_10m", 0) or 0
        if wind_gusts >= 90:
            alerts.append({
                "type": "wind",
                "severity": "warning",
                "message": f"Dangerous wind gusts: {wind_gusts} km/h",
            })
        elif wind_gusts >= 60:
            alerts.append({
                "type": "wind",
                "severity": "advisory",
                "message": f"Strong wind gusts: {wind_gusts} km/h",
            })

        # Check hourly data for upcoming conditions
        weather_codes = hourly.get("weather_code", [])
        precip_probs = hourly.get("precipitation_probability", [])
        temperatures = hourly.get("temperature_2m", [])
        visibilities = hourly.get("visibility", [])

        # Heavy precipitation forecast
        for i, code in enumerate(weather_codes[:48]):
            if code in (65, 67, 75, 82, 86, 99):
                time = hourly["time"][i] if i < len(hourly.get("time", [])) else "upcoming"
                alerts.append({
                    "type": "precipitation",
                    "severity": "warning",
                    "message": f"Heavy precipitation expected at {time}: {_weather_description(code)}",
                })
                break  # Report only the first occurrence

        # Extreme temperatures from daily data
        for i, temp_max in enumerate(daily.get("temperature_2m_max", [])):
            if temp_max is not None and temp_max >= 40:
                date = daily["time"][i] if i < len(daily.get("time", [])) else "upcoming"
                alerts.append({
                    "type": "heat",
                    "severity": "warning",
                    "message": f"Extreme heat on {date}: {temp_max}°C",
                })
        for i, temp_min in enumerate(daily.get("temperature_2m_min", [])):
            if temp_min is not None and temp_min <= -20:
                date = daily["time"][i] if i < len(daily.get("time", [])) else "upcoming"
                alerts.append({
                    "type": "cold",
                    "severity": "warning",
                    "message": f"Extreme cold on {date}: {temp_min}°C",
                })

        # Low visibility
        for i, vis in enumerate(visibilities[:48]):
            if vis is not None and vis < 1000:
                time = hourly["time"][i] if i < len(hourly.get("time", [])) else "upcoming"
                alerts.append({
                    "type": "visibility",
                    "severity": "advisory",
                    "message": f"Low visibility ({vis}m) expected at {time}",
                })
                break

        # High UV from daily data
        for i, uv in enumerate(daily.get("uv_index_max", [])):
            if uv is not None and uv >= 11:
                date = daily["time"][i] if i < len(daily.get("time", [])) else "upcoming"
                alerts.append({
                    "type": "uv",
                    "severity": "warning",
                    "message": f"Extreme UV index on {date}: {uv}",
                })
            elif uv is not None and uv >= 8:
                date = daily["time"][i] if i < len(daily.get("time", [])) else "upcoming"
                alerts.append({
                    "type": "uv",
                    "severity": "advisory",
                    "message": f"Very high UV index on {date}: {uv}",
                })

        return {
            "alert_count": len(alerts),
            "alerts": alerts,
        }

    async def _fetch(self, params: dict) -> dict:
        """Make a request to the Open-Meteo API."""
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(WEATHER_API_URL, params=params)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error("open_meteo_http_error", status=e.response.status_code, body=e.response.text)
            raise RuntimeError(f"Open-Meteo API error: {e.response.status_code}")
        except httpx.RequestError as e:
            logger.error("open_meteo_request_error", error=str(e))
            raise RuntimeError(f"Failed to connect to Open-Meteo API: {e}")
