"""MyFitnessPal module tool implementations."""

from __future__ import annotations

import asyncio
import http.cookiejar
from datetime import date, timedelta

import structlog

logger = structlog.get_logger()


def _today() -> date:
    return date.today()


def _days_ago(n: int) -> date:
    return date.today() - timedelta(days=n)


def _parse_date(s: str) -> date:
    """Parse a YYYY-MM-DD string into a date object."""
    parts = s.split("-")
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def _build_cookiejar(cookie_string: str) -> http.cookiejar.CookieJar:
    """Build a CookieJar from a raw cookie header string.

    The cookie_string should be in the format sent by browsers:
    'name1=value1; name2=value2; ...'
    """
    jar = http.cookiejar.CookieJar()
    for pair in cookie_string.split(";"):
        pair = pair.strip()
        if "=" not in pair:
            continue
        name, value = pair.split("=", 1)
        cookie = http.cookiejar.Cookie(
            version=0,
            name=name.strip(),
            value=value.strip(),
            port=None,
            port_specified=False,
            domain=".myfitnesspal.com",
            domain_specified=True,
            domain_initial_dot=True,
            path="/",
            path_specified=True,
            secure=True,
            expires=None,
            discard=True,
            comment=None,
            comment_url=None,
            rest={},
        )
        jar.set_cookie(cookie)
    return jar


class MyFitnessPalTools:
    """Tool implementations for fetching MyFitnessPal data."""

    def __init__(self, username: str, cookie_string: str):
        self.username = username
        self.cookie_string = cookie_string
        self._client = None

    def _ensure_client(self):
        """Get an authenticated MyFitnessPal client."""
        if self._client is not None:
            return self._client

        import myfitnesspal

        if not self.cookie_string:
            raise RuntimeError(
                "MyFitnessPal credentials not configured. "
                "Set MFP_USERNAME and MFP_COOKIE_STRING in .env. "
                "Extract cookies from your browser while logged into myfitnesspal.com."
            )

        jar = _build_cookiejar(self.cookie_string)
        self._client = myfitnesspal.Client(cookiejar=jar)
        logger.info("myfitnesspal_client_ready", username=self.username)
        return self._client

    def _reset_client(self) -> None:
        """Clear cached client so next call re-authenticates."""
        self._client = None

    async def get_day(self, date: str | None = None) -> dict:
        """Fetch the food diary for a specific date."""
        target = _parse_date(date) if date else _today()

        try:
            client = await asyncio.to_thread(self._ensure_client)
            day = await asyncio.to_thread(client.get_date, target)
        except Exception as exc:
            if "cookie" in str(exc).lower() or "auth" in str(exc).lower():
                self._reset_client()
                client = await asyncio.to_thread(self._ensure_client)
                day = await asyncio.to_thread(client.get_date, target)
            else:
                raise

        meals = []
        totals: dict[str, float] = {}

        for meal in day.meals:
            entries = []
            for entry in meal.entries:
                nutrition = {}
                if hasattr(entry, "nutrition_information"):
                    nutrition = {
                        k: v for k, v in entry.nutrition_information.items()
                    }
                elif hasattr(entry, "totals"):
                    nutrition = {k: v for k, v in entry.totals.items()}
                entries.append({
                    "name": entry.name if hasattr(entry, "name") else str(entry),
                    "nutrition": nutrition,
                })
            meal_totals = {}
            if hasattr(meal, "totals"):
                meal_totals = {k: v for k, v in meal.totals.items()}
            meals.append({
                "name": meal.name if hasattr(meal, "name") else str(meal),
                "entries": entries,
                "totals": meal_totals,
            })

        # Day-level totals
        if hasattr(day, "totals"):
            totals = {k: v for k, v in day.totals.items()}

        # Day-level goals
        goals = {}
        if hasattr(day, "goals"):
            goals = {k: v for k, v in day.goals.items()}

        result: dict = {
            "date": target.isoformat(),
            "meals": meals,
            "totals": totals,
            "goals": goals,
            "complete": getattr(day, "complete", None),
        }

        # Water intake
        try:
            water = getattr(day, "water", None)
            if water is not None:
                result["water"] = water
        except Exception:
            pass

        return result

    async def get_measurements(
        self,
        measurement: str = "Weight",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Fetch body measurements over a date range."""
        lower = _parse_date(start_date) if start_date else _days_ago(30)
        upper = _parse_date(end_date) if end_date else _today()

        try:
            client = await asyncio.to_thread(self._ensure_client)
            data = await asyncio.to_thread(
                client.get_measurements, measurement, lower, upper
            )
        except Exception as exc:
            if "cookie" in str(exc).lower() or "auth" in str(exc).lower():
                self._reset_client()
                client = await asyncio.to_thread(self._ensure_client)
                data = await asyncio.to_thread(
                    client.get_measurements, measurement, lower, upper
                )
            else:
                raise

        if not data:
            return {
                "measurement": measurement,
                "start_date": lower.isoformat(),
                "end_date": upper.isoformat(),
                "entries": [],
            }

        entries = [
            {"date": d.isoformat(), "value": v}
            for d, v in sorted(data.items())
        ]

        values = [e["value"] for e in entries]
        return {
            "measurement": measurement,
            "start_date": lower.isoformat(),
            "end_date": upper.isoformat(),
            "count": len(entries),
            "latest": entries[-1]["value"] if entries else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "average": round(sum(values) / len(values), 2) if values else None,
            "entries": entries,
        }

    async def get_report(
        self,
        report_name: str = "Net Calories",
        report_category: str = "Nutrition",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Fetch a nutrition or fitness report over a date range."""
        lower = _parse_date(start_date) if start_date else _days_ago(7)
        upper = _parse_date(end_date) if end_date else _today()

        try:
            client = await asyncio.to_thread(self._ensure_client)
            data = await asyncio.to_thread(
                client.get_report, report_name, report_category, lower, upper
            )
        except Exception as exc:
            if "cookie" in str(exc).lower() or "auth" in str(exc).lower():
                self._reset_client()
                client = await asyncio.to_thread(self._ensure_client)
                data = await asyncio.to_thread(
                    client.get_report, report_name, report_category, lower, upper
                )
            else:
                raise

        if not data:
            return {
                "report": report_name,
                "category": report_category,
                "start_date": lower.isoformat(),
                "end_date": upper.isoformat(),
                "entries": [],
            }

        entries = [
            {"date": d.isoformat(), "value": v}
            for d, v in sorted(data.items())
        ]

        values = [e["value"] for e in entries if e["value"] is not None]
        return {
            "report": report_name,
            "category": report_category,
            "start_date": lower.isoformat(),
            "end_date": upper.isoformat(),
            "count": len(entries),
            "average": round(sum(values) / len(values), 2) if values else None,
            "total": round(sum(values), 2) if values else None,
            "min": min(values) if values else None,
            "max": max(values) if values else None,
            "entries": entries,
        }

    async def search_food(self, query: str) -> dict:
        """Search the MyFitnessPal food database."""
        try:
            client = await asyncio.to_thread(self._ensure_client)
            results = await asyncio.to_thread(client.get_food_search_results, query)
        except Exception as exc:
            if "cookie" in str(exc).lower() or "auth" in str(exc).lower():
                self._reset_client()
                client = await asyncio.to_thread(self._ensure_client)
                results = await asyncio.to_thread(
                    client.get_food_search_results, query
                )
            else:
                raise

        if not results:
            return {"query": query, "count": 0, "results": []}

        items = []
        for item in results[:15]:
            food = {
                "name": getattr(item, "name", str(item)),
                "brand": getattr(item, "brand", None),
                "mfp_id": getattr(item, "mfp_id", None),
            }
            if hasattr(item, "servings"):
                servings = []
                for serving in item.servings:
                    s = {
                        "description": getattr(serving, "description", str(serving)),
                        "nutrition": {},
                    }
                    if hasattr(serving, "nutrition_information"):
                        s["nutrition"] = {
                            k: v for k, v in serving.nutrition_information.items()
                        }
                    servings.append(s)
                food["servings"] = servings
            items.append(food)

        return {
            "query": query,
            "count": len(items),
            "results": items,
        }
