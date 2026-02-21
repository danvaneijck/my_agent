"""Project planner endpoints for the portal."""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone

import anthropic
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from portal.auth import PortalUser, require_auth
from portal.services.module_client import call_tool
from shared.config import get_settings
from sqlalchemy import func, select
from sqlalchemy import delete as sa_delete
from sqlalchemy import update as sa_update

from shared.database import get_session_factory
from shared.models.project import Project
from shared.models.project_phase import ProjectPhase
from shared.models.project_task import ProjectTask
from shared.models.token_usage import TokenLog

logger = structlog.get_logger()
router = APIRouter(prefix="/api/projects", tags=["projects"])

# Cost per 1M tokens (input, output) — mirrors core/llm_router/token_counter.py
_MODEL_COSTS: dict[str, tuple[float, float]] = {
    "claude-sonnet-4-20250514": (3.0, 15.0),
    "claude-haiku-4-5-20251001": (1.0, 5.0),
}


async def _log_portal_tokens(
    user_id: uuid.UUID,
    model: str,
    input_tokens: int,
    output_tokens: int,
    conversation_id: uuid.UUID | None = None,
) -> None:
    """Log token usage for direct Anthropic API calls made by the portal."""
    try:
        costs = _MODEL_COSTS.get(model, (3.0, 15.0))
        cost = (input_tokens / 1_000_000) * costs[0] + (output_tokens / 1_000_000) * costs[1]

        factory = get_session_factory()
        async with factory() as session:
            session.add(TokenLog(
                id=uuid.uuid4(),
                user_id=user_id,
                conversation_id=conversation_id,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_estimate=cost,
                created_at=datetime.now(timezone.utc),
            ))
            # Also update user's monthly counter
            from shared.models.user import User
            from sqlalchemy import select
            result = await session.execute(select(User).where(User.id == user_id))
            user_record = result.scalar_one_or_none()
            if user_record:
                user_record.tokens_used_this_month += input_tokens + output_tokens
            await session.commit()

        logger.info("portal_token_usage", model=model, input_tokens=input_tokens,
                     output_tokens=output_tokens, cost=round(cost, 6))
    except Exception as e:
        logger.error("portal_token_log_failed", error=str(e))


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
        "5. Write the complete plan to PLAN.md in the repository root and commit it.",
        "   This file will be used as context for all subsequent implementation phases.",
        "",
        "Focus on creating an actionable, well-structured plan that can be executed incrementally.",
        "",
        "## Git Workflow",
        "",
        "- Commit PLAN.md with the message: `docs: add project plan`",
        "- Push your branch: `git push -u origin HEAD`",
        "- **Do NOT start implementing.** Stop immediately after pushing PLAN.md.",
        "  Implementation will be requested as a separate step.",
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
    custom_prompt: str | None = None  # Optional instructions for the parser (e.g., "condense into 3 phases")
    force: bool = False  # Allow re-applying even when already applied


class ExecutePhaseRequest(BaseModel):
    phase_id: str | None = None  # If None, auto-pick next incomplete phase
    auto_push: bool = True
    timeout: int = 1800


class RetryPhaseRequest(BaseModel):
    phase_id: str


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


@router.post("/{project_id}/clear-phases")
async def clear_phases(
    project_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Delete all phases and tasks for a project, keeping the project itself."""
    uid = user.user_id
    pid = uuid.UUID(project_id)

    factory = get_session_factory()
    async with factory() as session:
        # Verify project belongs to user
        project = (await session.execute(
            select(Project).where(Project.id == pid, Project.user_id == uid)
        )).scalar_one_or_none()
        if not project:
            raise ValueError(f"Project not found: {project_id}")

        # Delete tasks first (FK constraint), then phases
        await session.execute(
            sa_delete(ProjectTask).where(ProjectTask.project_id == pid)
        )
        await session.execute(
            sa_delete(ProjectPhase).where(ProjectPhase.project_id == pid)
        )
        # Reset plan apply state so the plan can be applied again
        await session.execute(
            sa_update(Project)
            .where(Project.id == pid, Project.user_id == uid)
            .values(
                plan_apply_status="idle",
                plan_apply_error=None,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    logger.info("phases_cleared", project_id=project_id)
    return {"project_id": project_id, "message": "All phases and tasks cleared"}


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
                branch = (
                    project_data.get("project_branch")
                    or f"project/{_slugify(project_data.get('name', 'new'))}/integration"
                )
        except Exception:
            prompt = _build_planning_prompt(project_data, body.description)
            mode = "plan"
            branch = (
                project_data.get("project_branch")
                or f"project/{_slugify(project_data.get('name', 'new'))}/integration"
            )
    else:
        prompt = _build_planning_prompt(project_data, body.description)
        branch = (
            project_data.get("project_branch")
            or f"project/{_slugify(project_data.get('name', 'new'))}/integration"
        )

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
    pid = uuid.UUID(project_id)
    user_uuid = user.user_id
    settings = get_settings()
    factory = get_session_factory()

    # 1. Get the project and check idempotency
    project_result = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_project",
        arguments={"project_id": project_id},
        user_id=uid,
        timeout=15.0,
    )
    project_data = project_result.get("result", {})

    current_apply_status = project_data.get("plan_apply_status", "idle")
    if current_apply_status == "applying":
        raise HTTPException(
            status_code=409,
            detail="Plan application is already in progress. Please wait.",
        )
    if current_apply_status == "applied" and not body.force:
        raise HTTPException(
            status_code=409,
            detail="Plan has already been applied. Use force=true to re-apply.",
        )

    # 2. Persist "applying" state immediately so navigation away doesn't lose it
    async with factory() as session:
        await session.execute(
            sa_update(Project)
            .where(Project.id == pid, Project.user_id == user_uuid)
            .values(
                plan_apply_status="applying",
                plan_apply_error=None,
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    try:
        # 3. Get plan content
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
            logger.info(
                "apply_plan_source",
                has_plan_content=bool(task_result_data.get("plan_content")),
                has_raw_text=bool(task_result_data.get("raw_text")),
                plan_length=len(plan_content),
            )

        if not plan_content.strip():
            raise ValueError("No plan content found to apply")

        # 4. Parse plan using Anthropic API
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        parse_system_prompt = """You are a project plan parser. Given a markdown project plan, extract it into structured phases and tasks.

Return ONLY valid JSON with no other text, no markdown formatting, no code blocks. Return JSON in this exact format:
{
  "phases": [
    {
      "name": "Phase 1: ...",
      "description": "Phase description",
      "tasks": [
        {
          "title": "Task title",
          "description": "Full task description preserving all detail",
          "acceptance_criteria": "All acceptance criteria, preserving every bullet point"
        }
      ]
    }
  ]
}

Rules:
- Each phase should have a clear name and description
- Each task should have a title, description, and acceptance criteria
- IMPORTANT: Preserve the FULL detail from the original plan in descriptions and acceptance criteria. Do NOT summarize or truncate. Copy the content verbatim if possible.
- Acceptance criteria with multiple points should be preserved as a newline-separated list
- Preserve the order from the original plan
- If the plan has no clear phase structure, create logical groupings"""

        # Build the user message with optional custom instructions
        user_message = plan_content
        if body.custom_prompt:
            user_message = f"ADDITIONAL INSTRUCTIONS: {body.custom_prompt}\n\n---\n\n{plan_content}"

        try:
            response = await client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=16384,
                system=parse_system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )

            # Log token usage
            _input = response.usage.input_tokens
            _output = response.usage.output_tokens
            await _log_portal_tokens(
                user_id=user_uuid,
                model="claude-sonnet-4-20250514",
                input_tokens=_input,
                output_tokens=_output,
            )

            # Check if response was truncated
            if response.stop_reason == "max_tokens":
                logger.error("plan_parse_truncated", plan_length=len(plan_content), stop_reason=response.stop_reason)
                raise ValueError("LLM response was truncated (max_tokens reached). Plan may be too large.")

            # Extract JSON from response
            response_text = response.content[0].text
            # Try to extract JSON from markdown code blocks if present
            json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response_text, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group(1))
            else:
                # Strip any leading/trailing whitespace or text before the JSON
                stripped = response_text.strip()
                # Find the first { to handle any preamble text
                brace_idx = stripped.find("{")
                if brace_idx > 0:
                    stripped = stripped[brace_idx:]
                parsed = json.loads(stripped)

        except ValueError:
            raise
        except Exception as e:
            preview = response_text[:500] if "response_text" in locals() else "no response"
            logger.error("plan_parse_failed", error=str(e), plan_length=len(plan_content),
                         response_preview=preview)
            raise ValueError(f"Failed to parse plan: {str(e)}")

        # 5. Store the plan as design_document for display in the portal.
        #    The actual plan file (PLAN.md) lives in the repo and is read
        #    directly by claude_code during phase execution.
        await call_tool(
            module="project_planner",
            tool_name="project_planner.update_project",
            arguments={
                "project_id": project_id,
                "design_document": plan_content,
                "status": "active",
            },
            user_id=uid,
            timeout=15.0,
        )

        # 6. Create phases and tasks
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

        # 7. Mark apply as complete
        async with factory() as session:
            await session.execute(
                sa_update(Project)
                .where(Project.id == pid, Project.user_id == user_uuid)
                .values(
                    plan_apply_status="applied",
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

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

    except HTTPException:
        # Don't overwrite status for HTTP errors (shouldn't reach here, but be safe)
        raise
    except Exception as e:
        # Persist the failure so the UI can show an error and allow retry
        async with factory() as session:
            await session.execute(
                sa_update(Project)
                .where(Project.id == pid, Project.user_id == user_uuid)
                .values(
                    plan_apply_status="failed",
                    plan_apply_error=str(e),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()
        logger.error("plan_apply_failed", project_id=project_id, error=str(e))
        raise


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
    """Start executing the next phase using the new sequential execution system."""
    uid = str(user.user_id)

    result = await call_tool(
        module="project_planner",
        tool_name="project_planner.execute_next_phase",
        arguments={
            "project_id": project_id,
            "auto_push": body.auto_push,
            "timeout": body.timeout,
        },
        user_id=uid,
        timeout=30.0,
    )

    return result.get("result", {})


@router.post("/{project_id}/start-workflow")
async def start_workflow(
    project_id: str,
    body: ExecutePhaseRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Start fully automated sequential phase execution workflow."""
    uid = str(user.user_id)

    result = await call_tool(
        module="project_planner",
        tool_name="project_planner.start_project_workflow",
        arguments={
            "project_id": project_id,
            "auto_push": body.auto_push,
            "timeout": body.timeout,
            "platform": "web",
            "platform_channel_id": uid,
        },
        user_id=uid,
        timeout=30.0,
    )

    return result.get("result", {})


@router.post("/{project_id}/cancel-workflow")
async def cancel_workflow(
    project_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Cancel an active project workflow."""
    uid = str(user.user_id)

    # Get project to find workflow_id
    project_result = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_project",
        arguments={"project_id": project_id},
        user_id=uid,
        timeout=15.0,
    )
    project_data = project_result.get("result", {})
    workflow_id = project_data.get("workflow_id")

    if not workflow_id:
        return {
            "success": False,
            "message": "No active workflow found for this project",
        }

    # Cancel scheduler workflow
    result = await call_tool(
        module="scheduler",
        tool_name="scheduler.cancel_workflow",
        arguments={"workflow_id": workflow_id},
        user_id=uid,
        timeout=15.0,
    )

    # Clear workflow_id from project directly in DB
    session_factory = get_session_factory()
    async with session_factory() as session:
        db_result = await session.execute(
            select(Project).where(
                Project.id == uuid.UUID(project_id),
                Project.user_id == uuid.UUID(uid),
            )
        )
        project = db_result.scalar_one_or_none()
        if project:
            project.workflow_id = None
            await session.commit()

    return result.get("result", {})


@router.post("/{project_id}/retry-phase")
async def retry_phase(
    project_id: str,
    body: RetryPhaseRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Reset failed tasks in a phase and restart the automated workflow."""
    uid = str(user.user_id)
    phase_id = body.phase_id

    # 1. Get tasks for the phase
    tasks_result = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_phase_tasks",
        arguments={"phase_id": phase_id},
        user_id=uid,
        timeout=15.0,
    )
    tasks = tasks_result.get("result", [])
    retryable = [t for t in tasks if t.get("status") in ("failed", "doing")]

    if not retryable:
        return {"success": False, "message": "No failed or in-progress tasks to retry"}

    # 2. Reset each retryable task to "todo"
    for task in retryable:
        await call_tool(
            module="project_planner",
            tool_name="project_planner.update_task",
            arguments={
                "task_id": task["task_id"],
                "status": "todo",
                "error_message": "",
                "claude_task_id": "",
            },
            user_id=uid,
            timeout=15.0,
        )

    # 3. Reset phase status to "in_progress"
    await call_tool(
        module="project_planner",
        tool_name="project_planner.update_phase",
        arguments={"phase_id": phase_id, "status": "in_progress"},
        user_id=uid,
        timeout=15.0,
    )

    # 4. Restart automated workflow
    result = await call_tool(
        module="project_planner",
        tool_name="project_planner.start_project_workflow",
        arguments={
            "project_id": project_id,
            "auto_push": True,
            "platform": "web",
            "platform_channel_id": uid,
        },
        user_id=uid,
        timeout=30.0,
    )

    return result.get("result", {})


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


@router.post("/{project_id}/sync-pr-status")
async def sync_pr_status(
    project_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Check merged status of PRs linked to in_review tasks and update accordingly."""
    uid = user.user_id
    pid = uuid.UUID(project_id)

    factory = get_session_factory()
    async with factory() as session:
        # Get project to find repo info
        project = await session.execute(
            select(Project).where(Project.id == pid, Project.user_id == uid)
        )
        project = project.scalar_one_or_none()
        if not project or not project.repo_owner or not project.repo_name:
            return {"synced": 0, "message": "Project has no linked repository"}

        # Find all in_review tasks with a pr_number
        tasks_result = await session.execute(
            select(ProjectTask).where(
                ProjectTask.project_id == pid,
                ProjectTask.status == "in_review",
                ProjectTask.pr_number.isnot(None),
            )
        )
        tasks = list(tasks_result.scalars().all())

        if not tasks:
            return {"synced": 0, "message": "No in_review tasks with PRs to check"}

        # Deduplicate PR numbers to minimize API calls
        pr_numbers = {t.pr_number for t in tasks}
        merged_prs: set[int] = set()

        for pr_num in pr_numbers:
            try:
                pr_result = await call_tool(
                    module="git_platform",
                    tool_name="git_platform.get_pull_request",
                    arguments={
                        "owner": project.repo_owner,
                        "repo": project.repo_name,
                        "pr_number": pr_num,
                    },
                    user_id=str(uid),
                    timeout=15.0,
                )
                pr_data = pr_result.get("result", {})
                if pr_data.get("merged_at"):
                    merged_prs.add(pr_num)
            except Exception as e:
                logger.warning("sync_pr_check_failed", pr_number=pr_num, error=str(e))

        if not merged_prs:
            return {"synced": 0, "message": "No merged PRs found"}

        # Update tasks for merged PRs
        now = datetime.now(timezone.utc)
        synced = 0
        for task in tasks:
            if task.pr_number in merged_prs:
                task.status = "done"
                task.completed_at = now
                task.updated_at = now
                synced += 1

        await session.commit()

        # Check if project is now fully done
        remaining = await session.execute(
            select(func.count(ProjectTask.id)).where(
                ProjectTask.project_id == pid,
                ProjectTask.status.notin_(["done", "failed"]),
            )
        )
        if remaining.scalar() == 0 and project.status != "completed":
            project.status = "completed"
            project.updated_at = now
            await session.commit()
            logger.info("project_completed", project_id=project_id, project_name=project.name)

        logger.info("pr_status_synced", project_id=project_id, synced=synced, merged_prs=list(merged_prs))
        return {
            "synced": synced,
            "merged_prs": list(merged_prs),
            "project_completed": project.status == "completed",
        }


@router.post("/{project_id}/sync-phase-status")
async def sync_phase_status(
    project_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Detect in_progress phases whose claude tasks have finished and finalize them."""
    uid = str(user.user_id)
    pid = uuid.UUID(project_id)
    now = datetime.now(timezone.utc)

    factory = get_session_factory()
    async with factory() as session:
        # Find all in_progress phases for this project
        phases_result = await session.execute(
            select(ProjectPhase)
            .where(ProjectPhase.project_id == pid, ProjectPhase.status == "in_progress")
            .order_by(ProjectPhase.order_index)
        )
        phases = list(phases_result.scalars().all())

        if not phases:
            return {"synced": 0}

        synced = 0
        for phase in phases:
            # Find tasks with a claude_task_id that are still "doing"
            tasks_result = await session.execute(
                select(ProjectTask).where(
                    ProjectTask.phase_id == phase.id,
                    ProjectTask.status == "doing",
                    ProjectTask.claude_task_id.isnot(None),
                )
            )
            doing_tasks = list(tasks_result.scalars().all())

            if not doing_tasks:
                continue

            # Check if the claude task has finished
            claude_task_id = doing_tasks[0].claude_task_id
            try:
                task_status_result = await call_tool(
                    module="claude_code",
                    tool_name="claude_code.task_status",
                    arguments={"task_id": claude_task_id},
                    user_id=uid,
                    timeout=15.0,
                )
                status = task_status_result.get("result", {}).get("status")
            except Exception:
                continue

            if status not in ("completed", "failed", "timed_out", "cancelled"):
                continue  # still running

            # Claude task is done but phase is stuck — try complete_phase
            try:
                await call_tool(
                    module="project_planner",
                    tool_name="project_planner.complete_phase",
                    arguments={
                        "phase_id": str(phase.id),
                        "claude_task_id": claude_task_id,
                    },
                    user_id=uid,
                    timeout=30.0,
                )
                synced += 1
            except Exception as e:
                # complete_phase may fail (e.g. no PR possible) — just mark tasks done
                logger.warning(
                    "sync_complete_phase_failed",
                    phase_id=str(phase.id),
                    error=str(e),
                )
                for task in doing_tasks:
                    task.status = "done" if status == "completed" else "failed"
                    task.completed_at = now
                    task.updated_at = now
                    if status != "completed":
                        task.error_message = f"Task {status}"
                phase.status = "completed"
                phase.updated_at = now
                await session.commit()
                synced += 1

    return {"synced": synced}
