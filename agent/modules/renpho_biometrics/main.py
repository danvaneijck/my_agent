"""Renpho biometrics module - FastAPI service."""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from modules.renpho_biometrics.manifest import MANIFEST
from modules.renpho_biometrics.tools import RenphoBiometricsTools
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
app = FastAPI(title="Renpho Biometrics Module", version="1.0.0")

tools: RenphoBiometricsTools | None = None


@app.on_event("startup")
async def startup():
    global tools
    settings = get_settings()
    email = settings.renpho_email
    password = settings.renpho_password
    if not email or not password:
        logger.warning("renpho_credentials_missing", msg="Set RENPHO_EMAIL and RENPHO_PASSWORD in .env")
    tools = RenphoBiometricsTools(email=email, password=password)
    logger.info("renpho_biometrics_module_ready")


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

        if tool_name == "get_measurements":
            result = await tools.get_measurements(**call.arguments)
        elif tool_name == "get_latest":
            result = await tools.get_latest(**call.arguments)
        elif tool_name == "get_trend":
            result = await tools.get_trend(**call.arguments)
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
