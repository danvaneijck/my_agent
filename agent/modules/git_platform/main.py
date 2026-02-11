"""Git Platform module — FastAPI service for GitHub/Bitbucket integration."""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from modules.git_platform.manifest import MANIFEST
from modules.git_platform.providers.github import GitHubProvider
from modules.git_platform.tools import GitPlatformTools
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
app = FastAPI(title="Git Platform Module", version="1.0.0")

settings = get_settings()
tools: GitPlatformTools | None = None

# All tool method names that the /execute endpoint can dispatch to.
TOOL_MAP = {
    "get_repo",
    "list_branches",
    "get_file",
    "list_issues",
    "get_issue",
    "create_issue",
    "comment_on_issue",
    "list_pull_requests",
    "get_pull_request",
    "create_pull_request",
    "comment_on_pull_request",
    "merge_pull_request",
    "get_ci_status",
}


@app.on_event("startup")
async def startup():
    global tools

    provider_type = settings.git_platform_provider
    token = settings.git_platform_token

    if not token:
        logger.warning(
            "git_platform_not_configured",
            msg="GIT_PLATFORM_TOKEN must be set — module will return errors",
        )
        return

    if provider_type == "github":
        provider = GitHubProvider(token=token, base_url=settings.git_platform_base_url)
    else:
        logger.error("git_platform_unknown_provider", provider=provider_type)
        return

    tools = GitPlatformTools(provider=provider)
    logger.info("git_platform_ready", provider=provider_type)


@app.on_event("shutdown")
async def shutdown():
    if tools is not None:
        await tools.provider.close()


@app.get("/manifest", response_model=ModuleManifest)
async def manifest():
    """Return the module manifest."""
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall):
    """Execute a tool call."""
    if tools is None:
        return ToolResult(
            tool_name=call.tool_name,
            success=False,
            error="Git platform module not configured — set GIT_PLATFORM_TOKEN in .env",
        )

    try:
        tool_name = call.tool_name.split(".")[-1]
        args = dict(call.arguments)
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
