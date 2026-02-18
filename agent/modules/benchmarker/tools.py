"""Benchmarker module tool implementations."""

from __future__ import annotations

import httpx
import structlog

logger = structlog.get_logger()


class BenchmarkerClient:
    """Client for the Benchmarker IoT monitoring platform Agent API."""

    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_body: dict | None = None,
    ) -> dict:
        """Make an authenticated request and unwrap the response envelope."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.api_url}{path}"

        # Strip None values from params
        if params:
            params = {k: v for k, v in params.items() if v is not None}

        async with httpx.AsyncClient(timeout=30.0, headers=headers) as client:
            if method == "GET":
                resp = await client.get(url, params=params)
            elif method == "POST":
                resp = await client.post(url, params=params, json=json_body)
            else:
                raise RuntimeError(f"Unsupported HTTP method: {method}")

            resp.raise_for_status()

        envelope = resp.json()
        if not envelope.get("ok"):
            error = envelope.get("error", {})
            message = error.get("message", "Unknown API error") if isinstance(error, dict) else str(error)
            raise RuntimeError(f"Benchmarker API error: {message}")

        return envelope.get("data", {})

    async def device_lookup(self, serial_number: str) -> dict:
        """Look up a device by serial number."""
        return await self._request(
            "GET",
            "/api/agent/v1/device/lookup",
            params={"serial_number": serial_number},
        )

    async def send_downlink(self, serial_number: str, cli_command: str) -> dict:
        """Send a CLI command to a device."""
        return await self._request(
            "POST",
            "/api/agent/v1/device/send-downlink",
            json_body={"serial_number": serial_number, "cli_command": cli_command},
        )

    async def organisation_summary(
        self, name: str | None = None, short_name: str | None = None
    ) -> dict:
        """Get an overview of an organisation."""
        if not name and not short_name:
            raise RuntimeError("At least one of 'name' or 'short_name' is required")
        return await self._request(
            "GET",
            "/api/agent/v1/organisation/summary",
            params={"name": name, "short_name": short_name},
        )

    async def site_overview(
        self,
        site_id: int | None = None,
        name: str | None = None,
        organisation: str | None = None,
    ) -> dict:
        """Get details about a specific site."""
        if site_id is None and name is None:
            raise RuntimeError("At least one of 'site_id' or 'name' is required")
        return await self._request(
            "GET",
            "/api/agent/v1/site/overview",
            params={"site_id": site_id, "name": name, "organisation": organisation},
        )

    async def silent_devices(
        self,
        hours: int | None = None,
        organisation: str | None = None,
        site_id: int | None = None,
        device_type: str | None = None,
    ) -> dict:
        """Find devices that haven't reported within a given time window."""
        return await self._request(
            "GET",
            "/api/agent/v1/health/silent-devices",
            params={
                "hours": hours,
                "organisation": organisation,
                "site_id": site_id,
                "device_type": device_type,
            },
        )

    async def low_battery_devices(
        self,
        threshold: int | None = None,
        organisation: str | None = None,
        site_id: int | None = None,
    ) -> dict:
        """Find devices with low battery."""
        return await self._request(
            "GET",
            "/api/agent/v1/health/low-battery",
            params={
                "threshold": threshold,
                "organisation": organisation,
                "site_id": site_id,
            },
        )

    async def device_issues(
        self, serial_number: str, include_closed: bool | None = None
    ) -> dict:
        """Get open issues for a device."""
        return await self._request(
            "GET",
            "/api/agent/v1/issues/by-device",
            params={
                "serial_number": serial_number,
                "include_closed": include_closed,
            },
        )

    async def org_issues_summary(self, organisation: str) -> dict:
        """Get issue statistics for an organisation."""
        return await self._request(
            "GET",
            "/api/agent/v1/issues/org-summary",
            params={"organisation": organisation},
        )

    async def provision_organisation(
        self,
        organisations: dict,
        dry_run: bool | None = None,
        no_geocode: bool | None = None,
    ) -> dict:
        """Provision new organisations and sites."""
        return await self._request(
            "POST",
            "/api/agent/v1/actions/provision-organisation",
            params={"dry_run": dry_run, "no_geocode": no_geocode},
            json_body=organisations,
        )
