"""Project planner module — FastAPI service for project management."""

from __future__ import annotations

import structlog
from fastapi import Depends, FastAPI

from modules.project_planner.manifest import MANIFEST
from modules.project_planner.tools import ProjectPlannerTools
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
app = FastAPI(title="Project Planner Module", version="1.0.0")

tools: ProjectPlannerTools | None = None


@app.on_event("startup")
async def startup():
    global tools
    session_factory = get_session_factory()
    tools = ProjectPlannerTools(session_factory)
    logger.info("project_planner_module_ready")


# Allowlist of valid tool methods (must match manifest tool names)
_ALLOWED_TOOLS = {
    "create_project", "update_project", "get_project", "list_projects",
    "delete_project", "add_phase", "update_phase", "add_task",
    "bulk_add_tasks", "update_task", "get_task", "get_phase_tasks",
    "get_next_task", "get_execution_plan", "bulk_update_tasks",
    "get_project_status", "execute_next_phase", "complete_phase",
    "start_project_workflow", "advance_project_workflow",
}


@app.get("/manifest", response_model=ModuleManifest)
async def manifest(_=Depends(require_service_auth)):
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall, _=Depends(require_service_auth)):
    if tools is None:
        return ToolResult(tool_name=call.tool_name, success=False, error="Module not ready")

    try:
        tool_name = call.tool_name.split(".")[-1]
        if tool_name not in _ALLOWED_TOOLS:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        args = dict(call.arguments)
        if call.user_id:
            args["user_id"] = call.user_id

        handler = getattr(tools, tool_name)
        result = await handler(**args)
        return ToolResult(tool_name=call.tool_name, success=True, result=result)
    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e), exc_info=True)
        return ToolResult(tool_name=call.tool_name, success=False, error=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
