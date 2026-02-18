"""Skills module — FastAPI service for skills registry."""

from __future__ import annotations

import structlog
from fastapi import Depends, FastAPI

from modules.skills_modules.manifest import MANIFEST
from modules.skills_modules.tools import SkillsTools
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
app = FastAPI(title="Skills Module", version="1.0.0")

tools: SkillsTools | None = None


@app.on_event("startup")
async def startup():
    global tools
    session_factory = get_session_factory()
    tools = SkillsTools(session_factory)
    logger.info("skills_module_ready")


# Allowlist of valid tool methods (must match manifest tool names)
_ALLOWED_TOOLS = {
    "create_skill", "list_skills", "get_skill", "update_skill",
    "delete_skill", "attach_skill_to_project", "detach_skill_from_project",
    "get_project_skills", "attach_skill_to_task", "detach_skill_from_task",
    "get_task_skills", "render_skill",
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
        return ToolResult(tool_name=call.tool_name, success=False, error="Internal error processing request")


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
