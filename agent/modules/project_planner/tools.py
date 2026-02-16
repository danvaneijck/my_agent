"""Project planner tool implementations — project, phase, and task management."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import httpx
import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.config import get_settings
from shared.models.project import Project
from shared.models.project_phase import ProjectPhase
from shared.models.project_task import ProjectTask

settings = get_settings()

logger = structlog.get_logger()


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a URL-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug[:max_len].rstrip("-")


def _task_to_dict(t: ProjectTask) -> dict:
    return {
        "task_id": str(t.id),
        "phase_id": str(t.phase_id),
        "project_id": str(t.project_id),
        "title": t.title,
        "description": t.description,
        "acceptance_criteria": t.acceptance_criteria,
        "order_index": t.order_index,
        "status": t.status,
        "branch_name": t.branch_name,
        "pr_number": t.pr_number,
        "issue_number": t.issue_number,
        "claude_task_id": t.claude_task_id,
        "error_message": t.error_message,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "created_at": t.created_at.isoformat(),
    }


def _phase_to_dict(p: ProjectPhase, task_counts: dict | None = None, pr_number: int | None = None) -> dict:
    d = {
        "phase_id": str(p.id),
        "project_id": str(p.project_id),
        "name": p.name,
        "description": p.description,
        "order_index": p.order_index,
        "branch_name": p.branch_name,
        "status": p.status,
        "pr_number": pr_number,
        "created_at": p.created_at.isoformat(),
    }
    if task_counts is not None:
        d["task_counts"] = task_counts
    return d


class ProjectPlannerTools:
    """Tools for managing projects, phases, and tasks."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    # ── Project CRUD ────────────────────────────────────────────────────

    async def create_project(
        self,
        name: str,
        description: str | None = None,
        design_document: str | None = None,
        repo_owner: str | None = None,
        repo_name: str | None = None,
        default_branch: str = "main",
        auto_merge: bool = False,
        phases: list[dict] | None = None,
        user_id: str | None = None,
    ) -> dict:
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        project_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # Auto-generate a project integration branch when repo info is provided
        proj_branch = f"project/{_slugify(name)}" if repo_owner and repo_name else None

        async with self.session_factory() as session:
            project = Project(
                id=project_id,
                user_id=uid,
                name=name,
                description=description,
                design_document=design_document,
                repo_owner=repo_owner,
                repo_name=repo_name,
                default_branch=default_branch,
                project_branch=proj_branch,
                auto_merge=auto_merge,
                status="planning",
                created_at=now,
                updated_at=now,
            )
            session.add(project)

            phase_count = 0
            task_count = 0

            if phases:
                for idx, phase_data in enumerate(phases):
                    phase_id = uuid.uuid4()
                    # Prefix phase branch with project branch if it exists
                    phase_suffix = f"phase/{idx}/{_slugify(phase_data['name'])}"
                    phase_branch = f"{proj_branch}/{phase_suffix}" if proj_branch else phase_suffix
                    phase = ProjectPhase(
                        id=phase_id,
                        project_id=project_id,
                        name=phase_data["name"],
                        description=phase_data.get("description"),
                        order_index=idx,
                        branch_name=phase_branch,
                        status="planned",
                        created_at=now,
                        updated_at=now,
                    )
                    session.add(phase)
                    phase_count += 1

                    for tidx, task_data in enumerate(phase_data.get("tasks", [])):
                        task_id = uuid.uuid4()
                        task = ProjectTask(
                            id=task_id,
                            phase_id=phase_id,
                            project_id=project_id,
                            user_id=uid,
                            title=task_data["title"],
                            description=task_data.get("description"),
                            acceptance_criteria=task_data.get("acceptance_criteria"),
                            order_index=tidx,
                            status="todo",
                            created_at=now,
                            updated_at=now,
                        )
                        session.add(task)
                        task_count += 1

            await session.commit()

        logger.info(
            "project_created",
            project_id=str(project_id),
            name=name,
            phases=phase_count,
            tasks=task_count,
        )
        return {
            "project_id": str(project_id),
            "name": name,
            "status": "planning",
            "project_branch": proj_branch,
            "phases_created": phase_count,
            "tasks_created": task_count,
            "message": f"Project '{name}' created with {phase_count} phases and {task_count} tasks.",
        }

    async def update_project(
        self,
        project_id: str,
        name: str | None = None,
        description: str | None = None,
        design_document: str | None = None,
        status: str | None = None,
        repo_owner: str | None = None,
        repo_name: str | None = None,
        default_branch: str | None = None,
        auto_merge: bool | None = None,
        planning_task_id: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        pid = uuid.UUID(project_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(Project).where(Project.id == pid, Project.user_id == uid)
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            if name is not None:
                project.name = name
            if description is not None:
                project.description = description
            if design_document is not None:
                project.design_document = design_document
            if status is not None:
                project.status = status
            if repo_owner is not None:
                project.repo_owner = repo_owner
            if repo_name is not None:
                project.repo_name = repo_name
            if default_branch is not None:
                project.default_branch = default_branch
            if auto_merge is not None:
                project.auto_merge = auto_merge
            if planning_task_id is not None:
                project.planning_task_id = planning_task_id

            project.updated_at = datetime.now(timezone.utc)
            await session.commit()

        return {
            "project_id": project_id,
            "status": project.status,
            "message": "Project updated.",
        }

    async def get_project(
        self,
        project_id: str,
        user_id: str | None = None,
    ) -> dict:
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        pid = uuid.UUID(project_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(Project).where(Project.id == pid, Project.user_id == uid)
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Get phases with task counts
            phases_result = await session.execute(
                select(ProjectPhase)
                .where(ProjectPhase.project_id == pid)
                .order_by(ProjectPhase.order_index)
            )
            phases = list(phases_result.scalars().all())

            phase_dicts = []
            for phase in phases:
                counts_result = await session.execute(
                    select(ProjectTask.status, func.count(ProjectTask.id))
                    .where(ProjectTask.phase_id == phase.id)
                    .group_by(ProjectTask.status)
                )
                counts = {row[0]: row[1] for row in counts_result.all()}

                # Get PR number for this phase (all tasks share the same PR)
                pr_result = await session.execute(
                    select(ProjectTask.pr_number)
                    .where(
                        ProjectTask.phase_id == phase.id,
                        ProjectTask.pr_number.isnot(None),
                    )
                    .limit(1)
                )
                pr_number = pr_result.scalar_one_or_none()

                phase_dicts.append(_phase_to_dict(phase, task_counts=counts, pr_number=pr_number))

        return {
            "project_id": str(project.id),
            "name": project.name,
            "description": project.description,
            "design_document": project.design_document,
            "repo_owner": project.repo_owner,
            "repo_name": project.repo_name,
            "default_branch": project.default_branch,
            "project_branch": project.project_branch,
            "auto_merge": project.auto_merge,
            "planning_task_id": project.planning_task_id,
            "status": project.status,
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
            "phases": phase_dicts,
        }

    async def list_projects(
        self,
        status_filter: str | None = None,
        user_id: str | None = None,
    ) -> list[dict]:
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)

        async with self.session_factory() as session:
            query = (
                select(Project)
                .where(Project.user_id == uid)
                .order_by(Project.updated_at.desc())
            )
            if status_filter:
                query = query.where(Project.status == status_filter)

            result = await session.execute(query)
            projects = list(result.scalars().all())

            project_list = []
            for p in projects:
                # Get total task counts for summary
                counts_result = await session.execute(
                    select(ProjectTask.status, func.count(ProjectTask.id))
                    .where(ProjectTask.project_id == p.id)
                    .group_by(ProjectTask.status)
                )
                counts = {row[0]: row[1] for row in counts_result.all()}
                total = sum(counts.values())
                done = counts.get("done", 0)

                project_list.append({
                    "project_id": str(p.id),
                    "name": p.name,
                    "description": p.description,
                    "repo_owner": p.repo_owner,
                    "repo_name": p.repo_name,
                    "status": p.status,
                    "auto_merge": p.auto_merge,
                    "planning_task_id": p.planning_task_id,
                    "total_tasks": total,
                    "done_tasks": done,
                    "task_counts": counts,
                    "updated_at": p.updated_at.isoformat(),
                })

        return project_list

    async def delete_project(
        self,
        project_id: str,
        user_id: str | None = None,
    ) -> dict:
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        pid = uuid.UUID(project_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(Project).where(Project.id == pid, Project.user_id == uid)
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # CASCADE will handle phases and tasks
            await session.delete(project)
            await session.commit()

        logger.info("project_deleted", project_id=project_id, user_id=user_id)
        return {"project_id": project_id, "message": "Project deleted."}

    # ── Phase management ────────────────────────────────────────────────

    async def add_phase(
        self,
        project_id: str,
        name: str,
        description: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        pid = uuid.UUID(project_id)
        now = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            # Verify project ownership and get project
            proj_result = await session.execute(
                select(Project).where(Project.id == pid, Project.user_id == uid)
            )
            project = proj_result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Get next order_index
            max_result = await session.execute(
                select(func.max(ProjectPhase.order_index))
                .where(ProjectPhase.project_id == pid)
            )
            max_idx = max_result.scalar() or -1

            phase_id = uuid.uuid4()
            order_idx = max_idx + 1
            # Prefix phase branch with project branch if it exists
            phase_suffix = f"phase/{order_idx}/{_slugify(name)}"
            phase_branch = f"{project.project_branch}/{phase_suffix}" if project.project_branch else phase_suffix
            phase = ProjectPhase(
                id=phase_id,
                project_id=pid,
                name=name,
                description=description,
                order_index=order_idx,
                branch_name=phase_branch,
                status="planned",
                created_at=now,
                updated_at=now,
            )
            session.add(phase)
            await session.commit()

        return {
            "phase_id": str(phase_id),
            "project_id": project_id,
            "name": name,
            "order_index": order_idx,
            "branch_name": phase_branch,
            "message": f"Phase '{name}' added.",
        }

    async def update_phase(
        self,
        phase_id: str,
        name: str | None = None,
        description: str | None = None,
        status: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        phid = uuid.UUID(phase_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(ProjectPhase)
                .join(Project, Project.id == ProjectPhase.project_id)
                .where(ProjectPhase.id == phid, Project.user_id == uid)
            )
            phase = result.scalar_one_or_none()
            if not phase:
                raise ValueError(f"Phase not found: {phase_id}")

            if name is not None:
                phase.name = name
            if description is not None:
                phase.description = description
            if status is not None:
                phase.status = status

            phase.updated_at = datetime.now(timezone.utc)
            await session.commit()

        return {
            "phase_id": phase_id,
            "status": phase.status,
            "message": "Phase updated.",
        }

    # ── Task management ─────────────────────────────────────────────────

    async def add_task(
        self,
        phase_id: str,
        title: str,
        description: str | None = None,
        acceptance_criteria: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        phid = uuid.UUID(phase_id)
        now = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            # Verify phase ownership
            result = await session.execute(
                select(ProjectPhase)
                .join(Project, Project.id == ProjectPhase.project_id)
                .where(ProjectPhase.id == phid, Project.user_id == uid)
            )
            phase = result.scalar_one_or_none()
            if not phase:
                raise ValueError(f"Phase not found: {phase_id}")

            # Get next order_index
            max_result = await session.execute(
                select(func.max(ProjectTask.order_index))
                .where(ProjectTask.phase_id == phid)
            )
            max_idx = max_result.scalar() or -1

            task_id = uuid.uuid4()

            task = ProjectTask(
                id=task_id,
                phase_id=phid,
                project_id=phase.project_id,
                user_id=uid,
                title=title,
                description=description,
                acceptance_criteria=acceptance_criteria,
                order_index=max_idx + 1,
                status="todo",
                created_at=now,
                updated_at=now,
            )
            session.add(task)
            await session.commit()

        return _task_to_dict(task)

    async def bulk_add_tasks(
        self,
        phase_id: str,
        tasks: list[dict],
        user_id: str | None = None,
    ) -> dict:
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        phid = uuid.UUID(phase_id)
        now = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            # Verify phase ownership
            result = await session.execute(
                select(ProjectPhase)
                .join(Project, Project.id == ProjectPhase.project_id)
                .where(ProjectPhase.id == phid, Project.user_id == uid)
            )
            phase = result.scalar_one_or_none()
            if not phase:
                raise ValueError(f"Phase not found: {phase_id}")

            # Get next order_index
            max_result = await session.execute(
                select(func.max(ProjectTask.order_index))
                .where(ProjectTask.phase_id == phid)
            )
            max_idx = max_result.scalar() or -1

            created = []
            for idx, task_data in enumerate(tasks):
                task_id = uuid.uuid4()

                task = ProjectTask(
                    id=task_id,
                    phase_id=phid,
                    project_id=phase.project_id,
                    user_id=uid,
                    title=task_data["title"],
                    description=task_data.get("description"),
                    acceptance_criteria=task_data.get("acceptance_criteria"),
                    order_index=max_idx + 1 + idx,
                    status="todo",
                    created_at=now,
                    updated_at=now,
                )
                session.add(task)
                created.append({"task_id": str(task_id), "title": task_data["title"]})

            await session.commit()

        logger.info("tasks_bulk_added", phase_id=phase_id, count=len(created))
        return {
            "phase_id": phase_id,
            "tasks_created": len(created),
            "tasks": created,
            "message": f"Added {len(created)} tasks to phase.",
        }

    async def update_task(
        self,
        task_id: str,
        title: str | None = None,
        description: str | None = None,
        acceptance_criteria: str | None = None,
        status: str | None = None,
        branch_name: str | None = None,
        pr_number: int | None = None,
        issue_number: int | None = None,
        claude_task_id: str | None = None,
        error_message: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        tid = uuid.UUID(task_id)
        now = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            result = await session.execute(
                select(ProjectTask).where(
                    ProjectTask.id == tid, ProjectTask.user_id == uid
                )
            )
            task = result.scalar_one_or_none()
            if not task:
                raise ValueError(f"Task not found: {task_id}")

            if title is not None:
                task.title = title
            if description is not None:
                task.description = description
            if acceptance_criteria is not None:
                task.acceptance_criteria = acceptance_criteria
            if status is not None:
                task.status = status
                if status == "doing" and task.started_at is None:
                    task.started_at = now
                elif status in ("done", "failed"):
                    task.completed_at = now
            if branch_name is not None:
                task.branch_name = branch_name
            if pr_number is not None:
                task.pr_number = pr_number
            if issue_number is not None:
                task.issue_number = issue_number
            if claude_task_id is not None:
                task.claude_task_id = claude_task_id
            if error_message is not None:
                task.error_message = error_message

            task.updated_at = now
            await session.commit()

        return _task_to_dict(task)

    async def get_task(
        self,
        task_id: str,
        user_id: str | None = None,
    ) -> dict:
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        tid = uuid.UUID(task_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(ProjectTask).where(
                    ProjectTask.id == tid, ProjectTask.user_id == uid
                )
            )
            task = result.scalar_one_or_none()
            if not task:
                raise ValueError(f"Task not found: {task_id}")

        return _task_to_dict(task)

    # ── Execution helpers ───────────────────────────────────────────────

    async def get_phase_tasks(
        self,
        phase_id: str,
        user_id: str | None = None,
    ) -> list[dict]:
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        phid = uuid.UUID(phase_id)

        async with self.session_factory() as session:
            # Verify ownership via join
            result = await session.execute(
                select(ProjectTask)
                .join(ProjectPhase, ProjectPhase.id == ProjectTask.phase_id)
                .join(Project, Project.id == ProjectPhase.project_id)
                .where(ProjectTask.phase_id == phid, Project.user_id == uid)
                .order_by(ProjectTask.order_index)
            )
            tasks = list(result.scalars().all())

        return [_task_to_dict(t) for t in tasks]

    async def get_next_task(
        self,
        phase_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
    ) -> dict | None:
        if not user_id:
            raise ValueError("user_id is required")
        if not phase_id and not project_id:
            raise ValueError("Either phase_id or project_id is required")

        uid = uuid.UUID(user_id)

        async with self.session_factory() as session:
            if phase_id:
                # Specific phase requested
                phid = uuid.UUID(phase_id)
                result = await session.execute(
                    select(ProjectTask)
                    .join(ProjectPhase, ProjectPhase.id == ProjectTask.phase_id)
                    .join(Project, Project.id == ProjectPhase.project_id)
                    .where(
                        ProjectTask.phase_id == phid,
                        ProjectTask.status == "todo",
                        Project.user_id == uid,
                    )
                    .order_by(ProjectTask.order_index)
                    .limit(1)
                )
                task = result.scalar_one_or_none()
            else:
                # Find earliest phase with a todo task
                pid = uuid.UUID(project_id)
                result = await session.execute(
                    select(ProjectTask)
                    .join(ProjectPhase, ProjectPhase.id == ProjectTask.phase_id)
                    .join(Project, Project.id == ProjectPhase.project_id)
                    .where(
                        ProjectTask.project_id == pid,
                        ProjectTask.status == "todo",
                        Project.user_id == uid,
                    )
                    .order_by(ProjectPhase.order_index, ProjectTask.order_index)
                    .limit(1)
                )
                task = result.scalar_one_or_none()

            if task is None:
                return None

            task_dict = _task_to_dict(task)

            # Include branch context so the LLM knows which branches to use
            phase = await session.get(ProjectPhase, task.phase_id)
            project = await session.get(Project, phase.project_id)

            # Phase branch — fall back to task's own branch_name for pre-migration projects
            phase_branch = (
                (phase.branch_name if phase else None)
                or task.branch_name
            )
            task_dict["phase_branch"] = phase_branch
            task_dict["project_branch"] = project.project_branch if project else None

            # source_branch: previous phase's branch, or project/default branch for first phase
            prev_result = await session.execute(
                select(ProjectPhase)
                .where(
                    ProjectPhase.project_id == phase.project_id,
                    ProjectPhase.order_index < phase.order_index,
                )
                .order_by(ProjectPhase.order_index.desc())
                .limit(1)
            )
            prev_phase = prev_result.scalar_one_or_none()

            if prev_phase and prev_phase.branch_name:
                task_dict["source_branch"] = prev_phase.branch_name
            else:
                task_dict["source_branch"] = (
                    project.project_branch or project.default_branch
                    if project else "main"
                )

        return task_dict

    # ── Batch execution ──────────────────────────────────────────────────

    @staticmethod
    def _build_batch_prompt(
        project_name: str,
        design_document: str | None,
        phases: list[dict],
    ) -> str:
        """Assemble a combined prompt for a single claude_code.run_task call."""
        lines: list[str] = [
            f'You are implementing a project called "{project_name}".',
            "",
            "# Project Plan",
            "",
            "There should be a PLAN.md (or plan.md) file in the root of this repository",
            "containing the full project plan. **Read it first** to understand the overall",
            "goals, architecture decisions, and how your current work fits into the",
            "bigger picture.",
            "",
        ]

        # Include inline plan as fallback in case PLAN.md is not in the repo
        if design_document:
            lines.append("If PLAN.md is not present, here is the full plan for reference:")
            lines.append("")
            lines.append("<project-plan>")
            lines.append(design_document)
            lines.append("</project-plan>")
            lines.append("")

        lines.append("---")
        lines.append("")

        # Current phase tasks to implement
        lines.append("# Your Tasks")
        lines.append("")
        lines.append("Implement ONLY the following tasks. Do not work on tasks from other phases.")
        lines.append("Commit after completing each logical unit of work with clear messages referencing the phase/task.")
        lines.append("Run any existing tests after your changes to make sure nothing is broken.")
        lines.append("")

        for phase in phases:
            lines.append(f"## {phase['name']}")
            if phase.get("description"):
                lines.append(f"\n{phase['description']}\n")
            for task in phase["tasks"]:
                lines.append(f"### Task: {task['title']}")
                if task.get("description"):
                    lines.append(f"\n{task['description']}\n")
                if task.get("acceptance_criteria"):
                    lines.append(
                        f"**Acceptance criteria:** {task['acceptance_criteria']}\n"
                    )
            lines.append("")

        lines.append("## Instructions")
        lines.append("- Read PLAN.md first for full context about the project design and goals.")
        lines.append("- Implement ONLY the tasks listed above under 'Your Tasks'.")
        lines.append("- Within each phase, implement tasks in the order listed.")
        lines.append("- Make sure all tests pass before finishing.")
        return "\n".join(lines)

    async def get_execution_plan(
        self,
        project_id: str,
        phase_ids: list[str] | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Gather all todo tasks across phases into a single execution plan."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        pid = uuid.UUID(project_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(Project).where(Project.id == pid, Project.user_id == uid)
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Load phases
            phase_query = (
                select(ProjectPhase)
                .where(ProjectPhase.project_id == pid)
                .order_by(ProjectPhase.order_index)
            )
            if phase_ids:
                phase_query = phase_query.where(
                    ProjectPhase.id.in_([uuid.UUID(p) for p in phase_ids])
                )
            phases_result = await session.execute(phase_query)
            phases = list(phases_result.scalars().all())

            if not phases:
                return {"message": "No phases found for the given filters."}

            # Build phase list with todo tasks
            phase_dicts: list[dict] = []
            all_todo_ids: list[str] = []

            for phase in phases:
                tasks_result = await session.execute(
                    select(ProjectTask)
                    .where(
                        ProjectTask.phase_id == phase.id,
                        ProjectTask.status == "todo",
                    )
                    .order_by(ProjectTask.order_index)
                )
                tasks = list(tasks_result.scalars().all())

                task_dicts = []
                for t in tasks:
                    all_todo_ids.append(str(t.id))
                    task_dicts.append({
                        "task_id": str(t.id),
                        "title": t.title,
                        "description": t.description,
                        "acceptance_criteria": t.acceptance_criteria,
                        "order_index": t.order_index,
                        "status": t.status,
                    })

                if task_dicts:
                    phase_dicts.append({
                        "phase_id": str(phase.id),
                        "name": phase.name,
                        "description": phase.description,
                        "order_index": phase.order_index,
                        "tasks": task_dicts,
                    })

            if not all_todo_ids:
                return {"message": "No todo tasks found. All tasks may already be done or in progress."}

            # Build repo URL
            repo_url = None
            if project.repo_owner and project.repo_name:
                repo_url = f"https://github.com/{project.repo_owner}/{project.repo_name}"

            # Source branch: previous phase's branch so each phase builds on the last
            first_phase = phases[0]
            prev_result = await session.execute(
                select(ProjectPhase)
                .where(
                    ProjectPhase.project_id == pid,
                    ProjectPhase.order_index < first_phase.order_index,
                )
                .order_by(ProjectPhase.order_index.desc())
                .limit(1)
            )
            prev_phase = prev_result.scalar_one_or_none()
            if prev_phase and prev_phase.branch_name:
                source_branch = prev_phase.branch_name
            else:
                source_branch = project.project_branch or project.default_branch

            branch = first_phase.branch_name or project.project_branch or project.default_branch

            prompt = self._build_batch_prompt(
                project.name, project.design_document, phase_dicts,
            )

        return {
            "project_id": str(project.id),
            "project_name": project.name,
            "repo_url": repo_url,
            "branch": branch,
            "source_branch": source_branch,
            "design_document": project.design_document,
            "total_tasks": len(all_todo_ids),
            "todo_task_ids": all_todo_ids,
            "phases": phase_dicts,
            "prompt": prompt,
        }

    async def execute_next_phase(
        self,
        project_id: str,
        auto_push: bool = True,
        timeout: int = 1800,
        user_id: str | None = None,
    ) -> dict:
        """Execute the next phase in sequence. Reuses planning task context for phase 0."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        pid = uuid.UUID(project_id)

        async with self.session_factory() as session:
            # Get project
            result = await session.execute(
                select(Project).where(Project.id == pid, Project.user_id == uid)
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Find next phase to execute (first with status="planned" or "in_progress" with todos)
            phases_result = await session.execute(
                select(ProjectPhase)
                .where(ProjectPhase.project_id == pid)
                .order_by(ProjectPhase.order_index)
            )
            phases = list(phases_result.scalars().all())

            target_phase = None
            for phase in phases:
                if phase.status == "planned" or (phase.status == "in_progress"):
                    # Check if it has todo tasks
                    tasks_result = await session.execute(
                        select(ProjectTask)
                        .where(
                            ProjectTask.phase_id == phase.id,
                            ProjectTask.status == "todo",
                        )
                        .limit(1)
                    )
                    if tasks_result.scalar_one_or_none():
                        target_phase = phase
                        break

            if not target_phase:
                return {
                    "message": "No phases left to execute. All phases are complete or have no todo tasks.",
                    "project_status": project.status,
                }

            # Get execution plan for this phase
            exec_plan = await self.get_execution_plan(
                project_id=project_id,
                phase_ids=[str(target_phase.id)],
                user_id=user_id,
            )

            if not exec_plan.get("prompt"):
                return {
                    "message": f"Phase '{target_phase.name}' has no todo tasks to execute.",
                    "phase_id": str(target_phase.id),
                }

            todo_task_ids = exec_plan.get("todo_task_ids", [])
            prompt = exec_plan.get("prompt")
            repo_url = exec_plan.get("repo_url")
            phase_branch = target_phase.branch_name

            # Source branch: previous phase's branch so each phase builds on the last
            prev_result = await session.execute(
                select(ProjectPhase)
                .where(
                    ProjectPhase.project_id == pid,
                    ProjectPhase.order_index < target_phase.order_index,
                )
                .order_by(ProjectPhase.order_index.desc())
                .limit(1)
            )
            prev_phase = prev_result.scalar_one_or_none()
            if prev_phase and prev_phase.branch_name:
                source_branch = prev_phase.branch_name
            else:
                source_branch = project.project_branch or project.default_branch

            # Determine if we should reuse planning task (phase 0 + planning_task_id exists + awaiting_input)
            use_continue_task = False
            claude_task_id = None

            if target_phase.order_index == 0 and project.planning_task_id:
                # Check planning task status via HTTP call to claude_code
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        f"{settings.module_services['claude_code']}/execute",
                        json={
                            "tool_name": "claude_code.task_status",
                            "arguments": {"task_id": project.planning_task_id},
                            "user_id": user_id,
                        }
                    )
                    if resp.status_code == 200:
                        task_data = resp.json()
                        if task_data.get("success") and task_data.get("result", {}).get("status") == "awaiting_input":
                            use_continue_task = True

            # Launch claude_code task
            if use_continue_task:
                # Continue from planning task
                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{settings.module_services['claude_code']}/execute",
                        json={
                            "tool_name": "claude_code.continue_task",
                            "arguments": {
                                "task_id": project.planning_task_id,
                                "prompt": prompt,
                                "mode": "execute",
                                "auto_push": auto_push,
                                "timeout": timeout,
                            },
                            "user_id": user_id,
                        }
                    )
                    if resp.status_code != 200:
                        raise ValueError(f"Failed to continue planning task: {resp.text}")
                    result_data = resp.json()
                    if not result_data.get("success"):
                        raise ValueError(f"Failed to continue planning task: {result_data.get('error')}")
                    claude_task_id = result_data.get("result", {}).get("task_id")
            else:
                # New task for this phase
                task_args = {
                    "prompt": prompt,
                    "mode": "execute",
                    "auto_push": auto_push,
                    "timeout": timeout,
                }
                if repo_url:
                    task_args["repo_url"] = repo_url
                    task_args["branch"] = phase_branch
                    task_args["source_branch"] = source_branch

                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{settings.module_services['claude_code']}/execute",
                        json={
                            "tool_name": "claude_code.run_task",
                            "arguments": task_args,
                            "user_id": user_id,
                        }
                    )
                    if resp.status_code != 200:
                        raise ValueError(f"Failed to start claude_code task: {resp.text}")
                    result_data = resp.json()
                    if not result_data.get("success"):
                        raise ValueError(f"Failed to start claude_code task: {result_data.get('error')}")
                    claude_task_id = result_data.get("result", {}).get("task_id")

            # Update tasks to "doing" status
            await self.bulk_update_tasks(
                task_ids=todo_task_ids,
                status="doing",
                claude_task_id=claude_task_id,
                user_id=user_id,
            )

            # Update phase to "in_progress"
            target_phase.status = "in_progress"
            target_phase.updated_at = datetime.now(timezone.utc)
            await session.commit()

            logger.info(
                "phase_execution_started",
                project_id=project_id,
                phase_id=str(target_phase.id),
                phase_name=target_phase.name,
                phase_index=target_phase.order_index,
                claude_task_id=claude_task_id,
                task_count=len(todo_task_ids),
                reused_planning_context=use_continue_task,
            )

            return {
                "phase_id": str(target_phase.id),
                "phase_name": target_phase.name,
                "phase_index": target_phase.order_index,
                "claude_task_id": claude_task_id,
                "task_count": len(todo_task_ids),
                "reused_planning_context": use_continue_task,
                "message": f"Started executing {len(todo_task_ids)} tasks in phase '{target_phase.name}'",
            }

    async def complete_phase(
        self,
        phase_id: str,
        claude_task_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Complete a phase: create PR, update task statuses, mark phase complete."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        phid = uuid.UUID(phase_id)

        async with self.session_factory() as session:
            # Get phase and project
            result = await session.execute(
                select(ProjectPhase).where(ProjectPhase.id == phid)
            )
            phase = result.scalar_one_or_none()
            if not phase:
                raise ValueError(f"Phase not found: {phase_id}")

            result = await session.execute(
                select(Project).where(Project.id == phase.project_id, Project.user_id == uid)
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError("Project not found or access denied")

            # Get all tasks for this phase with matching claude_task_id
            tasks_result = await session.execute(
                select(ProjectTask).where(
                    ProjectTask.phase_id == phid,
                    ProjectTask.claude_task_id == claude_task_id,
                )
            )
            tasks = list(tasks_result.scalars().all())

            if not tasks:
                return {
                    "success": False,
                    "message": f"No tasks found for phase {phase_id} with claude_task_id {claude_task_id}",
                }

            # Check claude_code task status
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{settings.module_services['claude_code']}/execute",
                    json={
                        "tool_name": "claude_code.task_status",
                        "arguments": {"task_id": claude_task_id},
                        "user_id": user_id,
                    }
                )
                if resp.status_code != 200:
                    raise ValueError(f"Failed to get task status: {resp.text}")
                task_data = resp.json()
                if not task_data.get("success"):
                    raise ValueError(f"Failed to get task status: {task_data.get('error')}")

                task_status_result = task_data.get("result", {})
                status = task_status_result.get("status")

            # Handle failure
            if status in ("failed", "timed_out", "cancelled"):
                error_msg = task_status_result.get("error") or f"Task {status}"
                for task in tasks:
                    task.status = "failed"
                    task.error_message = error_msg
                    task.completed_at = datetime.now(timezone.utc)
                    task.updated_at = datetime.now(timezone.utc)

                phase.status = "completed"
                phase.updated_at = datetime.now(timezone.utc)
                await session.commit()

                logger.warning(
                    "phase_failed",
                    project_id=str(project.id),
                    phase_id=phase_id,
                    claude_task_id=claude_task_id,
                    error=error_msg,
                )

                return {
                    "success": False,
                    "trigger_next": False,
                    "message": f"Phase '{phase.name}' failed: {error_msg}",
                    "phase_status": "failed",
                }

            # Handle success - create PR and update tasks
            pr_number = None
            pr_url = None

            if project.repo_owner and project.repo_name and phase.branch_name:
                # PR always targets the project branch so phases merge in order
                pr_base = project.project_branch or project.default_branch

                # Create PR via git_platform
                pr_title = f"{project.name}: {phase.name}"
                pr_body = f"## Phase: {phase.name}\n\n{phase.description or ''}\n\n### Tasks Completed:\n"
                for task in tasks:
                    pr_body += f"- {task.title}\n"

                async with httpx.AsyncClient(timeout=30.0) as client:
                    resp = await client.post(
                        f"{settings.module_services['git_platform']}/execute",
                        json={
                            "tool_name": "git_platform.create_pull_request",
                            "arguments": {
                                "owner": project.repo_owner,
                                "repo": project.repo_name,
                                "title": pr_title,
                                "head": phase.branch_name,
                                "base": pr_base,
                                "body": pr_body,
                                "draft": False,
                            },
                            "user_id": user_id,
                        }
                    )
                    if resp.status_code == 200:
                        pr_data = resp.json()
                        if pr_data.get("success"):
                            pr_result = pr_data.get("result", {})
                            pr_number = pr_result.get("pr_number")
                            pr_url = pr_result.get("url")
                    else:
                        logger.error("pr_creation_failed", status=resp.status_code, response=resp.text)

            # Update all tasks to "in_review"
            now = datetime.now(timezone.utc)
            for task in tasks:
                task.status = "in_review"
                task.completed_at = now
                task.updated_at = now
                if pr_number:
                    task.pr_number = pr_number

            # Mark phase as complete
            phase.status = "completed"
            phase.updated_at = now
            await session.commit()

            logger.info(
                "phase_completed",
                project_id=str(project.id),
                phase_id=phase_id,
                phase_name=phase.name,
                pr_number=pr_number,
                pr_url=pr_url,
                task_count=len(tasks),
            )

            return {
                "success": True,
                "trigger_next": True,
                "phase_id": phase_id,
                "phase_name": phase.name,
                "pr_number": pr_number,
                "pr_url": pr_url,
                "task_count": len(tasks),
                "message": f"Phase '{phase.name}' completed successfully. PR #{pr_number} created." if pr_number else f"Phase '{phase.name}' completed successfully.",
            }

    async def start_project_workflow(
        self,
        project_id: str,
        workflow_id: str | None = None,
        auto_push: bool = True,
        timeout: int = 1800,
        platform: str | None = None,
        platform_channel_id: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Start automated sequential phase execution with scheduler workflow chaining."""
        if not user_id:
            raise ValueError("user_id is required")
        if not platform or not platform_channel_id:
            raise ValueError("platform and platform_channel_id are required for workflow scheduling")

        uid = uuid.UUID(user_id)
        pid = uuid.UUID(project_id)

        # Generate workflow_id if not provided
        if not workflow_id:
            workflow_id = str(uuid.uuid4())

        async with self.session_factory() as session:
            # Get project
            result = await session.execute(
                select(Project).where(Project.id == pid, Project.user_id == uid)
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Store workflow_id in project
            project.workflow_id = workflow_id
            await session.commit()

        # Execute first phase
        phase_result = await self.execute_next_phase(
            project_id=project_id,
            auto_push=auto_push,
            timeout=timeout,
            user_id=user_id,
        )

        if "claude_task_id" not in phase_result:
            return {
                "success": False,
                "message": phase_result.get("message", "Failed to start first phase"),
            }

        claude_task_id = phase_result["claude_task_id"]
        phase_id = phase_result["phase_id"]
        phase_name = phase_result["phase_name"]

        # Create scheduler job to monitor this phase
        on_success_message = (
            f"Project '{project.name}' phase '{phase_name}' (phase_id: {phase_id}) "
            f"with claude_code task {claude_task_id} has completed. "
            f"Use project_planner.complete_phase(phase_id='{phase_id}', claude_task_id='{claude_task_id}') "
            f"to create the PR and update task statuses. Then check if there are more phases to execute "
            f"by calling project_planner.execute_next_phase(project_id='{project_id}'). "
            f"If another phase starts, create a new scheduler job to monitor it. "
            f"Continue until all phases are complete. Workflow ID: {workflow_id}"
        )

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{settings.module_services['scheduler']}/execute",
                json={
                    "tool_name": "scheduler.add_job",
                    "arguments": {
                        "job_type": "poll_module",
                        "check_config": {
                            "module": "claude_code",
                            "tool": "claude_code.task_status",
                            "args": {"task_id": claude_task_id},
                            "success_field": "status",
                            "success_values": ["completed", "failed", "timed_out", "cancelled"],
                        },
                        "interval_seconds": 30,
                        "max_attempts": 240,  # 2 hours max
                        "on_success_message": on_success_message,
                        "on_complete": "resume_conversation",
                        "workflow_id": workflow_id,
                        "platform": platform,
                        "platform_channel_id": platform_channel_id,
                    },
                    "user_id": user_id,
                }
            )
            if resp.status_code != 200:
                raise ValueError(f"Failed to create scheduler job: {resp.text}")
            scheduler_data = resp.json()
            if not scheduler_data.get("success"):
                raise ValueError(f"Failed to create scheduler job: {scheduler_data.get('error')}")

        logger.info(
            "project_workflow_started",
            project_id=project_id,
            workflow_id=workflow_id,
            first_phase_id=phase_id,
            first_phase_name=phase_name,
            claude_task_id=claude_task_id,
        )

        return {
            "success": True,
            "workflow_id": workflow_id,
            "project_id": project_id,
            "project_name": project.name,
            "first_phase_id": phase_id,
            "first_phase_name": phase_name,
            "claude_task_id": claude_task_id,
            "message": f"Workflow started. Executing first phase '{phase_name}'. Scheduler will auto-progress through remaining phases.",
        }

    async def bulk_update_tasks(
        self,
        task_ids: list[str],
        status: str,
        claude_task_id: str | None = None,
        error_message: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Update status on multiple tasks at once."""
        if not user_id:
            raise ValueError("user_id is required")
        if status not in ("todo", "doing", "in_review", "done", "failed"):
            raise ValueError(f"Invalid status: {status}")

        uid = uuid.UUID(user_id)
        tids = [uuid.UUID(t) for t in task_ids]
        now = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            result = await session.execute(
                select(ProjectTask).where(
                    ProjectTask.id.in_(tids),
                    ProjectTask.user_id == uid,
                )
            )
            tasks = list(result.scalars().all())

            for task in tasks:
                task.status = status
                if status == "doing" and task.started_at is None:
                    task.started_at = now
                elif status in ("done", "failed"):
                    task.completed_at = now
                if claude_task_id is not None:
                    task.claude_task_id = claude_task_id
                if error_message is not None:
                    task.error_message = error_message
                task.updated_at = now

            await session.commit()

        updated = [str(t.id) for t in tasks]
        logger.info(
            "bulk_tasks_updated",
            count=len(updated),
            status=status,
        )
        return {
            "updated_count": len(updated),
            "status": status,
            "task_ids": updated,
            "message": f"Updated {len(updated)} tasks to status '{status}'.",
        }

    # ── Reporting ───────────────────────────────────────────────────────

    async def get_project_status(
        self,
        project_id: str,
        user_id: str | None = None,
    ) -> dict:
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        pid = uuid.UUID(project_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(Project).where(Project.id == pid, Project.user_id == uid)
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Overall task counts
            counts_result = await session.execute(
                select(ProjectTask.status, func.count(ProjectTask.id))
                .where(ProjectTask.project_id == pid)
                .group_by(ProjectTask.status)
            )
            task_counts = {row[0]: row[1] for row in counts_result.all()}
            total = sum(task_counts.values())

            # Phases with status
            phases_result = await session.execute(
                select(ProjectPhase)
                .where(ProjectPhase.project_id == pid)
                .order_by(ProjectPhase.order_index)
            )
            phases = list(phases_result.scalars().all())

            # Find current phase (first non-completed)
            current_phase = None
            for p in phases:
                if p.status != "completed":
                    current_phase = {"phase_id": str(p.id), "name": p.name, "status": p.status}
                    break

            # Failed tasks
            failed_result = await session.execute(
                select(ProjectTask)
                .where(ProjectTask.project_id == pid, ProjectTask.status == "failed")
            )
            failed_tasks = [
                {"task_id": str(t.id), "title": t.title, "error": t.error_message}
                for t in failed_result.scalars().all()
            ]

        return {
            "project_id": str(project.id),
            "name": project.name,
            "status": project.status,
            "planning_task_id": project.planning_task_id,
            "total_tasks": total,
            "task_counts": task_counts,
            "current_phase": current_phase,
            "failed_tasks": failed_tasks,
            "phases": [
                {"phase_id": str(p.id), "name": p.name, "status": p.status}
                for p in phases
            ],
        }
