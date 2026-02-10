"""Garmin Connect module - FastAPI service."""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from modules.garmin.manifest import MANIFEST
from modules.garmin.tools import GarminTools
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
app = FastAPI(title="Garmin Connect Module", version="1.0.0")

tools: GarminTools | None = None


@app.on_event("startup")
async def startup():
    global tools
    settings = get_settings()
    email = settings.garmin_email
    password = settings.garmin_password
    if not email or not password:
        logger.warning("garmin_credentials_missing", msg="Set GARMIN_EMAIL and GARMIN_PASSWORD in .env")
    tools = GarminTools(email=email, password=password)
    logger.info("garmin_module_ready")


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

        if tool_name == "get_daily_summary":
            result = await tools.get_daily_summary(**call.arguments)
        elif tool_name == "get_heart_rate":
            result = await tools.get_heart_rate(**call.arguments)
        elif tool_name == "get_sleep":
            result = await tools.get_sleep(**call.arguments)
        elif tool_name == "get_body_composition":
            result = await tools.get_body_composition(**call.arguments)
        elif tool_name == "get_activities":
            result = await tools.get_activities(**call.arguments)
        elif tool_name == "get_stress":
            result = await tools.get_stress(**call.arguments)
        elif tool_name == "get_steps":
            result = await tools.get_steps(**call.arguments)
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
