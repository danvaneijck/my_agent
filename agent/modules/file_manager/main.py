"""File Manager module - FastAPI service."""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from modules.file_manager.manifest import MANIFEST
from modules.file_manager.tools import FileManagerTools
from shared.config import get_settings
from shared.database import get_session_factory
from shared.schemas.common import HealthResponse
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()
app = FastAPI(title="File Manager Module", version="1.0.0")

settings = get_settings()
tools: FileManagerTools | None = None


@app.on_event("startup")
async def startup():
    global tools
    session_factory = get_session_factory()
    tools = FileManagerTools(settings, session_factory)
    logger.info("file_manager_ready")


@app.get("/manifest", response_model=ModuleManifest)
async def manifest():
    """Return the module manifest."""
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall):
    """Execute a tool call."""
    if tools is None:
        return ToolResult(tool_name=call.tool_name, success=False, error="Module not ready")

    try:
        # Strip module prefix
        tool_name = call.tool_name.split(".")[-1]

        if tool_name == "create_document":
            result = await tools.create_document(user_id=call.user_id, **call.arguments)
        elif tool_name == "upload_file":
            result = await tools.upload_file(user_id=call.user_id, **call.arguments)
        elif tool_name == "read_document":
            result = await tools.read_document(user_id=call.user_id, **call.arguments)
        elif tool_name == "list_files":
            result = await tools.list_files(user_id=call.user_id, **call.arguments)
        elif tool_name == "get_file_link":
            result = await tools.get_file_link(user_id=call.user_id, **call.arguments)
        elif tool_name == "delete_file":
            result = await tools.delete_file(user_id=call.user_id, **call.arguments)
        else:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        return ToolResult(tool_name=call.tool_name, success=True, result=result)
    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e))
        return ToolResult(tool_name=call.tool_name, success=False, error=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
