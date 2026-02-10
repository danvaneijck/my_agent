"""Renpho biometrics module tool implementations."""

from __future__ import annotations

import structlog
from renpho import RenphoClient, RenphoAPIError, format_timestamp

logger = structlog.get_logger()

# Metrics to include in formatted output
KEY_METRICS = [
    ("weight", "Weight", "kg"),
    ("bmi", "BMI", ""),
    ("bodyfat", "Body Fat", "%"),
    ("water", "Body Water", "%"),
    ("muscle", "Muscle Mass", "%"),
    ("bone", "Bone Mass", "%"),
    ("bmr", "BMR", "kcal/day"),
    ("visfat", "Visceral Fat", "level"),
    ("subfat", "Subcutaneous Fat", "%"),
    ("protein", "Protein", "%"),
    ("bodyage", "Body Age", "years"),
    ("sinew", "Lean Body Mass", "kg"),
    ("fatFreeWeight", "Fat Free Weight", "kg"),
    ("heartRate", "Heart Rate", "bpm"),
    ("cardiacIndex", "Cardiac Index", ""),
    ("bodyShape", "Body Shape", ""),
]


def _format_measurement(m: dict) -> dict:
    """Extract and format relevant fields from a raw measurement."""
    result: dict = {"timestamp": format_timestamp(m.get("timeStamp"))}
    for key, label, unit in KEY_METRICS:
        val = m.get(key)
        if val is not None and val != 0:
            result[key] = {"label": label, "value": val, "unit": unit}
    return result


class RenphoBiometricsTools:
    """Tool implementations for fetching Renpho biometric data."""

    def __init__(self, email: str, password: str):
        self.email = email
        self.password = password

    def _create_client(self) -> RenphoClient:
        """Create a fresh client instance for each request."""
        return RenphoClient(self.email, self.password)

    async def get_measurements(self, limit: int = 10) -> dict:
        """Fetch recent biometric measurements."""
        try:
            client = self._create_client()
            all_measurements = client.get_all_measurements()

            measurements = all_measurements[:limit]
            formatted = [_format_measurement(m) for m in measurements]

            return {
                "count": len(formatted),
                "total_available": len(all_measurements),
                "measurements": formatted,
            }
        except RenphoAPIError as e:
            logger.error("renpho_api_error", context=e.context, code=e.code, msg=e.msg)
            raise RuntimeError(f"Renpho API error ({e.context}): {e.msg}")
        except Exception as e:
            logger.error("renpho_get_measurements_error", error=str(e))
            raise RuntimeError(f"Failed to fetch measurements: {e}")

    async def get_latest(self) -> dict:
        """Get the most recent measurement."""
        try:
            client = self._create_client()
            all_measurements = client.get_all_measurements()

            if not all_measurements:
                return {"error": "No measurements found"}

            return _format_measurement(all_measurements[0])
        except RenphoAPIError as e:
            logger.error("renpho_api_error", context=e.context, code=e.code, msg=e.msg)
            raise RuntimeError(f"Renpho API error ({e.context}): {e.msg}")
        except Exception as e:
            logger.error("renpho_get_latest_error", error=str(e))
            raise RuntimeError(f"Failed to fetch latest measurement: {e}")

    async def get_trend(self, count: int = 30) -> dict:
        """Analyse trends across recent measurements."""
        try:
            client = self._create_client()
            all_measurements = client.get_all_measurements()

            measurements = all_measurements[:count]
            if not measurements:
                return {"error": "No measurements found"}

            # Measurements are newest-first; oldest is last
            latest = measurements[0]
            oldest = measurements[-1]

            trend_metrics = []
            for key, label, unit in KEY_METRICS:
                latest_val = latest.get(key)
                oldest_val = oldest.get(key)
                if latest_val is None or oldest_val is None:
                    continue
                if latest_val == 0 and oldest_val == 0:
                    continue

                # Compute average across the window
                values = [m.get(key) for m in measurements if m.get(key) is not None and m.get(key) != 0]
                if not values:
                    continue

                avg = round(sum(values) / len(values), 2)
                change = round(latest_val - oldest_val, 2)

                trend_metrics.append({
                    "metric": label,
                    "key": key,
                    "unit": unit,
                    "current": latest_val,
                    "oldest_in_range": oldest_val,
                    "change": change,
                    "average": avg,
                    "data_points": len(values),
                })

            return {
                "period": {
                    "from": format_timestamp(oldest.get("timeStamp")),
                    "to": format_timestamp(latest.get("timeStamp")),
                    "measurement_count": len(measurements),
                },
                "trends": trend_metrics,
            }
        except RenphoAPIError as e:
            logger.error("renpho_api_error", context=e.context, code=e.code, msg=e.msg)
            raise RuntimeError(f"Renpho API error ({e.context}): {e.msg}")
        except Exception as e:
            logger.error("renpho_get_trend_error", error=str(e))
            raise RuntimeError(f"Failed to compute trends: {e}")
