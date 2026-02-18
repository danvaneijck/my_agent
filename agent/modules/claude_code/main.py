"""Claude Code module — FastAPI service."""

from __future__ import annotations

import asyncio
import structlog
from fastapi import Depends, FastAPI

from modules.claude_code.manifest import MANIFEST
from modules.claude_code.tools import ClaudeCodeTools
from shared.config import get_settings
from shared.credential_store import CredentialStore
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
app = FastAPI(title="Claude Code Module", version="1.0.0")

tools: ClaudeCodeTools | None = None
_credential_store: CredentialStore | None = None


async def cleanup_terminal_containers_loop() -> None:
    """Background task to cleanup idle terminal containers every hour."""
    while True:
        try:
            await asyncio.sleep(3600)  # 1 hour
            if tools:
                result = await tools.cleanup_idle_terminal_containers()
                if result["count"] > 0:
                    logger.info(
                        "terminal_cleanup_completed",
                        removed=result["count"],
                        containers=result["removed"],
                        errors=result.get("errors", []),
                    )
        except Exception as e:
            logger.error("cleanup_loop_error", error=str(e))


@app.on_event("startup")
async def startup() -> None:
    global tools, _credential_store
    tools = ClaudeCodeTools()
    settings = get_settings()
    if settings.credential_encryption_key:
        _credential_store = CredentialStore(settings.credential_encryption_key)
        logger.info("credential_store_initialized")
    else:
        logger.warning("credential_store_not_configured", reason="CREDENTIAL_ENCRYPTION_KEY not set")

    # Start background cleanup task
    asyncio.create_task(cleanup_terminal_containers_loop())
    logger.info("terminal_cleanup_loop_started")

    logger.info("claude_code_module_ready")


async def _get_user_credentials(user_id: str) -> dict[str, dict[str, str]]:
    """Look up per-user credentials for claude_code and github services."""
    if not _credential_store:
        return {}
    try:
        factory = get_session_factory()
        async with factory() as session:
            claude_creds = await _credential_store.get_all(session, user_id, "claude_code")
            github_creds = await _credential_store.get_all(session, user_id, "github")
        result = {}
        if claude_creds:
            result["claude_code"] = claude_creds
        if github_creds:
            result["github"] = github_creds
        return result
    except Exception as e:
        logger.warning("credential_lookup_failed", user_id=user_id, error=str(e))
        return {}


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

        # Look up per-user credentials for task execution methods
        if tool_name in ("run_task", "continue_task") and call.user_id:
            user_creds = await _get_user_credentials(call.user_id)
            if user_creds:
                args["user_credentials"] = user_creds

        if tool_name == "run_task":
            result = await tools.run_task(**args)
        elif tool_name == "continue_task":
            result = await tools.continue_task(**args)
        elif tool_name == "task_status":
            result = await tools.task_status(**args)
        elif tool_name == "task_logs":
            result = await tools.task_logs(**args)
        elif tool_name == "cancel_task":
            result = await tools.cancel_task(**args)
        elif tool_name == "list_tasks":
            result = await tools.list_tasks(**args)
        elif tool_name == "get_task_chain":
            result = await tools.get_task_chain(**args)
        elif tool_name == "delete_workspace":
            result = await tools.delete_workspace(**args)
        elif tool_name == "delete_all_workspaces":
            result = await tools.delete_all_workspaces(**args)
        elif tool_name == "browse_workspace":
            result = await tools.browse_workspace(**args)
        elif tool_name == "read_workspace_file":
            result = await tools.read_workspace_file(**args)
        elif tool_name == "get_task_container":
            result = await tools.get_task_container(**args)
        elif tool_name == "create_terminal_container":
            result = await tools.create_terminal_container(**args)
        elif tool_name == "stop_terminal_container":
            result = await tools.stop_terminal_container(**args)
        elif tool_name == "list_terminal_containers":
            result = await tools.list_terminal_containers(**args)
        elif tool_name == "git_status":
            result = await tools.git_status(**args)
        elif tool_name == "git_push":
            result = await tools.git_push(**args)
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
async def health() -> HealthResponse:
    return HealthResponse(status="ok")