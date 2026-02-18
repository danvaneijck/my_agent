"""HTTP client for core orchestrator /message endpoint."""

from __future__ import annotations

import httpx
import structlog

from shared.auth import get_service_auth_headers
from shared.config import get_settings

logger = structlog.get_logger()


async def send_message(
    content: str,
    platform_user_id: str,
    platform_channel_id: str,
    platform_username: str = "Portal User",
    attachments: list[dict] | None = None,
) -> dict:
    """POST an IncomingMessage to core and return the AgentResponse dict.

    This mirrors the pattern used by Discord/Telegram/Slack bots.
    """
    settings = get_settings()
    payload = {
        "platform": "web",
        "platform_user_id": platform_user_id,
        "platform_username": platform_username,
        "platform_channel_id": platform_channel_id,
        "content": content,
        "attachments": attachments or [],
    }

    async with httpx.AsyncClient(timeout=180.0, headers=get_service_auth_headers()) as client:
        resp = await client.post(
            f"{settings.orchestrator_url}/message",
            json=payload,
        )
        resp.raise_for_status()

    return resp.json()
