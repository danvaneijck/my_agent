"""Claude Code module — FastAPI service."""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from modules.claude_code.manifest import MANIFEST
from modules.claude_code.tools import ClaudeCodeTools
from shared.schemas.common import HealthResponse
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()
app = FastAPI(title="Claude Code Module", version="1.0.0")

tools: ClaudeCodeTools | None = None


@app.on_event("startup")
async def startup() -> None:
    global tools
    tools = ClaudeCodeTools()
    logger.info("claude_code_module_ready")


@app.get("/manifest", response_model=ModuleManifest)
async def manifest() -> ModuleManifest:
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall) -> ToolResult:
    if tools is None:
        return ToolResult(tool_name=call.tool_name, success=False, error="Module not ready")

    try:
        tool_name = call.tool_name.split(".")[-1]
        args = dict(call.arguments)
        if call.user_id:
            args["user_id"] = call.user_id

        if tool_name == "run_task":
            result = await tools.run_task(**args)
        elif tool_name == "continue_task":
            result = await tools.continue_task(**args)
        elif tool_name == "task_status":
            result = await tools.task_status(**args)
        elif tool_name == "task_logs":
            result = await tools.task_logs(**args)
        elif tool_name == "cancel_task":
            result = await tools.cancel_task(**args)
        elif tool_name == "list_tasks":
            result = await tools.list_tasks(**args)
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
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
