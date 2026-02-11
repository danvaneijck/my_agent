"""Geocoding — resolve place names to coordinates."""

from __future__ import annotations

import math
from dataclasses import dataclass

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models.named_place import UserNamedPlace

logger = structlog.get_logger()

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"
USER_AGENT = "AgentLocationModule/1.0"


@dataclass
class PlaceResult:
    """A geocoding candidate."""

    name: str
    lat: float
    lng: float
    address: str | None = None
    distance_m: float | None = None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance in meters between two lat/lng points."""
    R = 6_371_000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def _check_named_places(
    session: AsyncSession, user_id: str, place: str
) -> PlaceResult | None:
    """Check if the place matches a user's saved named place."""
    place_lower = place.lower().strip()
    # Strip leading articles
    for prefix in ("the ", "my "):
        if place_lower.startswith(prefix):
            place_lower = place_lower[len(prefix):]

    result = await session.execute(
        select(UserNamedPlace).where(
            UserNamedPlace.user_id == user_id,
        )
    )
    named_places = result.scalars().all()
    for np in named_places:
        if np.name.lower() == place_lower:
            return PlaceResult(
                name=np.name,
                lat=np.latitude,
                lng=np.longitude,
                address=np.address,
            )
    return None


async def _geocode_nominatim(
    query: str,
    near_lat: float | None = None,
    near_lng: float | None = None,
    limit: int = 5,
) -> list[PlaceResult]:
    """Geocode a place query using OpenStreetMap Nominatim."""
    params: dict[str, str | int] = {
        "q": query,
        "format": "json",
        "limit": limit,
        "addressdetails": 1,
    }
    # Bias results near user's location
    if near_lat is not None and near_lng is not None:
        delta = 0.05  # ~5km bias box
        params["viewbox"] = (
            f"{near_lng - delta},{near_lat + delta},"
            f"{near_lng + delta},{near_lat - delta}"
        )
        params["bounded"] = 0

    headers = {"User-Agent": USER_AGENT}

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(NOMINATIM_URL, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    results: list[PlaceResult] = []
    for item in data:
        lat = float(item["lat"])
        lng = float(item["lon"])
        dist = None
        if near_lat is not None and near_lng is not None:
            dist = haversine_m(near_lat, near_lng, lat, lng)
        results.append(
            PlaceResult(
                name=item.get("display_name", query),
                lat=lat,
                lng=lng,
                address=item.get("display_name"),
                distance_m=dist,
            )
        )

    # Sort by distance if we have a reference point
    if near_lat is not None and near_lng is not None:
        results.sort(key=lambda r: r.distance_m or float("inf"))

    return results


async def reverse_geocode(lat: float, lng: float) -> str | None:
    """Reverse geocode coordinates to a human-readable address."""
    params = {"lat": lat, "lon": lng, "format": "json"}
    headers = {"User-Agent": USER_AGENT}

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                NOMINATIM_REVERSE_URL, params=params, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("display_name")
    except Exception:
        logger.warning("reverse_geocode_failed", lat=lat, lng=lng)
        return None


async def resolve_place(
    place: str,
    user_id: str,
    session: AsyncSession,
    near_lat: float | None = None,
    near_lng: float | None = None,
) -> list[PlaceResult]:
    """Resolve a place description to coordinates.

    Strategy:
    1. Check user's named places first ("home", "work", etc.)
    2. Geocode using Nominatim, biased near user's location
    """
    # 1. Check named places
    named = await _check_named_places(session, user_id, place)
    if named:
        return [named]

    # 2. Geocode via Nominatim
    results = await _geocode_nominatim(place, near_lat, near_lng)
    return results
