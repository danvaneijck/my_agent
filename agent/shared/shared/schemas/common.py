"""Common schemas used across services."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Standard health check response."""

    status: str = "ok"
