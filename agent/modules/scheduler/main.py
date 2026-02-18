"""Scheduler module - FastAPI service with background worker."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import Depends, FastAPI

from modules.scheduler.manifest import MANIFEST
from modules.scheduler.tools import SchedulerTools
from modules.scheduler.worker import scheduler_loop
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
        # Inject user_id from orchestrator context
        args = dict(call.arguments)
        if call.user_id:
            args["user_id"] = call.user_id

        # The orchestrator injects platform/conversation context for all scheduler.*
        # tools, but only add_job uses it. Strip for other tools.
        if tool_name != "add_job":
            for k in ("platform", "platform_channel_id", "platform_thread_id", "conversation_id"):
                args.pop(k, None)

        if tool_name == "add_job":
            result = await tools.add_job(**args)
        elif tool_name == "list_jobs":
            result = await tools.list_jobs(**args)
        elif tool_name == "cancel_job":
            result = await tools.cancel_job(**args)
        elif tool_name == "cancel_workflow":
            result = await tools.cancel_workflow(**args)
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
