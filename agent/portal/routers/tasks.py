"""Claude Code task management endpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query, WebSocket

from portal.auth import PortalUser, require_auth, verify_ws_auth
from portal.services.log_streamer import stream_task_logs
from portal.services.module_client import call_tool, check_module_health
from pydantic import BaseModel
from shared.config import get_settings
from shared.credential_store import CredentialStore
from shared.database import get_session_factory

logger = structlog.get_logger()
router = APIRouter(prefix="/api/tasks", tags=["tasks"])


# --------------- Health (must be before /{task_id} routes) ---------------


@router.get("/health")
async def tasks_health(user: PortalUser = Depends(require_auth)) -> dict:
    """Check if the claude_code module is reachable and the user has credentials."""
    # 1. Check module is running
    result = await check_module_health("claude_code")
    if result.get("status") != "ok":
        return {"available": False, "reason": "module_down", "error": "Claude Code service is not running."}

    # 2. Check user has claude_code credentials configured
    settings = get_settings()
    if settings.credential_encryption_key:
        try:
            store = CredentialStore(settings.credential_encryption_key)
            factory = get_session_factory()
            async with factory() as session:
                creds = await store.get_all(session, user.user_id, "claude_code")
            if creds:
                return {"available": True}
        except Exception as e:
            logger.warning("tasks_health_cred_check_failed", error=str(e))

    return {"available": False, "reason": "no_credentials", "error": "Claude Code credentials are not configured for your account."}


# --------------- Request schemas ---------------


class NewTaskRequest(BaseModel):
    prompt: str
    repo_url: str | None = None
    branch: str | None = None
    source_branch: str | None = None
    timeout: int | None = None
    mode: str = "execute"  # "execute" or "plan"
    auto_push: bool = False  # automatically push branch after task completes


class ContinueTaskRequest(BaseModel):
    prompt: str
    timeout: int | None = None
    mode: str | None = None  # None = inherit from parent, "execute" = approve plan


# --------------- REST endpoints ---------------


@router.get("")
async def list_tasks(
    status: str | None = Query(None, alias="status"),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List all Claude Code tasks, optionally filtered by status."""
    args: dict = {}
    if status:
        args["status_filter"] = status
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.list_tasks",
        arguments=args,
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.post("")
async def create_task(
    body: NewTaskRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Start a new Claude Code task."""
    args: dict = {"prompt": body.prompt}
    if body.repo_url:
        args["repo_url"] = body.repo_url
    if body.branch:
        args["branch"] = body.branch
    if body.source_branch:
        args["source_branch"] = body.source_branch
    if body.timeout is not None:
        args["timeout"] = body.timeout
    if body.mode:
        args["mode"] = body.mode
    if body.auto_push:
        args["auto_push"] = body.auto_push
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.run_task",
        arguments=args,
        user_id=str(user.user_id),
        timeout=30.0,
    )
    return result.get("result", {})


@router.get("/{task_id}")
async def get_task(
    task_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get status of a specific task."""
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.task_status",
        arguments={"task_id": task_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.get("/{task_id}/logs")
async def get_task_logs(
    task_id: str,
    tail: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get task logs with pagination."""
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.task_logs",
        arguments={"task_id": task_id, "tail": tail, "offset": offset},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.post("/{task_id}/continue")
async def continue_task(
    task_id: str,
    body: ContinueTaskRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Continue a task with a new prompt."""
    args: dict = {"task_id": task_id, "prompt": body.prompt}
    if body.timeout is not None:
        args["timeout"] = body.timeout
    if body.mode is not None:
        args["mode"] = body.mode
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.continue_task",
        arguments=args,
        user_id=str(user.user_id),
        timeout=30.0,
    )
    return result.get("result", {})


@router.get("/{task_id}/chain")
async def get_task_chain(
    task_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get all tasks in a planning chain."""
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.get_task_chain",
        arguments={"task_id": task_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.get("/{task_id}/workspace")
async def browse_workspace(
    task_id: str,
    path: str = Query("", alias="path"),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List files and directories in a task's workspace."""
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.browse_workspace",
        arguments={"task_id": task_id, "path": path},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.get("/{task_id}/workspace/file")
async def read_workspace_file(
    task_id: str,
    path: str = Query(..., alias="path"),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Read a file from a task's workspace."""
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.read_workspace_file",
        arguments={"task_id": task_id, "path": path},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.delete("/{task_id}")
async def cancel_task(
    task_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Cancel a running task."""
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.cancel_task",
        arguments={"task_id": task_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.delete("/{task_id}/workspace")
async def delete_workspace(
    task_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Delete a task's workspace and all associated tasks."""
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.delete_workspace",
        arguments={"task_id": task_id},
        user_id=str(user.user_id),
        timeout=30.0,
    )
    return result.get("result", {})


# --------------- WebSocket ---------------


@router.websocket("/{task_id}/logs/ws")
async def ws_task_logs(websocket: WebSocket, task_id: str) -> None:
    """Stream task logs in real-time via WebSocket."""
    await verify_ws_auth(websocket)
    await websocket.accept()
    await stream_task_logs(websocket, task_id)
