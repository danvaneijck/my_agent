"""Notification schemas for proactive messages via Redis pub/sub."""

from __future__ import annotations

from pydantic import BaseModel


class Notification(BaseModel):
    """A proactive message to send to a user on a specific platform channel."""

    platform: str  # "discord" | "telegram" | "slack"
    platform_channel_id: str  # where to send the message
    platform_thread_id: str | None = None  # optional thread
    content: str  # the message text
    user_id: str | None = None  # internal user UUID (for logging)
    job_id: str | None = None  # scheduler job ID that triggered this
