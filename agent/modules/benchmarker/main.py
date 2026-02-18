"""Benchmarker module - FastAPI service."""

from __future__ import annotations

import structlog
from fastapi import Depends, FastAPI

from modules.benchmarker.manifest import MANIFEST
from modules.benchmarker.tools import BenchmarkerClient
from shared.auth import require_service_auth
from shared.config import get_settings
from shared.schemas.common import HealthResponse
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()
app = FastAPI(title="Benchmarker Module", version="1.0.0")

settings = get_settings()
client: BenchmarkerClient | None = None


@app.on_event("startup")
async def startup():
    global client
    client = BenchmarkerClient(
        api_url=settings.benchmarker_api_url,
        api_key=settings.benchmarker_api_key,
    )
    logger.info("benchmarker_module_ready")


@app.get("/manifest", response_model=ModuleManifest)
async def manifest(_=Depends(require_service_auth)):
    """Return the module manifest."""
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall, _=Depends(require_service_auth)):
    """Execute a tool call."""
    if client is None:
        return ToolResult(tool_name=call.tool_name, success=False, error="Module not ready")

    try:
        tool_name = call.tool_name.split(".")[-1]

        if tool_name == "device_lookup":
            result = await client.device_lookup(**call.arguments)
        elif tool_name == "send_downlink":
            result = await client.send_downlink(**call.arguments)
        elif tool_name == "organisation_summary":
            result = await client.organisation_summary(**call.arguments)
        elif tool_name == "site_overview":
            result = await client.site_overview(**call.arguments)
        elif tool_name == "silent_devices":
            result = await client.silent_devices(**call.arguments)
        elif tool_name == "low_battery_devices":
            result = await client.low_battery_devices(**call.arguments)
        elif tool_name == "device_issues":
            result = await client.device_issues(**call.arguments)
        elif tool_name == "org_issues_summary":
            result = await client.org_issues_summary(**call.arguments)
        elif tool_name == "provision_organisation":
            result = await client.provision_organisation(**call.arguments)
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
