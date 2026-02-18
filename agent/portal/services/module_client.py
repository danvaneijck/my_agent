"""HTTP client for calling module /execute endpoints directly."""

from __future__ import annotations

import httpx
import structlog

from shared.auth import get_service_auth_headers
from shared.config import get_settings

logger = structlog.get_logger()


async def call_tool(
    module: str,
    tool_name: str,
    arguments: dict | None = None,
    user_id: str | None = None,
    timeout: float = 30.0,
) -> dict:
    """Call a module tool via POST /execute and return the ToolResult dict.

    Raises ``httpx.HTTPStatusError`` on non-2xx responses and
    ``RuntimeError`` if the tool reports failure.
    """
    settings = get_settings()
    base_url = settings.module_services.get(module)
    if not base_url:
        raise RuntimeError(f"Unknown module: {module}")

    payload = {
        "tool_name": tool_name,
        "arguments": arguments or {},
    }
    if user_id:
        payload["user_id"] = user_id

    headers = get_service_auth_headers()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{base_url}/execute", json=payload, headers=headers)
        resp.raise_for_status()

    result = resp.json()
    if not result.get("success"):
        error = result.get("error", "Unknown error")
        raise RuntimeError(f"Tool {tool_name} failed: {error}")
    return result


async def check_module_health(module: str) -> dict:
    """GET /health for a module. Returns {status, module, error?}."""
    settings = get_settings()
    base_url = settings.module_services.get(module)
    if not base_url:
        return {"module": module, "status": "unknown", "error": "not configured"}
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/health")
            resp.raise_for_status()
        return {"module": module, "status": "ok"}
    except Exception as e:
        return {"module": module, "status": "error", "error": str(e)}
