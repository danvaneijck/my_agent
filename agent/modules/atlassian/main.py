"""Atlassian module — FastAPI service for Jira and Confluence integration."""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from modules.atlassian.manifest import MANIFEST
from modules.atlassian.tools import AtlassianTools
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
app = FastAPI(title="Atlassian Module", version="1.0.0")

settings = get_settings()
tools: AtlassianTools | None = None


@app.on_event("startup")
async def startup():
    global tools
    if not settings.atlassian_url or not settings.atlassian_api_token:
        logger.warning(
            "atlassian_not_configured",
            msg="ATLASSIAN_URL and ATLASSIAN_API_TOKEN must be set — module will return errors",
        )
        return

    tools = AtlassianTools(
        url=settings.atlassian_url,
        username=settings.atlassian_username,
        api_token=settings.atlassian_api_token,
        cloud=settings.atlassian_cloud,
        default_space=settings.confluence_default_space,
    )
    logger.info("atlassian_ready", url=settings.atlassian_url, cloud=settings.atlassian_cloud)


@app.get("/manifest", response_model=ModuleManifest)
async def manifest():
    """Return the module manifest."""
    return MANIFEST


TOOL_MAP = {
    "jira_search",
    "jira_get_issue",
    "jira_create_issue",
    "jira_update_issue",
    "confluence_search",
    "confluence_get_page",
    "confluence_create_page",
    "confluence_update_page",
    "create_meeting_notes",
    "create_feature_doc",
}


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall):
    """Execute a tool call."""
    if tools is None:
        return ToolResult(
            tool_name=call.tool_name,
            success=False,
            error="Atlassian module not configured — set ATLASSIAN_URL and ATLASSIAN_API_TOKEN in .env",
        )

    try:
        tool_name = call.tool_name.split(".")[-1]
        args = dict(call.arguments)
        # user_id is available but not used by Atlassian tools currently
        args.pop("user_id", None)

        if tool_name not in TOOL_MAP:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        method = getattr(tools, tool_name)
        result = await method(**args)
        return ToolResult(tool_name=call.tool_name, success=True, result=result)

    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e))
        return ToolResult(tool_name=call.tool_name, success=False, error=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
