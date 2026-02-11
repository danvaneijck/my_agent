"""MyFitnessPal module - FastAPI service."""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from modules.myfitnesspal.manifest import MANIFEST
from modules.myfitnesspal.tools import MyFitnessPalTools
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
app = FastAPI(title="MyFitnessPal Module", version="1.0.0")

tools: MyFitnessPalTools | None = None


@app.on_event("startup")
async def startup():
    global tools
    settings = get_settings()
    username = settings.mfp_username
    password = settings.mfp_password
    cookie_string = settings.mfp_cookie_string
    if not password and not cookie_string:
        logger.warning(
            "mfp_credentials_missing",
            msg="Set MFP_USERNAME + MFP_PASSWORD (recommended) or MFP_COOKIE_STRING in .env",
        )
    tools = MyFitnessPalTools(
        username=username, password=password, cookie_string=cookie_string
    )
    logger.info("myfitnesspal_module_ready")


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

        if tool_name == "get_day":
            result = await tools.get_day(**call.arguments)
        elif tool_name == "get_measurements":
            result = await tools.get_measurements(**call.arguments)
        elif tool_name == "get_report":
            result = await tools.get_report(**call.arguments)
        elif tool_name == "search_food":
            result = await tools.search_food(**call.arguments)
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
