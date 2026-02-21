"""Deployer module — FastAPI service."""

from __future__ import annotations

import structlog
from fastapi import Depends, FastAPI

from modules.deployer.manifest import MANIFEST
from modules.deployer.tools import DeployerTools
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
app = FastAPI(title="Deployer Module", version="1.0.0")

tools: DeployerTools | None = None


@app.on_event("startup")
async def startup() -> None:
    global tools
    tools = DeployerTools()
    await tools.init()
    logger.info("deployer_module_ready")


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
        if call.user_id:
            args["user_id"] = call.user_id

        if tool_name == "deploy":
            result = await tools.deploy(**args)
        elif tool_name == "list_deployments":
            result = await tools.list_deployments(**args)
        elif tool_name == "teardown":
            result = await tools.teardown(**args)
        elif tool_name == "teardown_all":
            result = await tools.teardown_all(**args)
        elif tool_name == "get_logs":
            result = await tools.get_logs(**args)
        elif tool_name == "get_services":
            result = await tools.get_services(**args)
        elif tool_name == "get_service_logs":
            result = await tools.get_service_logs(**args)
        elif tool_name == "get_env_vars":
            result = await tools.get_env_vars(**args)
        elif tool_name == "update_env_vars":
            result = await tools.update_env_vars(**args)
        elif tool_name == "restart":
            result = await tools.restart_deployment(**args)
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
