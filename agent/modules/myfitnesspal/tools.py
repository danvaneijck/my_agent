"""MyFitnessPal module tool implementations."""

from __future__ import annotations

import asyncio
import http.cookiejar
from datetime import date, timedelta

import structlog

from modules.myfitnesspal.auth import (
    clear_cached_cookies,
    get_cookiejar,
)

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

    Fallback for when Selenium auth is not used. The cookie_string
    should be in the format: 'name1=value1; name2=value2; ...'
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
    """Tool implementations for fetching MyFitnessPal data.

    Auth priority:
    1. MFP_USERNAME + MFP_PASSWORD → Selenium headless login, cookies cached to disk
    2. MFP_COOKIE_STRING → manual browser cookie string (fallback)
    """

    def __init__(self, username: str, password: str, cookie_string: str):
        self.username = username
        self.password = password
        self.cookie_string = cookie_string
        self._client = None

    def _ensure_client(self):
        """Get an authenticated MyFitnessPal client (synchronous)."""
        if self._client is not None:
            return self._client

        import myfitnesspal

        # Primary: cookie string (fast, no Selenium/Cloudflare issues)
        if self.cookie_string:
            jar = _build_cookiejar(self.cookie_string)
            self._client = myfitnesspal.Client(cookiejar=jar)
            logger.info("myfitnesspal_client_ready", auth="cookie_string")
            return self._client

        # Fallback: Selenium-based auth (may be blocked by Cloudflare)
        if self.username and self.password:
            try:
                jar = get_cookiejar(self.username, self.password)
                self._client = myfitnesspal.Client(cookiejar=jar)
                logger.info("myfitnesspal_client_ready", auth="selenium", username=self.username)
                return self._client
            except Exception as exc:
                logger.error("mfp_selenium_auth_failed", error=str(exc))
                raise RuntimeError(
                    f"Selenium login failed (likely Cloudflare): {exc}. "
                    "Set MFP_COOKIE_STRING in .env instead — "
                    "copy the Cookie header from your browser's DevTools "
                    "on any myfitnesspal.com page."
                ) from exc

        raise RuntimeError(
            "MyFitnessPal credentials not configured. "
            "Set MFP_COOKIE_STRING in .env (recommended) — copy the Cookie header "
            "from your browser's DevTools on any myfitnesspal.com page. "
            "Alternatively set MFP_USERNAME + MFP_PASSWORD (may be blocked by Cloudflare)."
        )

    def _reset_client(self) -> None:
        """Clear cached client and cookies so next call re-authenticates."""
        self._client = None
        # If using Selenium auth, also clear cached cookies to force fresh login
        if self.username and self.password:
            clear_cached_cookies()

    async def _call_with_retry(self, fn, *args, **kwargs):
        """Call a sync function via to_thread, retrying once on auth failure."""
        try:
            client = await asyncio.to_thread(self._ensure_client)
            return await asyncio.to_thread(fn, client, *args, **kwargs)
        except Exception as exc:
            err = str(exc).lower()
            if "cookie" in err or "auth" in err or "401" in err or "403" in err:
                logger.warning("mfp_auth_retry", error=str(exc))
                self._reset_client()
                client = await asyncio.to_thread(self._ensure_client)
                return await asyncio.to_thread(fn, client, *args, **kwargs)
            raise

    async def get_day(self, date: str | None = None) -> dict:
        """Fetch the food diary for a specific date."""
        target = _parse_date(date) if date else _today()

        day = await self._call_with_retry(lambda c, d: c.get_date(d), target)

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

        if hasattr(day, "totals"):
            totals = {k: v for k, v in day.totals.items()}

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

        data = await self._call_with_retry(
            lambda c, m, lo, hi: c.get_measurements(m, lo, hi),
            measurement, lower, upper,
        )

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

        data = await self._call_with_retry(
            lambda c, rn, rc, lo, hi: c.get_report(rn, rc, lo, hi),
            report_name, report_category, lower, upper,
        )

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
        results = await self._call_with_retry(
            lambda c, q: c.get_food_search_results(q), query
        )

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
