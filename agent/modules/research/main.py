"""Research module - FastAPI service."""

from __future__ import annotations

import structlog
from fastapi import Depends, FastAPI

from modules.research.manifest import MANIFEST
from modules.research.tools import ResearchTools
from shared.config import get_settings
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
app = FastAPI(title="Research Module", version="1.0.0")

settings = get_settings()
tools: ResearchTools | None = None


@app.on_event("startup")
async def startup():
    global tools
    tools = ResearchTools(orchestrator_url=settings.orchestrator_url)
    logger.info("research_module_ready")


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

        if tool_name == "web_search":
            result = await tools.web_search(**call.arguments)
        elif tool_name == "news_search":
            result = await tools.news_search(**call.arguments)
        elif tool_name == "fetch_webpage":
            result = await tools.fetch_webpage(**call.arguments)
        elif tool_name == "summarize_text":
            result = await tools.summarize_text(**call.arguments)
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
