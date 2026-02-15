"""Normalized message schemas for cross-platform communication."""

from __future__ import annotations

from pydantic import BaseModel


class ToolCallSummary(BaseModel):
    """Summary of a single tool call execution."""

    name: str
    success: bool
    tool_use_id: str


class ToolCallsMetadata(BaseModel):
    """Metadata about tool calls made during an agent response."""

    total_count: int
    unique_tools: int
    tools_sequence: list[ToolCallSummary]


class IncomingMessage(BaseModel):
    """Normalized incoming message from any platform."""

    platform: str  # discord, telegram, slack
    platform_user_id: str
    platform_username: str | None = None
    platform_channel_id: str
    platform_thread_id: str | None = None
    platform_server_id: str | None = None
    content: str
    attachments: list[dict] = []  # [{file_id, filename, url, mime_type, size_bytes}]


class AgentResponse(BaseModel):
    """Response from the orchestrator back to the platform."""

    content: str
    files: list[dict] = []  # [{filename, url}]
    error: str | None = None
    tool_calls_metadata: ToolCallsMetadata | None = None
