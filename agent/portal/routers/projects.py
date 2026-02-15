"""Project planner endpoints for the portal."""

from __future__ import annotations

import json
import re

import anthropic
import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from portal.auth import PortalUser, require_auth
from portal.services.module_client import call_tool
from shared.config import get_settings

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
    planning_task_id: str | None = None


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


class ApplyPlanRequest(BaseModel):
    plan_content: str | None = None  # If None, fetch from planning task


class ExecutePhaseRequest(BaseModel):
    phase_id: str | None = None  # If None, auto-pick next incomplete phase
    auto_push: bool = True
    timeout: int = 1800


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

    # 4. Update project with planning_task_id and status
    try:
        update_args = {
            "project_id": project_id,
            "planning_task_id": claude_task.get("task_id"),
        }
        # Keep status as "planning" for plan mode, "active" for execute mode
        if mode == "execute":
            update_args["status"] = "active"
        elif mode == "plan":
            update_args["status"] = "planning"

        await call_tool(
            module="project_planner",
            tool_name="project_planner.update_project",
            arguments=update_args,
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


@router.post("/{project_id}/apply-plan")
async def apply_plan(
    project_id: str,
    body: ApplyPlanRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Parse a plan and create project phases and tasks from it."""
    uid = str(user.user_id)
    settings = get_settings()

    # 1. Get the project
    project_result = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_project",
        arguments={"project_id": project_id},
        user_id=uid,
        timeout=15.0,
    )
    project_data = project_result.get("result", {})

    # 2. Get plan content
    plan_content = body.plan_content
    if not plan_content:
        # Fetch from planning task
        planning_task_id = project_data.get("planning_task_id")
        if not planning_task_id:
            raise ValueError("No planning_task_id found and no plan_content provided")

        task_result = await call_tool(
            module="claude_code",
            tool_name="claude_code.task_status",
            arguments={"task_id": planning_task_id},
            user_id=uid,
            timeout=15.0,
        )
        task_data = task_result.get("result", {})
        task_result_data = task_data.get("result") or {}

        # Extract plan content from task result
        plan_content = (
            task_result_data.get("plan_content") or
            task_result_data.get("raw_text") or
            ""
        )

    if not plan_content.strip():
        raise ValueError("No plan content found to apply")

    # 3. Parse plan using Anthropic API
    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    parse_system_prompt = """You are a project plan parser. Given a markdown project plan, extract it into structured phases and tasks.

Return JSON in this exact format:
{
  "design_document": "extracted design overview text (if any)",
  "phases": [
    {
      "name": "Phase 1: ...",
      "description": "...",
      "tasks": [
        {
          "title": "Task title",
          "description": "Detailed description",
          "acceptance_criteria": "How to verify completion"
        }
      ]
    }
  ]
}

Rules:
- Each phase should have a clear name and description
- Each task should have a title, description, and acceptance criteria
- Preserve the order from the original plan
- If the plan has no clear phase structure, create logical groupings
- Extract any design document or architecture overview into the design_document field"""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=parse_system_prompt,
            messages=[{"role": "user", "content": plan_content}],
        )

        # Extract JSON from response
        response_text = response.content[0].text
        # Try to extract JSON from markdown code blocks if present
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group(1))
        else:
            parsed = json.loads(response_text)

    except Exception as e:
        logger.error("plan_parse_failed", error=str(e), plan_length=len(plan_content))
        raise ValueError(f"Failed to parse plan: {str(e)}")

    # 4. Update project with design document and status
    design_doc = parsed.get("design_document")
    if design_doc:
        await call_tool(
            module="project_planner",
            tool_name="project_planner.update_project",
            arguments={
                "project_id": project_id,
                "design_document": design_doc,
                "status": "active",
            },
            user_id=uid,
            timeout=15.0,
        )
    else:
        await call_tool(
            module="project_planner",
            tool_name="project_planner.update_project",
            arguments={"project_id": project_id, "status": "active"},
            user_id=uid,
            timeout=15.0,
        )

    # 5. Create phases and tasks
    phases = parsed.get("phases", [])
    phases_created = 0
    tasks_created = 0

    for phase_data in phases:
        phase_result = await call_tool(
            module="project_planner",
            tool_name="project_planner.add_phase",
            arguments={
                "project_id": project_id,
                "name": phase_data.get("name", "Unnamed Phase"),
                "description": phase_data.get("description"),
            },
            user_id=uid,
            timeout=15.0,
        )
        phase_id = phase_result.get("result", {}).get("phase_id")
        phases_created += 1

        # Add tasks for this phase
        tasks = phase_data.get("tasks", [])
        if tasks and phase_id:
            await call_tool(
                module="project_planner",
                tool_name="project_planner.bulk_add_tasks",
                arguments={
                    "phase_id": phase_id,
                    "tasks": tasks,
                },
                user_id=uid,
                timeout=30.0,
            )
            tasks_created += len(tasks)

    logger.info(
        "plan_applied",
        project_id=project_id,
        phases_created=phases_created,
        tasks_created=tasks_created,
    )

    return {
        "project_id": project_id,
        "phases_created": phases_created,
        "tasks_created": tasks_created,
        "message": f"Created {phases_created} phases with {tasks_created} tasks",
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


@router.post("/{project_id}/execute-phase")
async def execute_phase(
    project_id: str,
    body: ExecutePhaseRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Start executing a phase by launching a Claude Code task."""
    uid = str(user.user_id)

    # 1. Get project
    project_result = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_project",
        arguments={"project_id": project_id},
        user_id=uid,
        timeout=15.0,
    )
    project_data = project_result.get("result", {})

    # 2. Determine target phase
    target_phase_id = body.phase_id
    if not target_phase_id:
        # Find first phase with todo tasks
        for phase in project_data.get("phases", []):
            if phase.get("status") in ("planned", "in_progress"):
                task_counts = phase.get("task_counts", {})
                if task_counts.get("todo", 0) > 0:
                    target_phase_id = phase["phase_id"]
                    break

    if not target_phase_id:
        raise ValueError("No phase found with pending tasks to execute")

    # 3. Get execution plan for this phase
    exec_plan_result = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_execution_plan",
        arguments={
            "project_id": project_id,
            "phase_ids": [target_phase_id],
        },
        user_id=uid,
        timeout=15.0,
    )
    exec_plan = exec_plan_result.get("result", {})

    if not exec_plan.get("prompt"):
        raise ValueError("No tasks to execute in the selected phase")

    repo_url = exec_plan.get("repo_url")
    prompt = exec_plan.get("prompt")
    default_branch = project_data.get("default_branch", "main")

    # Find the phase to get its branch name
    target_phase = next(
        (p for p in project_data.get("phases", []) if p["phase_id"] == target_phase_id),
        None
    )
    if not target_phase:
        raise ValueError(f"Phase not found: {target_phase_id}")

    phase_branch = target_phase.get("branch_name")
    source_branch = default_branch

    # 4. Launch claude_code task
    task_args = {
        "prompt": prompt,
        "mode": "execute",
        "auto_push": body.auto_push,
        "timeout": body.timeout,
    }
    if repo_url:
        task_args["repo_url"] = repo_url
        task_args["branch"] = phase_branch
        task_args["source_branch"] = source_branch

    task_result = await call_tool(
        module="claude_code",
        tool_name="claude_code.run_task",
        arguments=task_args,
        user_id=uid,
        timeout=30.0,
    )
    claude_task = task_result.get("result", {})
    claude_task_id = claude_task.get("task_id")

    # 5. Mark tasks as "doing" with claude_task_id
    todo_task_ids = exec_plan.get("todo_task_ids", [])
    if todo_task_ids:
        await call_tool(
            module="project_planner",
            tool_name="project_planner.bulk_update_tasks",
            arguments={
                "task_ids": todo_task_ids,
                "status": "doing",
                "claude_task_id": claude_task_id,
            },
            user_id=uid,
            timeout=15.0,
        )

    # 6. Update phase status to in_progress
    await call_tool(
        module="project_planner",
        tool_name="project_planner.update_phase",
        arguments={
            "phase_id": target_phase_id,
            "status": "in_progress",
        },
        user_id=uid,
        timeout=15.0,
    )

    logger.info(
        "phase_execution_started",
        project_id=project_id,
        phase_id=target_phase_id,
        claude_task_id=claude_task_id,
        task_count=len(todo_task_ids),
    )

    return {
        "phase_id": target_phase_id,
        "claude_task_id": claude_task_id,
        "task_count": len(todo_task_ids),
        "message": f"Started executing {len(todo_task_ids)} tasks in phase '{target_phase.get('name')}'",
    }


@router.get("/{project_id}/execution-status")
async def get_execution_status(
    project_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get current execution status for a project."""
    uid = str(user.user_id)

    # 1. Get project status
    status_result = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_project_status",
        arguments={"project_id": project_id},
        user_id=uid,
        timeout=15.0,
    )
    project_status = status_result.get("result", {})

    current_phase = project_status.get("current_phase")
    if not current_phase or current_phase.get("status") != "in_progress":
        return {
            "project_id": project_id,
            "project_status": project_status.get("status"),
            "current_phase": None,
            "claude_task_status": None,
            "message": "No phase currently executing",
        }

    # 2. Get tasks for current phase to find claude_task_id
    phase_id = current_phase["phase_id"]
    tasks_result = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_phase_tasks",
        arguments={"phase_id": phase_id},
        user_id=uid,
        timeout=15.0,
    )
    tasks = tasks_result.get("result", [])

    # Find a task with a claude_task_id
    claude_task_id = None
    for task in tasks:
        if task.get("claude_task_id") and task.get("status") == "doing":
            claude_task_id = task["claude_task_id"]
            break

    claude_task_status = None
    if claude_task_id:
        # 3. Get claude_code task status
        task_status_result = await call_tool(
            module="claude_code",
            tool_name="claude_code.task_status",
            arguments={"task_id": claude_task_id},
            user_id=uid,
            timeout=15.0,
        )
        claude_task_status = task_status_result.get("result", {})

    # Count task statuses
    task_counts = project_status.get("task_counts", {})

    return {
        "project_id": project_id,
        "project_status": project_status.get("status"),
        "current_phase": current_phase,
        "claude_task_id": claude_task_id,
        "claude_task_status": claude_task_status,
        "total_tasks": project_status.get("total_tasks", 0),
        "task_counts": task_counts,
    }
