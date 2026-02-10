"""Scheduler module - FastAPI service with background worker."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import FastAPI

from modules.scheduler.manifest import MANIFEST
from modules.scheduler.tools import SchedulerTools
from modules.scheduler.worker import scheduler_loop
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
app = FastAPI(title="Scheduler Module", version="1.0.0")

tools: SchedulerTools | None = None
_worker_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup():
    global tools, _worker_task
    settings = get_settings()
    session_factory = get_session_factory()
    tools = SchedulerTools(session_factory, settings)

    # Start the background worker loop
    _worker_task = asyncio.create_task(
        scheduler_loop(session_factory, settings, settings.redis_url)
    )
    logger.info("scheduler_module_ready")


@app.on_event("shutdown")
async def shutdown():
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    logger.info("scheduler_module_shutdown")


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
        tool_name = call.tool_name.split(".")[-1]
        # Inject user_id from orchestrator context
        args = dict(call.arguments)
        if call.user_id:
            args["user_id"] = call.user_id

        if tool_name == "add_job":
            result = await tools.add_job(**args)
        elif tool_name == "list_jobs":
            result = await tools.list_jobs(**args)
        elif tool_name == "cancel_job":
            result = await tools.cancel_job(**args)
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
