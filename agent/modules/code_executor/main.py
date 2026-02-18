"""Code Executor module - FastAPI service."""

from __future__ import annotations

import structlog
from fastapi import Depends, FastAPI

from modules.code_executor.manifest import MANIFEST
from modules.code_executor.tools import CodeExecutorTools
from shared.config import get_settings
from shared.database import get_session_factory
from shared.schemas.common import HealthResponse
from shared.auth import require_service_auth
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()
app = FastAPI(title="Code Executor Module", version="1.0.0")

tools: CodeExecutorTools | None = None


@app.on_event("startup")
async def startup():
    global tools
    settings = get_settings()
    session_factory = get_session_factory()
    tools = CodeExecutorTools(settings, session_factory)
    logger.info("code_executor_ready")


@app.get("/manifest", response_model=ModuleManifest)
async def manifest(_=Depends(require_service_auth)):
    """Return the module manifest."""
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall, _=Depends(require_service_auth)):
    """Execute a tool call."""
    if tools is None:
        return ToolResult(tool_name=call.tool_name, success=False, error="Module not ready")

    try:
        tool_name = call.tool_name.split(".")[-1]

        if tool_name == "run_python":
            result = await tools.run_python(user_id=call.user_id, **call.arguments)
        elif tool_name == "load_file":
            result = await tools.load_file(user_id=call.user_id, **call.arguments)
        elif tool_name == "run_shell":
            result = await tools.run_shell(**call.arguments)
        else:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        return ToolResult(tool_name=call.tool_name, success=True, result=result)
    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e), exc_info=True)
        return ToolResult(tool_name=call.tool_name, success=False, error="Internal error processing request")


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
