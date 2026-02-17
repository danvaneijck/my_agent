"""Skills module tool implementations — CRUD and attachment operations."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import structlog
from jinja2 import Template, TemplateSyntaxError, UndefinedError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.models.project import Project
from shared.models.project_skill import ProjectSkill
from shared.models.project_task import ProjectTask
from shared.models.task_skill import TaskSkill
from shared.models.user_skill import UserSkill

logger = structlog.get_logger()


def _skill_to_dict(s: UserSkill) -> dict:
    """Convert UserSkill model to dictionary."""
    tags = json.loads(s.tags) if s.tags else []
    return {
        "skill_id": str(s.id),
        "user_id": str(s.user_id),
        "name": s.name,
        "description": s.description,
        "category": s.category,
        "content": s.content,
        "language": s.language,
        "tags": tags,
        "is_template": s.is_template,
        "created_at": s.created_at.isoformat(),
        "updated_at": s.updated_at.isoformat(),
    }


def _project_skill_to_dict(ps: ProjectSkill, skill: UserSkill) -> dict:
    """Convert ProjectSkill junction to dictionary with skill details."""
    return {
        "project_skill_id": str(ps.id),
        "project_id": str(ps.project_id),
        "skill_id": str(ps.skill_id),
        "order_index": ps.order_index,
        "applied_at": ps.applied_at.isoformat(),
        "skill": _skill_to_dict(skill),
    }


def _task_skill_to_dict(ts: TaskSkill, skill: UserSkill) -> dict:
    """Convert TaskSkill junction to dictionary with skill details."""
    return {
        "task_skill_id": str(ts.id),
        "task_id": str(ts.task_id),
        "skill_id": str(ts.skill_id),
        "order_index": ts.order_index,
        "applied_at": ts.applied_at.isoformat(),
        "skill": _skill_to_dict(skill),
    }


class SkillsTools:
    """Tools for managing skills and skill attachments."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    # ── Skill CRUD ──────────────────────────────────────────────────────

    async def create_skill(
        self,
        name: str,
        content: str,
        description: str | None = None,
        category: str | None = None,
        language: str | None = None,
        tags: list[str] | None = None,
        is_template: bool = False,
        user_id: str | None = None,
    ) -> dict:
        """Create a new skill."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        skill_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        # Convert tags list to JSON string
        tags_json = json.dumps(tags) if tags else "[]"

        async with self.session_factory() as session:
            # Check for duplicate name
            result = await session.execute(
                select(UserSkill).where(
                    UserSkill.user_id == uid,
                    UserSkill.name == name,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                raise ValueError(f"Skill with name '{name}' already exists")

            skill = UserSkill(
                id=skill_id,
                user_id=uid,
                name=name,
                description=description,
                category=category,
                content=content,
                language=language,
                tags=tags_json,
                is_template=is_template,
                created_at=now,
                updated_at=now,
            )
            session.add(skill)
            await session.commit()

        logger.info("skill_created", skill_id=str(skill_id), user_id=user_id, name=name)
        return {
            "skill_id": str(skill_id),
            "created_at": now.isoformat(),
        }

    async def list_skills(
        self,
        category_filter: str | None = None,
        tag_filter: str | None = None,
        search_query: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """List all skills for the user with optional filters."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)

        async with self.session_factory() as session:
            query = select(UserSkill).where(UserSkill.user_id == uid)

            # Apply category filter
            if category_filter:
                query = query.where(UserSkill.category == category_filter)

            # Apply search query (name or description)
            if search_query:
                search_pattern = f"%{search_query}%"
                query = query.where(
                    (UserSkill.name.ilike(search_pattern)) |
                    (UserSkill.description.ilike(search_pattern))
                )

            # Order by created_at descending (newest first)
            query = query.order_by(UserSkill.created_at.desc())

            result = await session.execute(query)
            skills = result.scalars().all()

            # Filter by tag if provided (client-side since tags are JSON)
            if tag_filter:
                skills = [
                    s for s in skills
                    if tag_filter in json.loads(s.tags or "[]")
                ]

        skills_list = [_skill_to_dict(s) for s in skills]
        logger.info("skills_listed", user_id=user_id, count=len(skills_list))
        return {"skills": skills_list, "count": len(skills_list)}

    async def get_skill(
        self,
        skill_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Get full details for a single skill."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        sid = uuid.UUID(skill_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(UserSkill).where(
                    UserSkill.id == sid,
                    UserSkill.user_id == uid,
                )
            )
            skill = result.scalar_one_or_none()
            if not skill:
                raise ValueError(f"Skill {skill_id} not found or not owned by user")

        return _skill_to_dict(skill)

    async def update_skill(
        self,
        skill_id: str,
        name: str | None = None,
        content: str | None = None,
        description: str | None = None,
        category: str | None = None,
        language: str | None = None,
        tags: list[str] | None = None,
        is_template: bool | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Update skill fields."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        sid = uuid.UUID(skill_id)
        now = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            result = await session.execute(
                select(UserSkill).where(
                    UserSkill.id == sid,
                    UserSkill.user_id == uid,
                )
            )
            skill = result.scalar_one_or_none()
            if not skill:
                raise ValueError(f"Skill {skill_id} not found or not owned by user")

            # Check for name uniqueness if changing name
            if name and name != skill.name:
                result = await session.execute(
                    select(UserSkill).where(
                        UserSkill.user_id == uid,
                        UserSkill.name == name,
                        UserSkill.id != sid,
                    )
                )
                existing = result.scalar_one_or_none()
                if existing:
                    raise ValueError(f"Skill with name '{name}' already exists")
                skill.name = name

            # Update fields
            if content is not None:
                skill.content = content
            if description is not None:
                skill.description = description
            if category is not None:
                skill.category = category
            if language is not None:
                skill.language = language
            if tags is not None:
                skill.tags = json.dumps(tags)
            if is_template is not None:
                skill.is_template = is_template

            skill.updated_at = now
            await session.commit()

        logger.info("skill_updated", skill_id=skill_id, user_id=user_id)
        return {"success": True, "updated_at": now.isoformat()}

    async def delete_skill(
        self,
        skill_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Delete a skill (CASCADE deletes attachments)."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        sid = uuid.UUID(skill_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(UserSkill).where(
                    UserSkill.id == sid,
                    UserSkill.user_id == uid,
                )
            )
            skill = result.scalar_one_or_none()
            if not skill:
                raise ValueError(f"Skill {skill_id} not found or not owned by user")

            await session.delete(skill)
            await session.commit()

        logger.info("skill_deleted", skill_id=skill_id, user_id=user_id)
        return {"success": True}

    # ── Project skill attachment ────────────────────────────────────────

    async def attach_skill_to_project(
        self,
        project_id: str,
        skill_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Attach a skill to a project."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        pid = uuid.UUID(project_id)
        sid = uuid.UUID(skill_id)
        now = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            # Verify project ownership
            result = await session.execute(
                select(Project).where(
                    Project.id == pid,
                    Project.user_id == uid,
                )
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {project_id} not found or not owned by user")

            # Verify skill ownership
            result = await session.execute(
                select(UserSkill).where(
                    UserSkill.id == sid,
                    UserSkill.user_id == uid,
                )
            )
            skill = result.scalar_one_or_none()
            if not skill:
                raise ValueError(f"Skill {skill_id} not found or not owned by user")

            # Check if already attached
            result = await session.execute(
                select(ProjectSkill).where(
                    ProjectSkill.project_id == pid,
                    ProjectSkill.skill_id == sid,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                raise ValueError(f"Skill {skill_id} is already attached to project {project_id}")

            # Get max order_index for this project
            result = await session.execute(
                select(ProjectSkill).where(ProjectSkill.project_id == pid)
            )
            existing_attachments = result.scalars().all()
            max_order = max([a.order_index for a in existing_attachments], default=-1)

            # Create attachment
            attachment = ProjectSkill(
                id=uuid.uuid4(),
                project_id=pid,
                skill_id=sid,
                order_index=max_order + 1,
                applied_at=now,
            )
            session.add(attachment)
            await session.commit()

        logger.info("skill_attached_to_project", project_id=project_id, skill_id=skill_id, user_id=user_id)
        return {"success": True, "applied_at": now.isoformat()}

    async def detach_skill_from_project(
        self,
        project_id: str,
        skill_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Detach a skill from a project."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        pid = uuid.UUID(project_id)
        sid = uuid.UUID(skill_id)

        async with self.session_factory() as session:
            # Verify project ownership
            result = await session.execute(
                select(Project).where(
                    Project.id == pid,
                    Project.user_id == uid,
                )
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {project_id} not found or not owned by user")

            # Find and delete attachment
            result = await session.execute(
                select(ProjectSkill).where(
                    ProjectSkill.project_id == pid,
                    ProjectSkill.skill_id == sid,
                )
            )
            attachment = result.scalar_one_or_none()
            if not attachment:
                raise ValueError(f"Skill {skill_id} is not attached to project {project_id}")

            await session.delete(attachment)
            await session.commit()

        logger.info("skill_detached_from_project", project_id=project_id, skill_id=skill_id, user_id=user_id)
        return {"success": True}

    async def get_project_skills(
        self,
        project_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Get all skills attached to a project."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        pid = uuid.UUID(project_id)

        async with self.session_factory() as session:
            # Verify project ownership
            result = await session.execute(
                select(Project).where(
                    Project.id == pid,
                    Project.user_id == uid,
                )
            )
            project = result.scalar_one_or_none()
            if not project:
                raise ValueError(f"Project {project_id} not found or not owned by user")

            # Get all attachments with skill details
            result = await session.execute(
                select(ProjectSkill, UserSkill).join(
                    UserSkill, ProjectSkill.skill_id == UserSkill.id
                ).where(ProjectSkill.project_id == pid)
                .order_by(ProjectSkill.order_index)
            )
            attachments = result.all()

        skills_list = [_project_skill_to_dict(ps, skill) for ps, skill in attachments]
        return {"skills": skills_list, "count": len(skills_list)}

    # ── Task skill attachment ───────────────────────────────────────────

    async def attach_skill_to_task(
        self,
        task_id: str,
        skill_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Attach a skill to a task."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        tid = uuid.UUID(task_id)
        sid = uuid.UUID(skill_id)
        now = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            # Verify task ownership
            result = await session.execute(
                select(ProjectTask).where(
                    ProjectTask.id == tid,
                    ProjectTask.user_id == uid,
                )
            )
            task = result.scalar_one_or_none()
            if not task:
                raise ValueError(f"Task {task_id} not found or not owned by user")

            # Verify skill ownership
            result = await session.execute(
                select(UserSkill).where(
                    UserSkill.id == sid,
                    UserSkill.user_id == uid,
                )
            )
            skill = result.scalar_one_or_none()
            if not skill:
                raise ValueError(f"Skill {skill_id} not found or not owned by user")

            # Check if already attached
            result = await session.execute(
                select(TaskSkill).where(
                    TaskSkill.task_id == tid,
                    TaskSkill.skill_id == sid,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                raise ValueError(f"Skill {skill_id} is already attached to task {task_id}")

            # Get max order_index for this task
            result = await session.execute(
                select(TaskSkill).where(TaskSkill.task_id == tid)
            )
            existing_attachments = result.scalars().all()
            max_order = max([a.order_index for a in existing_attachments], default=-1)

            # Create attachment
            attachment = TaskSkill(
                id=uuid.uuid4(),
                task_id=tid,
                skill_id=sid,
                order_index=max_order + 1,
                applied_at=now,
            )
            session.add(attachment)
            await session.commit()

        logger.info("skill_attached_to_task", task_id=task_id, skill_id=skill_id, user_id=user_id)
        return {"success": True, "applied_at": now.isoformat()}

    async def detach_skill_from_task(
        self,
        task_id: str,
        skill_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Detach a skill from a task."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        tid = uuid.UUID(task_id)
        sid = uuid.UUID(skill_id)

        async with self.session_factory() as session:
            # Verify task ownership
            result = await session.execute(
                select(ProjectTask).where(
                    ProjectTask.id == tid,
                    ProjectTask.user_id == uid,
                )
            )
            task = result.scalar_one_or_none()
            if not task:
                raise ValueError(f"Task {task_id} not found or not owned by user")

            # Find and delete attachment
            result = await session.execute(
                select(TaskSkill).where(
                    TaskSkill.task_id == tid,
                    TaskSkill.skill_id == sid,
                )
            )
            attachment = result.scalar_one_or_none()
            if not attachment:
                raise ValueError(f"Skill {skill_id} is not attached to task {task_id}")

            await session.delete(attachment)
            await session.commit()

        logger.info("skill_detached_from_task", task_id=task_id, skill_id=skill_id, user_id=user_id)
        return {"success": True}

    async def get_task_skills(
        self,
        task_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Get all skills attached to a task."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        tid = uuid.UUID(task_id)

        async with self.session_factory() as session:
            # Verify task ownership
            result = await session.execute(
                select(ProjectTask).where(
                    ProjectTask.id == tid,
                    ProjectTask.user_id == uid,
                )
            )
            task = result.scalar_one_or_none()
            if not task:
                raise ValueError(f"Task {task_id} not found or not owned by user")

            # Get all attachments with skill details
            result = await session.execute(
                select(TaskSkill, UserSkill).join(
                    UserSkill, TaskSkill.skill_id == UserSkill.id
                ).where(TaskSkill.task_id == tid)
                .order_by(TaskSkill.order_index)
            )
            attachments = result.all()

        skills_list = [_task_skill_to_dict(ts, skill) for ts, skill in attachments]
        return {"skills": skills_list, "count": len(skills_list)}

    # ── Template rendering ──────────────────────────────────────────────

    async def render_skill(
        self,
        skill_id: str,
        variables: dict | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Render a template skill with variable substitution."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        sid = uuid.UUID(skill_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(UserSkill).where(
                    UserSkill.id == sid,
                    UserSkill.user_id == uid,
                )
            )
            skill = result.scalar_one_or_none()
            if not skill:
                raise ValueError(f"Skill {skill_id} not found or not owned by user")

        # Render template if is_template, otherwise return content as-is
        if skill.is_template:
            try:
                template = Template(skill.content)
                rendered = template.render(**(variables or {}))
            except TemplateSyntaxError as e:
                raise ValueError(f"Template syntax error: {e}")
            except UndefinedError as e:
                raise ValueError(f"Undefined variable in template: {e}")
            except Exception as e:
                raise ValueError(f"Template rendering error: {e}")
        else:
            rendered = skill.content

        logger.info("skill_rendered", skill_id=skill_id, user_id=user_id, is_template=skill.is_template)
        return {
            "skill_id": str(skill.id),
            "name": skill.name,
            "is_template": skill.is_template,
            "rendered_content": rendered,
        }
