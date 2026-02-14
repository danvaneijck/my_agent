"""Garmin Connect module tool implementations."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta
from pathlib import Path

import structlog
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

logger = structlog.get_logger()

TOKENSTORE_PATH = Path("/app/.garmin_tokens")


def _today() -> str:
    return date.today().isoformat()


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _seconds_to_hm(seconds: int | float | None) -> str | None:
    """Convert seconds to 'Xh Ym' string."""
    if seconds is None:
        return None
    total_min = int(seconds) // 60
    hours = total_min // 60
    minutes = total_min % 60
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _safe_get(data: dict | None, *keys, default=None):
    """Safely traverse nested dicts."""
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
    return current


class GarminTools:
    """Tool implementations for fetching Garmin Connect data."""

    def __init__(self, email: str, password: str, tokenstore_path: Path | None = None):
        self.email = email
        self.password = password
        self._tokenstore_path = tokenstore_path or TOKENSTORE_PATH
        self._client: Garmin | None = None

    def _ensure_client(self) -> Garmin:
        """Get an authenticated Garmin client, reusing tokens when possible."""
        if self._client is not None:
            return self._client

        # Try loading saved tokens first
        if self._tokenstore_path.exists():
            try:
                client = Garmin()
                client.login(str(self._tokenstore_path))
                self._client = client
                logger.info("garmin_auth_from_tokens")
                return client
            except Exception:
                logger.info("garmin_saved_tokens_expired")

        # Fall back to email/password login
        if not self.email or not self.password:
            raise RuntimeError(
                "Garmin credentials not configured. Add credentials in Portal Settings or set GARMIN_EMAIL and GARMIN_PASSWORD in .env"
            )

        client = Garmin(email=self.email, password=self.password)
        client.login()
        self._tokenstore_path.mkdir(parents=True, exist_ok=True)
        client.garth.dump(str(self._tokenstore_path))
        self._client = client
        logger.info("garmin_auth_from_credentials")
        return client

    def _reset_client(self) -> None:
        """Clear cached client so next call re-authenticates."""
        self._client = None

    async def get_daily_summary(self, date: str | None = None) -> dict:
        """Fetch daily activity summary."""
        cdate = date or _today()
        try:
            client = await asyncio.to_thread(self._ensure_client)
            stats = await asyncio.to_thread(client.get_user_summary, cdate)
        except GarminConnectAuthenticationError:
            self._reset_client()
            client = await asyncio.to_thread(self._ensure_client)
            stats = await asyncio.to_thread(client.get_user_summary, cdate)

        if not stats:
            return {"date": cdate, "error": "No data available for this date"}

        return {
            "date": cdate,
            "steps": stats.get("totalSteps"),
            "distance_km": round(stats.get("totalDistanceMeters", 0) / 1000, 2) if stats.get("totalDistanceMeters") else None,
            "calories_total": stats.get("totalKilocalories"),
            "calories_active": stats.get("activeKilocalories"),
            "floors_climbed": stats.get("floorsAscended"),
            "active_minutes": stats.get("activeSeconds", 0) // 60 if stats.get("activeSeconds") else None,
            "highly_active_minutes": stats.get("highlyActiveSeconds", 0) // 60 if stats.get("highlyActiveSeconds") else None,
            "sedentary_minutes": stats.get("sedentarySeconds", 0) // 60 if stats.get("sedentarySeconds") else None,
            "resting_heart_rate": stats.get("restingHeartRate"),
            "min_heart_rate": stats.get("minHeartRate"),
            "max_heart_rate": stats.get("maxHeartRate"),
            "average_stress": stats.get("averageStressLevel"),
            "steps_goal": stats.get("dailyStepGoal"),
        }

    async def get_heart_rate(self, date: str | None = None) -> dict:
        """Fetch heart rate data for a day."""
        cdate = date or _today()
        try:
            client = await asyncio.to_thread(self._ensure_client)
            hr = await asyncio.to_thread(client.get_heart_rates, cdate)
        except GarminConnectAuthenticationError:
            self._reset_client()
            client = await asyncio.to_thread(self._ensure_client)
            hr = await asyncio.to_thread(client.get_heart_rates, cdate)

        if not hr:
            return {"date": cdate, "error": "No heart rate data available"}

        result: dict = {
            "date": cdate,
            "resting_heart_rate": hr.get("restingHeartRate"),
            "max_heart_rate": hr.get("maxHeartRate"),
            "min_heart_rate": hr.get("minHeartRate"),
        }

        # Extract HR zone summaries if available
        zones = hr.get("heartRateZones")
        if zones:
            result["zones"] = [
                {
                    "zone": z.get("zoneName") or z.get("zone"),
                    "low_bpm": z.get("zoneLowBoundary"),
                    "high_bpm": z.get("zoneHighBoundary"),
                    "minutes": z.get("secsInZone", 0) // 60 if z.get("secsInZone") else 0,
                }
                for z in zones
            ]

        return result

    async def get_sleep(self, date: str | None = None) -> dict:
        """Fetch sleep data for a night."""
        cdate = date or _today()
        try:
            client = await asyncio.to_thread(self._ensure_client)
            sleep = await asyncio.to_thread(client.get_sleep_data, cdate)
        except GarminConnectAuthenticationError:
            self._reset_client()
            client = await asyncio.to_thread(self._ensure_client)
            sleep = await asyncio.to_thread(client.get_sleep_data, cdate)

        if not sleep:
            return {"date": cdate, "error": "No sleep data available"}

        daily = sleep.get("dailySleepDTO", {})

        result: dict = {
            "date": cdate,
            "sleep_score": daily.get("sleepScores", {}).get("overall", {}).get("value")
                if isinstance(daily.get("sleepScores"), dict) else None,
            "total_sleep": _seconds_to_hm(daily.get("sleepTimeSeconds")),
            "deep_sleep": _seconds_to_hm(daily.get("deepSleepSeconds")),
            "light_sleep": _seconds_to_hm(daily.get("lightSleepSeconds")),
            "rem_sleep": _seconds_to_hm(daily.get("remSleepSeconds")),
            "awake_time": _seconds_to_hm(daily.get("awakeSleepSeconds")),
            "average_spo2": daily.get("averageSpO2Value"),
            "average_respiration": daily.get("averageRespirationValue"),
        }

        return result

    async def get_body_composition(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> dict:
        """Fetch body composition data over a date range."""
        end = end_date or _today()
        start = start_date or _days_ago(30)
        try:
            client = await asyncio.to_thread(self._ensure_client)
            body = await asyncio.to_thread(client.get_body_composition, start, end)
        except GarminConnectAuthenticationError:
            self._reset_client()
            client = await asyncio.to_thread(self._ensure_client)
            body = await asyncio.to_thread(client.get_body_composition, start, end)

        if not body:
            return {"start_date": start, "end_date": end, "error": "No body composition data available"}

        # Extract the weight entries
        weight_entries = body.get("dateWeightList", [])
        formatted_entries = []
        for entry in weight_entries:
            formatted_entries.append({
                "date": entry.get("calendarDate"),
                "weight_kg": round(entry.get("weight", 0) / 1000, 2) if entry.get("weight") else None,
                "bmi": entry.get("bmi"),
                "body_fat_pct": entry.get("bodyFat"),
                "muscle_mass_kg": round(entry.get("muscleMass", 0) / 1000, 2) if entry.get("muscleMass") else None,
                "bone_mass_kg": round(entry.get("boneMass", 0) / 1000, 2) if entry.get("boneMass") else None,
                "body_water_pct": entry.get("bodyWater"),
            })

        # Overall stats
        stats = body.get("totalAverage", {}) or {}
        return {
            "start_date": start,
            "end_date": end,
            "entries": formatted_entries,
            "averages": {
                "weight_kg": round(stats.get("weight", 0) / 1000, 2) if stats.get("weight") else None,
                "bmi": stats.get("bmi"),
                "body_fat_pct": stats.get("bodyFat"),
                "muscle_mass_kg": round(stats.get("muscleMass", 0) / 1000, 2) if stats.get("muscleMass") else None,
                "bone_mass_kg": round(stats.get("boneMass", 0) / 1000, 2) if stats.get("boneMass") else None,
                "body_water_pct": stats.get("bodyWater"),
            },
        }

    async def get_activities(
        self, limit: int = 10, activity_type: str | None = None
    ) -> dict:
        """Fetch recent activities."""
        try:
            client = await asyncio.to_thread(self._ensure_client)
            activities = await asyncio.to_thread(
                client.get_activities, 0, limit, activity_type
            )
        except GarminConnectAuthenticationError:
            self._reset_client()
            client = await asyncio.to_thread(self._ensure_client)
            activities = await asyncio.to_thread(
                client.get_activities, 0, limit, activity_type
            )

        if not activities:
            return {"count": 0, "activities": []}

        formatted = []
        for act in activities:
            formatted.append({
                "name": act.get("activityName"),
                "type": act.get("activityType", {}).get("typeKey") if isinstance(act.get("activityType"), dict) else None,
                "date": act.get("startTimeLocal"),
                "duration": _seconds_to_hm(act.get("duration")),
                "distance_km": round(act.get("distance", 0) / 1000, 2) if act.get("distance") else None,
                "calories": act.get("calories"),
                "avg_heart_rate": act.get("averageHR"),
                "max_heart_rate": act.get("maxHR"),
                "avg_speed_kmh": round(act.get("averageSpeed", 0) * 3.6, 2) if act.get("averageSpeed") else None,
                "elevation_gain_m": act.get("elevationGain"),
                "steps": act.get("steps"),
            })

        return {"count": len(formatted), "activities": formatted}

    async def get_stress(self, date: str | None = None) -> dict:
        """Fetch stress data for a day."""
        cdate = date or _today()
        try:
            client = await asyncio.to_thread(self._ensure_client)
            stress = await asyncio.to_thread(client.get_stress_data, cdate)
        except GarminConnectAuthenticationError:
            self._reset_client()
            client = await asyncio.to_thread(self._ensure_client)
            stress = await asyncio.to_thread(client.get_stress_data, cdate)

        if not stress:
            return {"date": cdate, "error": "No stress data available"}

        return {
            "date": cdate,
            "overall_level": stress.get("overallStressLevel"),
            "rest_minutes": stress.get("restStressDuration", 0) // 60 if stress.get("restStressDuration") else None,
            "low_minutes": stress.get("lowStressDuration", 0) // 60 if stress.get("lowStressDuration") else None,
            "medium_minutes": stress.get("mediumStressDuration", 0) // 60 if stress.get("mediumStressDuration") else None,
            "high_minutes": stress.get("highStressDuration", 0) // 60 if stress.get("highStressDuration") else None,
            "max_stress": stress.get("maxStressLevel"),
            "avg_stress": stress.get("avgStressLevel"),
        }

    async def get_steps(
        self, start_date: str | None = None, end_date: str | None = None
    ) -> dict:
        """Fetch daily step counts over a date range."""
        end = end_date or _today()
        start = start_date or _days_ago(7)
        try:
            client = await asyncio.to_thread(self._ensure_client)
            steps = await asyncio.to_thread(client.get_daily_steps, start, end)
        except GarminConnectAuthenticationError:
            self._reset_client()
            client = await asyncio.to_thread(self._ensure_client)
            steps = await asyncio.to_thread(client.get_daily_steps, start, end)

        if not steps:
            return {"start_date": start, "end_date": end, "days": []}

        days = []
        for entry in steps:
            days.append({
                "date": entry.get("calendarDate"),
                "steps": entry.get("totalSteps"),
                "goal": entry.get("stepGoal"),
                "distance_km": round(entry.get("totalDistance", 0) / 100000, 2) if entry.get("totalDistance") else None,
            })

        total = sum(d.get("steps") or 0 for d in days)
        avg = total // len(days) if days else 0

        return {
            "start_date": start,
            "end_date": end,
            "total_steps": total,
            "daily_average": avg,
            "days": days,
        }
