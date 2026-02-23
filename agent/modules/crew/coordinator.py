"""Crew coordinator — handles wave dispatch, merge integration, and member lifecycle."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import httpx
import redis.asyncio as aioredis
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import get_service_auth_headers
from shared.config import get_settings
from shared.database import get_session_factory
from shared.models.crew_context_entry import CrewContextEntry
from shared.models.crew_member import CrewMember
from shared.models.crew_session import CrewSession
from shared.models.project import Project
from shared.models.project_task import ProjectTask
from modules.crew.prompts import build_agent_prompt
from modules.crew.waves import compute_waves

logger = structlog.get_logger()

_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        settings = get_settings()
        _redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return _redis


async def _publish_event(session_id: uuid.UUID, event: dict) -> None:
    """Publish a crew event to Redis pub/sub."""
    r = await _get_redis()
    event["timestamp"] = datetime.now(timezone.utc).isoformat()
    await r.publish(f"crew:{session_id}:events", json.dumps(event))


async def _call_module(module: str, tool_name: str, arguments: dict, user_id: str, timeout: float = 30.0) -> dict:
    """Call a module tool via its /execute endpoint."""
    settings = get_settings()
    base_url = settings.module_services.get(module)
    if not base_url:
        raise RuntimeError(f"Unknown module: {module}")

    payload = {"tool_name": tool_name, "arguments": arguments, "user_id": user_id}
    headers = get_service_auth_headers()
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(f"{base_url}/execute", json=payload, headers=headers)
        resp.raise_for_status()
    result = resp.json()
    if not result.get("success"):
        raise RuntimeError(f"Tool {tool_name} failed: {result.get('error', 'unknown')}")
    return result.get("result", {})


async def analyze_and_compute_waves(
    session: CrewSession,
    db: AsyncSession,
) -> list[list[str]]:
    """Load project tasks and compute the wave plan."""
    if not session.project_id:
        raise ValueError("Crew session has no linked project")

    result = await db.execute(
        select(ProjectTask)
        .where(
            ProjectTask.project_id == session.project_id,
            ProjectTask.status.in_(["todo", "doing"]),
        )
        .order_by(ProjectTask.order_index)
    )
    tasks = list(result.scalars().all())

    if not tasks:
        raise ValueError("No pending tasks found in the project")

    task_dicts = [
        {
            "task_id": str(t.id),
            "depends_on": t.depends_on or [],
            "status": t.status,
        }
        for t in tasks
    ]

    return compute_waves(task_dicts)


async def dispatch_wave(
    session_id: uuid.UUID,
    user_id: str,
    *,
    platform: str = "web",
    platform_channel_id: str | None = None,
) -> dict:
    """Dispatch the next wave of agents for a crew session."""
    factory = get_session_factory()
    async with factory() as db:
        session = await db.get(CrewSession, session_id)
        if not session:
            raise ValueError(f"Crew session not found: {session_id}")
        if session.status not in ("running", "configuring"):
            raise ValueError(f"Session is {session.status}, cannot dispatch")

        # Get project info
        project = await db.get(Project, session.project_id) if session.project_id else None

        # Get all project tasks
        result = await db.execute(
            select(ProjectTask)
            .where(ProjectTask.project_id == session.project_id)
            .order_by(ProjectTask.order_index)
        )
        all_tasks = list(result.scalars().all())

        # Find completed task IDs
        completed_ids = {str(t.id) for t in all_tasks if t.status in ("done", "in_review")}

        # Find tasks ready for this wave (deps satisfied, status=todo)
        ready_tasks = [
            t for t in all_tasks
            if t.status == "todo" and set(t.depends_on or []).issubset(completed_ids)
        ]

        if not ready_tasks:
            # Check if everything is done
            pending = [t for t in all_tasks if t.status in ("todo", "doing")]
            if not pending:
                session.status = "completed"
                session.updated_at = datetime.now(timezone.utc)
                await db.commit()
                await _publish_event(session_id, {
                    "event": "session_completed",
                    "status": "completed",
                })
                return {"status": "completed", "message": "All tasks done"}
            else:
                return {"status": "waiting", "message": "No tasks ready yet, waiting for dependencies"}

        # Limit to max_agents
        wave_tasks = ready_tasks[:session.max_agents]
        wave_number = session.current_wave

        # Get context board entries
        ctx_result = await db.execute(
            select(CrewContextEntry)
            .where(CrewContextEntry.session_id == session_id)
            .order_by(CrewContextEntry.created_at)
        )
        context_entries = [
            {
                "entry_type": e.entry_type,
                "title": e.title,
                "content": e.content,
            }
            for e in ctx_result.scalars().all()
        ]

        dispatched_members = []

        for i, task in enumerate(wave_tasks):
            branch = f"crew/{str(session_id)[:8]}/wave-{wave_number}/task-{i}"

            # Determine role from config
            role_assignments = session.config.get("role_assignments", {})
            role = role_assignments.get(str(task.id))

            # Build prompt
            prompt = build_agent_prompt(
                task_title=task.title,
                task_description=task.description,
                acceptance_criteria=task.acceptance_criteria,
                role=role,
                context_entries=context_entries,
                project_name=project.name if project else None,
                design_document=project.design_document if project else None,
                branch_name=branch,
                wave_number=wave_number,
                total_waves=session.total_waves,
            )

            # Launch claude_code task
            task_args: dict = {
                "prompt": prompt,
                "mode": "execute",
                "auto_push": session.config.get("auto_push", True),
                "timeout": session.config.get("timeout", 1800),
            }
            if session.repo_url:
                task_args["repo_url"] = session.repo_url
                task_args["branch"] = branch
                task_args["source_branch"] = session.integration_branch

            claude_result = await _call_module(
                "claude_code", "claude_code.run_task", task_args, user_id
            )
            claude_task_id = claude_result.get("task_id")

            # Create crew member record
            member = CrewMember(
                id=uuid.uuid4(),
                session_id=session_id,
                role=role,
                branch_name=branch,
                claude_task_id=claude_task_id,
                task_id=task.id,
                task_title=task.title,
                status="working",
                wave_number=wave_number,
                started_at=datetime.now(timezone.utc),
            )
            db.add(member)

            # Update project task status
            task.status = "doing"
            task.started_at = datetime.now(timezone.utc)
            task.claude_task_id = claude_task_id
            task.branch_name = branch

            # Create scheduler job to monitor this member
            # Use unique workflow_id per member to avoid sibling cancellation
            channel_id = platform_channel_id or user_id
            scheduler_args = {
                "job_type": "poll_module",
                "check_config": {
                    "module": "claude_code",
                    "tool": "claude_code.task_status",
                    "args": {"task_id": claude_task_id},
                    "success_field": "status",
                    "success_values": ["completed", "failed", "timed_out", "cancelled"],
                },
                "on_success_message": (
                    f"[Crew] Agent completed. "
                    f"Call crew.advance_session with "
                    f"session_id={session_id} "
                    f"member_id={member.id} "
                    f"claude_task_id={claude_task_id}"
                ),
                "on_complete": "resume_conversation",
                "workflow_id": str(uuid.uuid4()),
                "interval_seconds": 30,
                "max_attempts": 240,
                "platform": platform,
                "platform_channel_id": channel_id,
            }
            try:
                await _call_module("scheduler", "scheduler.add_job", scheduler_args, user_id)
            except Exception as e:
                logger.error("scheduler_job_failed", member_id=str(member.id), error=str(e))

            dispatched_members.append({
                "member_id": str(member.id),
                "task_title": task.title,
                "branch": branch,
                "claude_task_id": claude_task_id,
                "role": role,
            })

            await _publish_event(session_id, {
                "event": "member_started",
                "member_id": str(member.id),
                "task_title": task.title,
                "role": role,
                "wave": wave_number,
                "branch": branch,
            })

        # Update session state
        session.status = "running"
        session.current_wave = wave_number
        session.updated_at = datetime.now(timezone.utc)
        await db.commit()

        await _publish_event(session_id, {
            "event": "wave_dispatched",
            "wave": wave_number,
            "agents_count": len(dispatched_members),
        })

        return {
            "wave": wave_number,
            "dispatched": dispatched_members,
            "total_in_wave": len(dispatched_members),
        }


async def on_member_complete(
    session_id: uuid.UUID,
    member_id: uuid.UUID,
    claude_task_id: str,
    user_id: str,
    *,
    platform: str = "web",
    platform_channel_id: str | None = None,
) -> dict:
    """Handle a crew member completing its task."""
    factory = get_session_factory()
    async with factory() as db:
        session = await db.get(CrewSession, session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        member = await db.get(CrewMember, member_id)
        if not member:
            raise ValueError(f"Member not found: {member_id}")

        # Get claude_code task status
        try:
            task_status = await _call_module(
                "claude_code", "claude_code.task_status",
                {"task_id": claude_task_id}, user_id
            )
        except Exception as e:
            task_status = {"status": "failed", "error": str(e)}

        status = task_status.get("status", "failed")
        now = datetime.now(timezone.utc)

        if status == "completed":
            member.status = "merging"
            await db.commit()

            await _publish_event(session_id, {
                "event": "member_merging",
                "member_id": str(member_id),
                "task_title": member.task_title,
                "branch": member.branch_name,
            })

            # Attempt merge into integration branch
            merge_result = await _merge_branch(
                session, member, user_id
            )

            if merge_result.get("success"):
                member.status = "completed"
                member.completed_at = now

                # Update project task
                if member.task_id:
                    task = await db.get(ProjectTask, member.task_id)
                    if task:
                        task.status = "done"
                        task.completed_at = now

                # Post merge result to context board
                db.add(CrewContextEntry(
                    id=uuid.uuid4(),
                    session_id=session_id,
                    member_id=member_id,
                    entry_type="merge_result",
                    title=f"Merged: {member.task_title}",
                    content=f"Branch `{member.branch_name}` merged into `{session.integration_branch}` successfully.",
                ))
            else:
                member.status = "failed"
                member.completed_at = now
                member.error_message = merge_result.get("error", "Merge failed")

                if member.task_id:
                    task = await db.get(ProjectTask, member.task_id)
                    if task:
                        task.status = "failed"
                        task.completed_at = now
                        task.error_message = f"Merge conflict: {merge_result.get('error', '')}"

                db.add(CrewContextEntry(
                    id=uuid.uuid4(),
                    session_id=session_id,
                    member_id=member_id,
                    entry_type="blocker",
                    title=f"Merge conflict: {member.task_title}",
                    content=merge_result.get("error", "Unknown merge error"),
                ))
        else:
            # Task failed/timed_out/cancelled
            member.status = "failed"
            member.completed_at = now
            member.error_message = task_status.get("error", f"Task {status}")

            if member.task_id:
                task = await db.get(ProjectTask, member.task_id)
                if task:
                    task.status = "failed"
                    task.completed_at = now
                    task.error_message = member.error_message

        await db.commit()

        await _publish_event(session_id, {
            "event": "member_completed",
            "member_id": str(member_id),
            "task_title": member.task_title,
            "status": member.status,
        })

        # Check if all members in current wave are done
        wave_result = await db.execute(
            select(CrewMember).where(
                CrewMember.session_id == session_id,
                CrewMember.wave_number == session.current_wave,
                CrewMember.status.in_(["working", "merging"]),
            )
        )
        still_working = list(wave_result.scalars().all())

        if not still_working:
            # Wave complete — dispatch next
            await _publish_event(session_id, {
                "event": "wave_completed",
                "wave": session.current_wave,
            })

            session.current_wave += 1
            session.updated_at = now
            await db.commit()

            # Try dispatching next wave
            next_result = await dispatch_wave(
                session_id, user_id,
                platform=platform,
                platform_channel_id=platform_channel_id,
            )

            if next_result.get("status") == "completed":
                # Create final PR if repo configured
                if session.repo_url and session.project_id:
                    try:
                        project = await db.get(Project, session.project_id)
                        if project and project.repo_owner and project.repo_name:
                            await _call_module(
                                "git_platform",
                                "git_platform.create_pull_request",
                                {
                                    "owner": project.repo_owner,
                                    "repo": project.repo_name,
                                    "title": f"[Crew] {session.name}",
                                    "head": session.integration_branch,
                                    "base": session.source_branch,
                                    "body": f"Multi-agent crew session completed.\n\nAll waves finished successfully.",
                                },
                                user_id,
                            )
                    except Exception as e:
                        logger.warning("final_pr_creation_failed", error=str(e))

                await _publish_event(session_id, {
                    "event": "session_completed",
                    "status": "completed",
                })

            return {
                "member_status": member.status,
                "wave_complete": True,
                "next_wave": next_result,
            }

        return {
            "member_status": member.status,
            "wave_complete": False,
            "remaining_in_wave": len(still_working),
        }


async def _merge_branch(
    session: CrewSession,
    member: CrewMember,
    user_id: str,
) -> dict:
    """Merge a member's branch into the integration branch using a claude_code task."""
    merge_prompt = (
        f"Merge the branch `{member.branch_name}` into `{session.integration_branch}`.\n\n"
        f"Steps:\n"
        f"1. `git fetch origin`\n"
        f"2. `git checkout {session.integration_branch}` (create from `{session.source_branch}` if it doesn't exist)\n"
        f"3. `git merge origin/{member.branch_name} --no-edit`\n"
        f"4. If there are merge conflicts, resolve them intelligently:\n"
        f"   - Keep both sides' changes where possible\n"
        f"   - For code conflicts, merge the logic from both branches\n"
        f"   - Run any available tests after resolving\n"
        f"5. `git push origin {session.integration_branch}`\n\n"
        f"If the merge is clean (no conflicts), this should be very quick."
    )

    try:
        task_args: dict = {
            "prompt": merge_prompt,
            "mode": "execute",
            "auto_push": True,
            "timeout": 300,  # 5 min max for merges
        }
        if session.repo_url:
            task_args["repo_url"] = session.repo_url
            task_args["branch"] = session.integration_branch
            task_args["source_branch"] = session.source_branch

        result = await _call_module("claude_code", "claude_code.run_task", task_args, user_id)
        merge_task_id = result.get("task_id")

        # Poll for completion (simple sync wait, max 5 min)
        import asyncio
        for _ in range(60):
            await asyncio.sleep(5)
            status = await _call_module(
                "claude_code", "claude_code.task_status",
                {"task_id": merge_task_id}, user_id
            )
            if status.get("status") in ("completed", "failed", "timed_out"):
                if status.get("status") == "completed":
                    return {"success": True}
                else:
                    return {
                        "success": False,
                        "error": status.get("error", f"Merge task {status.get('status')}"),
                    }

        return {"success": False, "error": "Merge task timed out"}

    except Exception as e:
        return {"success": False, "error": str(e)}
