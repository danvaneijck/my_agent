"""Tool and module manifest schemas."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class ToolParameter(BaseModel):
    """Parameter definition for a tool."""

    name: str
    type: str  # string, integer, boolean, number, array, object
    description: str
    required: bool = True
    enum: list[str] | None = None


class ToolDefinition(BaseModel):
    """Definition of a single tool exposed by a module."""

    name: str  # e.g. "file_manager.create_document"
    description: str
    parameters: list[ToolParameter]
    required_permission: str = "guest"  # minimum permission level


class ModuleManifest(BaseModel):
    """Manifest describing a module and its tools."""

    module_name: str
    description: str
    tools: list[ToolDefinition]


class ToolCall(BaseModel):
    """A tool call request."""

    tool_name: str
    arguments: dict


class ToolResult(BaseModel):
    """Result from a tool execution."""

    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None
