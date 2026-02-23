"""Crew tools — business logic for multi-agent crew sessions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import select

from shared.database import get_session_factory
from shared.models.crew_context_entry import CrewContextEntry
from shared.models.crew_member import CrewMember
from shared.models.crew_session import CrewSession
from shared.models.project import Project
from shared.models.project_task import ProjectTask
from modules.crew.coordinator import (
    analyze_and_compute_waves,
    dispatch_wave,
    on_member_complete,
    _publish_event,
)

logger = structlog.get_logger()


class CrewTools:
    def __init__(self) -> None:
        pass

    async def create_session(
        self,
        project_id: str,
        user_id: str,
        name: str | None = None,
        max_agents: int = 4,
        role_assignments: dict | None = None,
        auto_push: bool = True,
        timeout: int = 1800,
    ) -> dict:
        """Create a new crew session linked to a project."""
        max_agents = min(max_agents, 6)
        factory = get_session_factory()
        async with factory() as db:
            # Get project info
            pid = uuid.UUID(project_id)
            project = await db.get(Project, pid)
            if not project:
                raise ValueError(f"Project not found: {project_id}")

            # Build repo URL
            repo_url = None
            if project.repo_owner and project.repo_name:
                repo_url = f"https://github.com/{project.repo_owner}/{project.repo_name}"

            session_name = name or f"Crew: {project.name}"
            integration_branch = f"crew/{project_id[:8]}/integration"

            session = CrewSession(
                id=uuid.uuid4(),
                user_id=uuid.UUID(user_id),
                project_id=pid,
                name=session_name,
                status="configuring",
                max_agents=max_agents,
                repo_url=repo_url,
                integration_branch=integration_branch,
                source_branch=project.default_branch or "main",
                config={
                    "auto_push": auto_push,
                    "timeout": timeout,
                    "role_assignments": role_assignments or {},
                },
            )

            # Compute waves from task dependencies
            try:
                waves = await analyze_and_compute_waves(session, db)
                session.total_waves = len(waves)
            except ValueError as e:
                logger.warning("wave_computation_failed", error=str(e))
                session.total_waves = 1  # Fallback: treat all tasks as one wave

            db.add(session)
            await db.commit()

            return {
                "session_id": str(session.id),
                "name": session.name,
                "status": session.status,
                "max_agents": session.max_agents,
                "total_waves": session.total_waves,
                "repo_url": repo_url,
                "integration_branch": integration_branch,
            }

    async def start_session(
        self,
        session_id: str,
        user_id: str,
        platform: str = "web",
        platform_channel_id: str | None = None,
    ) -> dict:
        """Start a crew session — dispatches wave 0."""
        sid = uuid.UUID(session_id)

        factory = get_session_factory()
        async with factory() as db:
            session = await db.get(CrewSession, sid)
            if not session:
                raise ValueError(f"Session not found: {session_id}")
            if session.status not in ("configuring", "paused"):
                raise ValueError(f"Cannot start session in {session.status} state")

            session.status = "running"
            session.current_wave = 0
            session.workflow_id = uuid.uuid4()
            session.updated_at = datetime.now(timezone.utc)
            await db.commit()

        result = await dispatch_wave(
            sid, user_id,
            platform=platform,
            platform_channel_id=platform_channel_id or user_id,
        )

        return {
            "session_id": session_id,
            "status": "running",
            "wave_result": result,
        }

    async def get_session(self, session_id: str, user_id: str) -> dict:
        """Get full session detail with members and context."""
        sid = uuid.UUID(session_id)
        factory = get_session_factory()
        async with factory() as db:
            session = await db.get(CrewSession, sid)
            if not session:
                raise ValueError(f"Session not found: {session_id}")

            # Get members
            members_result = await db.execute(
                select(CrewMember)
                .where(CrewMember.session_id == sid)
                .order_by(CrewMember.wave_number, CrewMember.created_at)
            )
            members = [
                {
                    "member_id": str(m.id),
                    "role": m.role,
                    "branch_name": m.branch_name,
                    "claude_task_id": m.claude_task_id,
                    "task_id": str(m.task_id) if m.task_id else None,
                    "task_title": m.task_title,
                    "status": m.status,
                    "wave_number": m.wave_number,
                    "error_message": m.error_message,
                    "started_at": m.started_at.isoformat() if m.started_at else None,
                    "completed_at": m.completed_at.isoformat() if m.completed_at else None,
                }
                for m in members_result.scalars().all()
            ]

            # Get context entries
            ctx_result = await db.execute(
                select(CrewContextEntry)
                .where(CrewContextEntry.session_id == sid)
                .order_by(CrewContextEntry.created_at)
            )
            context_entries = [
                {
                    "entry_id": str(e.id),
                    "member_id": str(e.member_id) if e.member_id else None,
                    "entry_type": e.entry_type,
                    "title": e.title,
                    "content": e.content,
                    "created_at": e.created_at.isoformat(),
                }
                for e in ctx_result.scalars().all()
            ]

            # Count task statuses
            completed_members = sum(1 for m in members if m["status"] == "completed")
            failed_members = sum(1 for m in members if m["status"] == "failed")
            working_members = sum(1 for m in members if m["status"] in ("working", "merging"))

            return {
                "session_id": str(session.id),
                "project_id": str(session.project_id) if session.project_id else None,
                "name": session.name,
                "status": session.status,
                "max_agents": session.max_agents,
                "repo_url": session.repo_url,
                "integration_branch": session.integration_branch,
                "source_branch": session.source_branch,
                "current_wave": session.current_wave,
                "total_waves": session.total_waves,
                "config": session.config,
                "members": members,
                "context_entries": context_entries,
                "summary": {
                    "completed": completed_members,
                    "failed": failed_members,
                    "working": working_members,
                    "total": len(members),
                },
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
            }

    async def list_sessions(
        self,
        user_id: str,
        status_filter: str | None = None,
    ) -> list[dict]:
        """List crew sessions for a user."""
        factory = get_session_factory()
        async with factory() as db:
            query = select(CrewSession).where(
                CrewSession.user_id == uuid.UUID(user_id)
            )
            if status_filter:
                query = query.where(CrewSession.status == status_filter)
            query = query.order_by(CrewSession.updated_at.desc())

            result = await db.execute(query)
            sessions = []
            for s in result.scalars().all():
                # Count members per session
                member_result = await db.execute(
                    select(CrewMember).where(CrewMember.session_id == s.id)
                )
                members = list(member_result.scalars().all())
                completed = sum(1 for m in members if m.status == "completed")

                sessions.append({
                    "session_id": str(s.id),
                    "project_id": str(s.project_id) if s.project_id else None,
                    "name": s.name,
                    "status": s.status,
                    "max_agents": s.max_agents,
                    "current_wave": s.current_wave,
                    "total_waves": s.total_waves,
                    "member_count": len(members),
                    "completed_count": completed,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                })
            return sessions

    async def pause_session(self, session_id: str, user_id: str) -> dict:
        """Pause a running crew session."""
        factory = get_session_factory()
        async with factory() as db:
            session = await db.get(CrewSession, uuid.UUID(session_id))
            if not session:
                raise ValueError(f"Session not found: {session_id}")
            if session.status != "running":
                raise ValueError(f"Cannot pause session in {session.status} state")

            session.status = "paused"
            session.updated_at = datetime.now(timezone.utc)
            await db.commit()

        await _publish_event(uuid.UUID(session_id), {
            "event": "session_paused",
        })
        return {"session_id": session_id, "status": "paused"}

    async def resume_session(
        self,
        session_id: str,
        user_id: str,
        platform: str = "web",
        platform_channel_id: str | None = None,
    ) -> dict:
        """Resume a paused crew session."""
        sid = uuid.UUID(session_id)
        factory = get_session_factory()
        async with factory() as db:
            session = await db.get(CrewSession, sid)
            if not session:
                raise ValueError(f"Session not found: {session_id}")
            if session.status != "paused":
                raise ValueError(f"Cannot resume session in {session.status} state")

            session.status = "running"
            session.updated_at = datetime.now(timezone.utc)
            await db.commit()

        result = await dispatch_wave(
            sid, user_id,
            platform=platform,
            platform_channel_id=platform_channel_id or user_id,
        )

        await _publish_event(sid, {"event": "session_resumed"})
        return {"session_id": session_id, "status": "running", "wave_result": result}

    async def cancel_session(self, session_id: str, user_id: str) -> dict:
        """Cancel a crew session and stop all running agents."""
        sid = uuid.UUID(session_id)
        factory = get_session_factory()
        async with factory() as db:
            session = await db.get(CrewSession, sid)
            if not session:
                raise ValueError(f"Session not found: {session_id}")

            # Cancel all working members
            members_result = await db.execute(
                select(CrewMember).where(
                    CrewMember.session_id == sid,
                    CrewMember.status.in_(["working", "merging"]),
                )
            )
            now = datetime.now(timezone.utc)
            for member in members_result.scalars().all():
                if member.claude_task_id:
                    try:
                        from modules.crew.coordinator import _call_module
                        await _call_module(
                            "claude_code", "claude_code.cancel_task",
                            {"task_id": member.claude_task_id}, user_id
                        )
                    except Exception as e:
                        logger.warning("cancel_member_failed", member_id=str(member.id), error=str(e))
                member.status = "failed"
                member.completed_at = now
                member.error_message = "Session cancelled"

            session.status = "failed"
            session.updated_at = now
            await db.commit()

        await _publish_event(sid, {"event": "session_cancelled"})
        return {"session_id": session_id, "status": "failed"}

    async def post_context(
        self,
        session_id: str,
        entry_type: str,
        title: str,
        content: str,
        user_id: str,
    ) -> dict:
        """Post an entry to the shared context board."""
        sid = uuid.UUID(session_id)
        factory = get_session_factory()
        async with factory() as db:
            entry = CrewContextEntry(
                id=uuid.uuid4(),
                session_id=sid,
                member_id=None,  # User-posted entries have no member
                entry_type=entry_type,
                title=title,
                content=content,
            )
            db.add(entry)
            await db.commit()

        await _publish_event(sid, {
            "event": "context_posted",
            "entry_type": entry_type,
            "title": title,
        })

        return {
            "entry_id": str(entry.id),
            "session_id": session_id,
            "entry_type": entry_type,
            "title": title,
        }

    async def get_context_board(self, session_id: str, user_id: str) -> list[dict]:
        """Get all context board entries for a session."""
        sid = uuid.UUID(session_id)
        factory = get_session_factory()
        async with factory() as db:
            result = await db.execute(
                select(CrewContextEntry)
                .where(CrewContextEntry.session_id == sid)
                .order_by(CrewContextEntry.created_at)
            )
            return [
                {
                    "entry_id": str(e.id),
                    "member_id": str(e.member_id) if e.member_id else None,
                    "entry_type": e.entry_type,
                    "title": e.title,
                    "content": e.content,
                    "created_at": e.created_at.isoformat(),
                }
                for e in result.scalars().all()
            ]

    async def advance_session(
        self,
        session_id: str,
        member_id: str,
        claude_task_id: str,
        user_id: str,
        platform: str = "web",
        platform_channel_id: str | None = None,
    ) -> dict:
        """Handle a crew member completing its task (called by scheduler)."""
        return await on_member_complete(
            session_id=uuid.UUID(session_id),
            member_id=uuid.UUID(member_id),
            claude_task_id=claude_task_id,
            user_id=user_id,
            platform=platform,
            platform_channel_id=platform_channel_id,
        )
