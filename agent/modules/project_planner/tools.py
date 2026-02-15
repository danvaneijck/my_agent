"""Project planner tool implementations — project, phase, and task management."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.models.project import Project
from shared.models.project_phase import ProjectPhase
from shared.models.project_task import ProjectTask

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


def _phase_to_dict(p: ProjectPhase, task_counts: dict | None = None) -> dict:
    d = {
        "phase_id": str(p.id),
        "project_id": str(p.project_id),
        "name": p.name,
        "description": p.description,
        "order_index": p.order_index,
        "branch_name": p.branch_name,
        "status": p.status,
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
                phase_dicts.append(_phase_to_dict(phase, task_counts=counts))

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
            "Implement ALL of the following phases and tasks in order.",
            "Commit after completing each logical unit of work with clear messages referencing the phase/task.",
            "Run any existing tests after your changes to make sure nothing is broken.",
            "",
        ]

        if design_document:
            lines.append("## Design Document\n")
            lines.append(design_document)
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
        lines.append("- Work through each phase sequentially.")
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

            branch = project.project_branch or project.default_branch
            source_branch = project.default_branch

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
