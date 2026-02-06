"""Normalized message schemas for cross-platform communication."""

from __future__ import annotations

from pydantic import BaseModel


class IncomingMessage(BaseModel):
    """Normalized incoming message from any platform."""

    platform: str  # discord, telegram, slack
    platform_user_id: str
    platform_username: str | None = None
    platform_channel_id: str
    platform_thread_id: str | None = None
    platform_server_id: str | None = None
    content: str
    attachments: list[str] = []  # URLs


class AgentResponse(BaseModel):
    """Response from the orchestrator back to the platform."""

    content: str
    files: list[dict] = []  # [{filename, url}]
    error: str | None = None
