"""Project planner endpoints for the portal."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from portal.auth import PortalUser, require_auth
from portal.services.module_client import call_tool

logger = structlog.get_logger()
router = APIRouter(prefix="/api/projects", tags=["projects"])


# --------------- Request schemas ---------------


class CreateProjectRequest(BaseModel):
    name: str
    description: str | None = None
    design_document: str | None = None
    repo_owner: str | None = None
    repo_name: str | None = None
    default_branch: str = "main"
    auto_merge: bool = False
    phases: list[dict] | None = None


class UpdateProjectRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    design_document: str | None = None
    status: str | None = None
    repo_owner: str | None = None
    repo_name: str | None = None
    default_branch: str | None = None
    auto_merge: bool | None = None


class UpdateTaskRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    acceptance_criteria: str | None = None
    status: str | None = None
    branch_name: str | None = None
    pr_number: int | None = None
    issue_number: int | None = None
    claude_task_id: str | None = None
    error_message: str | None = None


# --------------- Project endpoints ---------------


@router.get("")
async def list_projects(
    status: str | None = Query(None),
    user: PortalUser = Depends(require_auth),
) -> list:
    """List all projects for the authenticated user."""
    args: dict = {}
    if status:
        args["status_filter"] = status
    result = await call_tool(
        module="project_planner",
        tool_name="project_planner.list_projects",
        arguments=args,
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", [])


@router.post("")
async def create_project(
    body: CreateProjectRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Create a new project."""
    args = body.model_dump(exclude_none=True)
    result = await call_tool(
        module="project_planner",
        tool_name="project_planner.create_project",
        arguments=args,
        user_id=str(user.user_id),
        timeout=30.0,
    )
    return result.get("result", {})


@router.get("/{project_id}")
async def get_project(
    project_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get project detail with phases and task counts."""
    result = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_project",
        arguments={"project_id": project_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.put("/{project_id}")
async def update_project(
    project_id: str,
    body: UpdateProjectRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Update project fields."""
    args = {"project_id": project_id, **body.model_dump(exclude_none=True)}
    result = await call_tool(
        module="project_planner",
        tool_name="project_planner.update_project",
        arguments=args,
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.delete("/{project_id}")
async def delete_project(
    project_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Delete a project and all its phases/tasks."""
    result = await call_tool(
        module="project_planner",
        tool_name="project_planner.delete_project",
        arguments={"project_id": project_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.get("/{project_id}/status")
async def get_project_status(
    project_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get project status summary."""
    result = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_project_status",
        arguments={"project_id": project_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


# --------------- Phase endpoints ---------------


@router.get("/{project_id}/phases/{phase_id}/tasks")
async def get_phase_tasks(
    project_id: str,
    phase_id: str,
    user: PortalUser = Depends(require_auth),
) -> list:
    """Get all tasks for a phase (for kanban board)."""
    result = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_phase_tasks",
        arguments={"phase_id": phase_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", [])


# --------------- Task endpoints ---------------


@router.get("/{project_id}/tasks/{task_id}")
async def get_task(
    project_id: str,
    task_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get full detail for a task."""
    result = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_task",
        arguments={"task_id": task_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.put("/{project_id}/tasks/{task_id}")
async def update_task(
    project_id: str,
    task_id: str,
    body: UpdateTaskRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Update task fields (e.g., drag-and-drop status change on kanban)."""
    args = {"task_id": task_id, **body.model_dump(exclude_none=True)}
    result = await call_tool(
        module="project_planner",
        tool_name="project_planner.update_task",
        arguments=args,
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})
