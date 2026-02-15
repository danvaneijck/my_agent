"""Project planner endpoints for the portal."""

from __future__ import annotations

import re

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from portal.auth import PortalUser, require_auth
from portal.services.module_client import call_tool

logger = structlog.get_logger()
router = APIRouter(prefix="/api/projects", tags=["projects"])


def _slugify(text: str) -> str:
    """Convert text to a git-branch-safe slug."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return slug[:40] or "new-project"


def _build_planning_prompt(project_data: dict, description: str | None) -> str:
    """Build a prompt that asks Claude to create a project plan."""
    name = project_data.get("name", "Untitled")
    desc = description or project_data.get("description") or ""
    design_doc = project_data.get("design_document") or ""

    lines = [
        f'You are planning a software project called "{name}".',
        "",
    ]
    if desc:
        lines.append(f"## Project Goal\n\n{desc}\n")
    if design_doc:
        lines.append(f"## Design Document\n\n{design_doc}\n")

    lines.extend([
        "## Your Task",
        "",
        "1. Analyze the repository (if it exists) to understand the current codebase.",
        "2. Create a detailed design document covering architecture, key decisions, and implementation approach.",
        "3. Break the project into phases, each with concrete, implementable tasks.",
        "4. Each task should have a clear title, description, and acceptance criteria.",
        "5. Write the plan to PLAN.md in the workspace.",
        "",
        "Focus on creating an actionable, well-structured plan that can be executed incrementally.",
    ])
    return "\n".join(lines)


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


class KickoffRequest(BaseModel):
    mode: str = "plan"  # "plan" or "execute"
    auto_push: bool = True
    timeout: int = 1800
    description: str | None = None  # optional project goal for the prompt


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


@router.post("/{project_id}/kickoff")
async def kickoff_project(
    project_id: str,
    body: KickoffRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Create a project record and fire a claude_code task to plan or implement it."""
    uid = str(user.user_id)

    # 1. Get the project to extract repo info
    project_result = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_project",
        arguments={"project_id": project_id},
        user_id=uid,
        timeout=15.0,
    )
    project_data = project_result.get("result", {})

    repo_owner = project_data.get("repo_owner")
    repo_name = project_data.get("repo_name")
    repo_url = f"https://github.com/{repo_owner}/{repo_name}" if repo_owner and repo_name else None
    default_branch = project_data.get("default_branch", "main")

    # 2. Build prompt based on mode
    mode = body.mode
    if mode == "execute":
        # Try to get execution plan from existing tasks
        try:
            exec_result = await call_tool(
                module="project_planner",
                tool_name="project_planner.get_execution_plan",
                arguments={"project_id": project_id},
                user_id=uid,
                timeout=15.0,
            )
            plan_data = exec_result.get("result", {})
            if plan_data.get("prompt"):
                prompt = plan_data["prompt"]
                branch = plan_data.get("branch", default_branch)
            else:
                # No tasks to execute — fall back to planning
                prompt = _build_planning_prompt(project_data, body.description)
                mode = "plan"
                branch = f"project/{_slugify(project_data.get('name', 'new'))}"
        except Exception:
            prompt = _build_planning_prompt(project_data, body.description)
            mode = "plan"
            branch = f"project/{_slugify(project_data.get('name', 'new'))}"
    else:
        prompt = _build_planning_prompt(project_data, body.description)
        branch = f"project/{_slugify(project_data.get('name', 'new'))}"

    # 3. Fire claude_code task
    task_args: dict = {
        "prompt": prompt,
        "mode": mode,
        "auto_push": body.auto_push,
        "timeout": body.timeout,
    }
    if repo_url:
        task_args["repo_url"] = repo_url
        task_args["branch"] = branch
        task_args["source_branch"] = default_branch

    task_result = await call_tool(
        module="claude_code",
        tool_name="claude_code.run_task",
        arguments=task_args,
        user_id=uid,
        timeout=30.0,
    )
    claude_task = task_result.get("result", {})

    # 4. Update project status to "active"
    try:
        await call_tool(
            module="project_planner",
            tool_name="project_planner.update_project",
            arguments={"project_id": project_id, "status": "active"},
            user_id=uid,
            timeout=15.0,
        )
    except Exception as e:
        logger.warning("kickoff_status_update_failed", project_id=project_id, error=str(e))

    return {
        "project_id": project_id,
        "claude_task_id": claude_task.get("task_id"),
        "mode": mode,
        "workspace": claude_task.get("workspace"),
    }


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
