"""Weather module tool implementations."""

from __future__ import annotations

import structlog

from modules.weather.cache import CacheManager
from modules.weather.client import WeatherClient

logger = structlog.get_logger()


class WeatherTools:
    """Tool implementations for weather data retrieval."""

    def __init__(self, cache: CacheManager):
        self.client = WeatherClient()
        self.cache = cache

    async def weather_current(
        self, location: str, units: str = "metric"
    ) -> dict:
        """Get current weather for a location."""
        units = self._normalize_units(units)

        # Check cache
        cached = await self.cache.get(location, "current")
        if cached and cached.get("_units") == units:
            cached.pop("_units", None)
            return cached

        lat, lng, display_name = await self.client.get_coordinates(location)
        current = await self.client.get_current_weather(lat, lng, units)
        result = {
            "location": display_name,
            "latitude": lat,
            "longitude": lng,
            **current,
        }

        # Cache with units tag for invalidation
        await self.cache.set(location, "current", {**result, "_units": units})
        return result

    async def weather_forecast(
        self, location: str, days: int = 7, units: str = "metric"
    ) -> dict:
        """Get daily forecast for a location."""
        units = self._normalize_units(units)
        days = max(1, min(days, 16))

        cached = await self.cache.get(location, "forecast")
        if cached and cached.get("_units") == units and cached.get("_days", 0) >= days:
            cached.pop("_units", None)
            cached.pop("_days", None)
            cached["forecast"] = cached["forecast"][:days]
            return cached

        lat, lng, display_name = await self.client.get_coordinates(location)
        forecast = await self.client.get_forecast(lat, lng, days, units)
        result = {
            "location": display_name,
            "latitude": lat,
            "longitude": lng,
            "days": len(forecast),
            "forecast": forecast,
        }

        await self.cache.set(location, "forecast", {**result, "_units": units, "_days": days})
        return result

    async def weather_hourly(
        self, location: str, hours: int = 24, units: str = "metric"
    ) -> dict:
        """Get hourly forecast for a location."""
        units = self._normalize_units(units)
        hours = max(1, min(hours, 168))

        cached = await self.cache.get(location, "hourly")
        if cached and cached.get("_units") == units and cached.get("_hours", 0) >= hours:
            cached.pop("_units", None)
            cached.pop("_hours", None)
            cached["hourly"] = cached["hourly"][:hours]
            return cached

        lat, lng, display_name = await self.client.get_coordinates(location)
        hourly = await self.client.get_hourly_data(lat, lng, hours, units)
        result = {
            "location": display_name,
            "latitude": lat,
            "longitude": lng,
            "hours": len(hourly),
            "hourly": hourly,
        }

        await self.cache.set(location, "hourly", {**result, "_units": units, "_hours": hours})
        return result

    async def weather_alerts(self, location: str) -> dict:
        """Check for severe weather alerts at a location."""
        cached = await self.cache.get(location, "alerts")
        if cached:
            return cached

        lat, lng, display_name = await self.client.get_coordinates(location)
        alerts = await self.client.get_alerts(lat, lng)
        result = {
            "location": display_name,
            "latitude": lat,
            "longitude": lng,
            **alerts,
        }

        await self.cache.set(location, "alerts", result)
        return result

    @staticmethod
    def _normalize_units(units: str) -> str:
        """Normalize unit string to 'metric' or 'imperial'."""
        if units.lower() in ("imperial", "fahrenheit", "f"):
            return "imperial"
        return "metric"
