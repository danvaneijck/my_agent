"""Geocoding — resolve location names to coordinates using Open-Meteo Geocoding API."""

from __future__ import annotations

from dataclasses import dataclass

import httpx
import structlog

logger = structlog.get_logger()

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


@dataclass
class GeoResult:
    """A geocoding result."""

    name: str
    lat: float
    lng: float
    country: str | None = None
    admin1: str | None = None  # state/province


async def geocode(location: str) -> GeoResult | None:
    """Resolve a location name to coordinates using Open-Meteo's geocoding API.

    Returns the top result, or None if not found.
    """
    params = {"name": location, "count": 1, "language": "en", "format": "json"}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(GEOCODING_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        results = data.get("results")
        if not results:
            return None

        item = results[0]
        return GeoResult(
            name=item.get("name", location),
            lat=item["latitude"],
            lng=item["longitude"],
            country=item.get("country"),
            admin1=item.get("admin1"),
        )
    except Exception as e:
        logger.error("geocoding_failed", location=location, error=str(e))
        raise RuntimeError(f"Geocoding failed for '{location}': {e}")
