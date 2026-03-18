"""Error manager module — FastAPI service."""

from __future__ import annotations

import structlog
from fastapi import Depends, FastAPI

from modules.error_manager.manifest import MANIFEST
from modules.error_manager.tools import ErrorManagerTools
from shared.auth import require_service_auth
from shared.schemas.common import HealthResponse
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()
app = FastAPI(title="Error Manager Module", version="1.0.0")

tools: ErrorManagerTools | None = None


@app.on_event("startup")
async def startup() -> None:
    global tools
    tools = ErrorManagerTools()
    logger.info("error_manager_module_ready")


@app.get("/manifest", response_model=ModuleManifest)
async def manifest(_=Depends(require_service_auth)) -> ModuleManifest:
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall, _=Depends(require_service_auth)) -> ToolResult:
    if tools is None:
        return ToolResult(tool_name=call.tool_name, success=False, error="Module not ready")

    try:
        tool_name = call.tool_name.split(".")[-1]
        args = dict(call.arguments)

        if tool_name == "list_errors":
            result = await tools.list_errors(**args)
        elif tool_name == "error_summary":
            result = await tools.error_summary(**args)
        elif tool_name == "get_error":
            result = await tools.get_error(**args)
        elif tool_name == "dismiss_error":
            result = await tools.dismiss_error(**args)
        elif tool_name == "resolve_error":
            result = await tools.resolve_error(**args)
        elif tool_name == "bulk_dismiss":
            result = await tools.bulk_dismiss(**args)
        elif tool_name == "bulk_resolve":
            result = await tools.bulk_resolve(**args)
        else:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )
        return ToolResult(tool_name=call.tool_name, success=True, result=result)
    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e), exc_info=True)
        return ToolResult(tool_name=call.tool_name, success=False, error=str(e))


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
