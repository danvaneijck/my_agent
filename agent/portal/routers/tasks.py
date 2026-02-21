"""Claude Code task management endpoints."""

from __future__ import annotations

import asyncio
import json
import uuid

import structlog
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, UploadFile, File

from portal.auth import PortalUser, require_auth, verify_ws_auth
from portal.services.log_streamer import stream_task_logs
from portal.services.module_client import call_tool, check_module_health
from portal.services.terminal_service import get_terminal_service
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


def _format_skill_block(skill: dict) -> str:
    """Format a skill dict into a readable Markdown block for prompt injection."""
    name = skill.get("name", "Unnamed Skill")
    category = skill.get("category") or ""
    language = skill.get("language") or ""
    description = skill.get("description") or ""
    content = skill.get("content", "")

    meta_parts = []
    if category:
        meta_parts.append(f"Category: {category}")
    if language:
        meta_parts.append(f"Language: {language}")

    lines = [f"### {name}"]
    if meta_parts:
        lines.append(f"*{' | '.join(meta_parts)}*")
    if description:
        lines.append(f"> {description}")
    lines.append("")

    fence = f"```{language}" if language else "```"
    lines.append(f"{fence}\n{content}\n```")
    lines.append("")
    return "\n".join(lines)


class NewTaskRequest(BaseModel):
    prompt: str
    repo_url: str | None = None
    branch: str | None = None
    source_branch: str | None = None
    timeout: int | None = None
    mode: str = "execute"  # "execute" or "plan"
    auto_push: bool = False  # automatically push branch after task completes
    skill_ids: list[str] | None = None  # skill IDs whose content will be injected into the prompt


class ContinueTaskRequest(BaseModel):
    prompt: str
    timeout: int | None = None
    mode: str | None = None  # None = inherit from parent, "execute" = approve plan


# --------------- REST endpoints ---------------


@router.get("")
async def list_tasks(
    status: str | None = Query(None, alias="status"),
    latest_per_chain: bool = Query(True),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List all Claude Code tasks, optionally filtered by status."""
    args: dict = {}
    if status:
        args["status_filter"] = status
    if latest_per_chain:
        args["latest_per_chain"] = True
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
    prompt = body.prompt

    # Fetch selected skills and inject their content into the prompt
    if body.skill_ids:
        skill_blocks: list[str] = []
        for skill_id in body.skill_ids:
            try:
                result = await call_tool(
                    module="skills_modules",
                    tool_name="skills_modules.get_skill",
                    arguments={"skill_id": skill_id},
                    user_id=str(user.user_id),
                    timeout=10.0,
                )
                skill = result.get("result", {})
                if skill:
                    skill_blocks.append(_format_skill_block(skill))
            except Exception as e:
                logger.warning("skill_fetch_failed_for_task", skill_id=skill_id, error=str(e))

        if skill_blocks:
            header = "## Skills Context\n\nThe following skills are included as context for this task:\n\n---\n"
            skills_section = header + "\n---\n".join(skill_blocks)
            prompt = f"{skills_section}\n---\n\n## Task\n\n{body.prompt}"

    args: dict = {"prompt": prompt}
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


@router.post("/{task_id}/workspace/upload")
async def upload_workspace_file(
    task_id: str,
    file: UploadFile = File(...),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Upload a file to a task's workspace."""
    import tempfile
    import os
    import docker

    # Read file content
    content = await file.read()

    # Save to temporary file on host
    with tempfile.NamedTemporaryFile(delete=False, suffix=f"_{file.filename}") as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        # Get container info
        workspace_result = await call_tool(
            module="claude_code",
            tool_name="claude_code.get_task_container",
            arguments={"task_id": task_id},
            user_id=str(user.user_id),
            timeout=15.0,
        )

        container_info = workspace_result.get("result", {})
        container_id = container_info.get("container_id")
        workspace = container_info.get("workspace", "")

        if not container_id or not workspace:
            return {"success": False, "message": "Container or workspace not found"}

        # Copy file to container using Docker API
        docker_client = docker.from_env()
        container = docker_client.containers.get(container_id)

        # Read file and put it in container
        with open(tmp_path, "rb") as f:
            file_data = f.read()

        # Use docker cp to copy file to workspace
        import tarfile
        import io

        # Create tar archive in memory
        tar_stream = io.BytesIO()
        with tarfile.open(fileobj=tar_stream, mode="w") as tar:
            tarinfo = tarfile.TarInfo(name=file.filename or "uploaded_file")
            tarinfo.size = len(file_data)
            tar.addfile(tarinfo, io.BytesIO(file_data))

        tar_stream.seek(0)

        # Put archive into container
        container.put_archive(path=workspace, data=tar_stream.read())

        return {
            "success": True,
            "filename": file.filename,
            "message": f"File {file.filename} uploaded to workspace",
        }

    except Exception as e:
        logger.error("file_upload_error", error=str(e), task_id=task_id)
        return {"success": False, "message": str(e)}

    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except Exception:
            pass


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
    # Clean up terminal container if it exists
    terminal_service = get_terminal_service()
    await terminal_service.cleanup_terminal_container(task_id)

    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.delete_workspace",
        arguments={"task_id": task_id},
        user_id=str(user.user_id),
        timeout=30.0,
    )
    return result.get("result", {})


@router.post("/{task_id}/terminal/container")
async def create_terminal_container_endpoint(
    task_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Explicitly create a terminal container for a task.

    Useful for pre-warming container before opening terminal.
    """
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.create_terminal_container",
        arguments={"task_id": task_id},
        user_id=str(user.user_id),
        timeout=30.0,
    )
    return result.get("result", {})


@router.delete("/{task_id}/terminal/container")
async def stop_terminal_container_endpoint(
    task_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Stop and remove a terminal container."""
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.stop_terminal_container",
        arguments={"task_id": task_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.get("/terminal/containers")
async def list_terminal_containers_endpoint(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List all terminal containers for the current user."""
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.list_terminal_containers",
        arguments={},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.delete("/{task_id}/terminal")
async def stop_terminal_container(
    task_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Stop and remove the on-demand terminal container for a task (legacy endpoint)."""
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.stop_terminal_container",
        arguments={"task_id": task_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.delete("")
async def delete_all_workspaces(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Delete all workspaces and tasks for the current user."""
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.delete_all_workspaces",
        arguments={},
        user_id=str(user.user_id),
        timeout=60.0,
    )
    return result.get("result", {})


# --------------- WebSocket ---------------


@router.websocket("/{task_id}/logs/ws")
async def ws_task_logs(websocket: WebSocket, task_id: str) -> None:
    """Stream task logs in real-time via WebSocket."""
    await verify_ws_auth(websocket)
    await websocket.accept()
    await stream_task_logs(websocket, task_id)


@router.websocket("/{task_id}/terminal/ws")
async def ws_terminal(
    websocket: WebSocket,
    task_id: str,
    session_id: str = Query(None),
) -> None:
    """Interactive terminal session via WebSocket.

    Protocol:
    - Client → Server: {"type": "input", "data": "command text"}
    - Client → Server: {"type": "resize", "rows": 40, "cols": 120}
    - Server → Client: {"type": "output", "data": "terminal output"}
    - Server → Client: {"type": "ready"}
    - Server → Client: {"type": "error", "message": "error details"}
    """
    # Authenticate user
    user = await verify_ws_auth(websocket)
    await websocket.accept()

    terminal_service = get_terminal_service()
    # Use provided session_id or generate one
    if not session_id:
        session_id = f"terminal-{task_id}-{uuid.uuid4().hex[:8]}"
    socket = None

    try:
        # Get workspace information for the task
        logger.info("terminal_ws_connect", task_id=task_id, user_id=str(user.user_id))

        # Ensure a container exists (task or terminal)
        try:
            container_id = await terminal_service.ensure_terminal_container(
                task_id, str(user.user_id)
            )
        except Exception as e:
            logger.error(
                "terminal_container_ensure_failed",
                task_id=task_id,
                error=str(e),
            )
            await websocket.send_json({
                "type": "error",
                "message": str(e),
            })
            await websocket.close()
            return

        logger.info(
            "terminal_container_ready",
            task_id=task_id,
            container_id=container_id,
        )

        # Get workspace path from task status
        result = await call_tool(
            module="claude_code",
            tool_name="claude_code.task_status",
            arguments={"task_id": task_id},
            user_id=str(user.user_id),
            timeout=15.0,
        )

        task_info = result.get("result", {})
        workspace = task_info.get("workspace")

        if not workspace:
            await websocket.send_json({
                "type": "error",
                "message": "Workspace not found. The task may not have been created yet or was deleted.",
            })
            await websocket.close()
            return

        # Create terminal session
        # Use the actual workspace path instead of constructing from task_id
        # In task chains, workspace is named after the first task, not the current task
        session = await terminal_service.create_session(
            session_id=session_id,
            container_id=container_id,
            user_id=str(user.user_id),
            task_id=task_id,
            working_dir=workspace,
        )

        # Attach to session and get socket
        socket = await terminal_service.attach_session(session_id)

        # Set socket timeout to None (infinite) to prevent timeout errors
        # The WebSocket connection itself will handle disconnects
        socket._sock.settimeout(None)

        # Send ready signal
        await websocket.send_json({"type": "ready"})

        # Start bidirectional relay tasks
        async def read_from_container():
            """Read output from container and send to client."""
            try:
                loop = asyncio.get_event_loop()
                while True:
                    # Read from Docker socket in executor to avoid blocking event loop
                    chunk = await loop.run_in_executor(None, socket._sock.recv, 4096)
                    if not chunk:
                        break

                    # Send to WebSocket client
                    await websocket.send_json({
                        "type": "output",
                        "data": chunk.decode("utf-8", errors="replace"),
                    })

                    # Update activity timestamp
                    terminal_service.update_session_activity(session_id)

            except Exception as e:
                logger.debug("container_read_ended", error=str(e))

        async def write_to_container():
            """Read input from client and send to container."""
            try:
                while True:
                    # Receive from WebSocket client
                    message = await websocket.receive_json()

                    if message.get("type") == "input":
                        data = message.get("data", "")
                        # Send to Docker socket
                        socket._sock.sendall(data.encode("utf-8"))

                        # Update activity timestamp
                        terminal_service.update_session_activity(session_id)

                    elif message.get("type") == "resize":
                        # Handle terminal resize (future enhancement)
                        # Docker API supports exec_resize but requires exec_id
                        rows = message.get("rows", 24)
                        cols = message.get("cols", 80)
                        try:
                            terminal_service.docker_client.api.exec_resize(
                                exec_id=session.exec_id,
                                height=rows,
                                width=cols,
                            )
                        except Exception as e:
                            logger.debug("resize_failed", error=str(e))

            except WebSocketDisconnect:
                logger.info("terminal_client_disconnected", session_id=session_id)
            except Exception as e:
                logger.debug("websocket_read_ended", error=str(e))

        # Run both relay tasks concurrently
        await asyncio.gather(
            read_from_container(),
            write_to_container(),
            return_exceptions=True,
        )

    except Exception as e:
        logger.error(
            "terminal_ws_error",
            task_id=task_id,
            session_id=session_id,
            error=str(e),
        )
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Terminal error: {str(e)}",
            })
        except Exception:
            pass

    finally:
        # Cleanup session
        logger.info("terminal_ws_cleanup", session_id=session_id, task_id=task_id)
        await terminal_service.cleanup_session(session_id)
