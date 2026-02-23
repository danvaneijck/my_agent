"""Crew session endpoints for the portal."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from portal.auth import PortalUser, require_auth
from portal.services.module_client import call_tool

logger = structlog.get_logger()
router = APIRouter(prefix="/api/crews", tags=["crews"])


# --------------- Request schemas ---------------


class CreateCrewRequest(BaseModel):
    project_id: str
    name: str | None = None
    max_agents: int = 4
    role_assignments: dict | None = None
    auto_push: bool = True
    timeout: int = 1800


class StartCrewRequest(BaseModel):
    pass  # no extra params needed


class PostContextRequest(BaseModel):
    entry_type: str
    title: str
    content: str


# --------------- Endpoints ---------------


@router.get("")
async def list_sessions(
    status: str | None = Query(None),
    user: PortalUser = Depends(require_auth),
) -> list:
    """List crew sessions for the authenticated user."""
    args: dict = {}
    if status:
        args["status_filter"] = status
    result = await call_tool(
        module="crew",
        tool_name="crew.list_sessions",
        arguments=args,
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", [])


@router.post("")
async def create_session(
    body: CreateCrewRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Create a new crew session linked to a project."""
    result = await call_tool(
        module="crew",
        tool_name="crew.create_session",
        arguments=body.model_dump(exclude_none=True),
        user_id=str(user.user_id),
        timeout=30.0,
    )
    return result.get("result", {})


@router.get("/{session_id}")
async def get_session(
    session_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get full crew session detail with members and context."""
    result = await call_tool(
        module="crew",
        tool_name="crew.get_session",
        arguments={"session_id": session_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.post("/{session_id}/start")
async def start_session(
    session_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Start a crew session — dispatches wave 1."""
    result = await call_tool(
        module="crew",
        tool_name="crew.start_session",
        arguments={"session_id": session_id},
        user_id=str(user.user_id),
        timeout=60.0,
    )
    return result.get("result", {})


@router.post("/{session_id}/pause")
async def pause_session(
    session_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Pause a running crew session."""
    result = await call_tool(
        module="crew",
        tool_name="crew.pause_session",
        arguments={"session_id": session_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.post("/{session_id}/resume")
async def resume_session(
    session_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Resume a paused crew session."""
    result = await call_tool(
        module="crew",
        tool_name="crew.resume_session",
        arguments={"session_id": session_id},
        user_id=str(user.user_id),
        timeout=60.0,
    )
    return result.get("result", {})


@router.post("/{session_id}/cancel")
async def cancel_session(
    session_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Cancel a crew session and stop all running agents."""
    result = await call_tool(
        module="crew",
        tool_name="crew.cancel_session",
        arguments={"session_id": session_id},
        user_id=str(user.user_id),
        timeout=30.0,
    )
    return result.get("result", {})


@router.get("/{session_id}/context")
async def get_context_board(
    session_id: str,
    user: PortalUser = Depends(require_auth),
) -> list:
    """Get all context board entries."""
    result = await call_tool(
        module="crew",
        tool_name="crew.get_context_board",
        arguments={"session_id": session_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", [])


@router.post("/{session_id}/context")
async def post_context(
    session_id: str,
    body: PostContextRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Post an entry to the shared context board."""
    result = await call_tool(
        module="crew",
        tool_name="crew.post_context",
        arguments={
            "session_id": session_id,
            **body.model_dump(),
        },
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})
