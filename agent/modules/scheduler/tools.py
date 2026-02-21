"""Scheduler module tool implementations — background job management."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.config import Settings
from shared.models.scheduled_job import ScheduledJob
from shared.models.scheduled_workflow import ScheduledWorkflow

logger = structlog.get_logger()


class SchedulerTools:
    """Tools for scheduling and managing background monitoring jobs."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], settings: Settings):
        self.session_factory = session_factory
        self.settings = settings

    async def add_job(
        self,
        job_type: str,
        check_config: dict,
        on_success_message: str,
        on_failure_message: str | None = None,
        on_complete: str = "notify",
        workflow_id: str | None = None,
        interval_seconds: int = 30,
        max_attempts: int = 120,
        max_runs: int | None = None,
        expires_at: str | None = None,
        name: str | None = None,
        description: str | None = None,
        platform: str | None = None,
        platform_channel_id: str | None = None,
        platform_thread_id: str | None = None,
        platform_server_id: str | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Create a new background monitoring job."""
        if not user_id:
            raise ValueError("user_id is required")
        if not platform or not platform_channel_id:
            raise ValueError("platform and platform_channel_id are required for notifications")

        uid = uuid.UUID(user_id)
        job_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        wf_id: uuid.UUID | None = None
        if workflow_id:
            wf_id = uuid.UUID(workflow_id)

        conv_id: uuid.UUID | None = None
        if conversation_id:
            conv_id = uuid.UUID(conversation_id)

        expires_at_dt: datetime | None = None
        if expires_at:
            expires_at_dt = datetime.fromisoformat(expires_at)
            if expires_at_dt.tzinfo is None:
                expires_at_dt = expires_at_dt.replace(tzinfo=timezone.utc)

        # Validate cron expression upfront
        if job_type == "cron":
            cron_expr = check_config.get("cron_expr", "")
            if not cron_expr:
                raise ValueError("check_config.cron_expr is required for cron jobs")
            if not croniter.is_valid(cron_expr):
                raise ValueError(f"Invalid cron expression: {cron_expr!r}")

        # For cron jobs, compute the first next_run_at from the expression
        if job_type == "cron":
            tz_name = check_config.get("timezone", "UTC")
            try:
                import zoneinfo
                tz = zoneinfo.ZoneInfo(tz_name)
                now_local = now.astimezone(tz)
                first_run = croniter(cron_expr, now_local).get_next(datetime)
                first_run_utc = first_run.astimezone(timezone.utc)
            except Exception:
                first_run_utc = now + timedelta(seconds=interval_seconds)
        else:
            first_run_utc = now + timedelta(seconds=interval_seconds)

        async with self.session_factory() as session:
            job = ScheduledJob(
                id=job_id,
                user_id=uid,
                conversation_id=conv_id,
                platform=platform,
                platform_channel_id=platform_channel_id,
                platform_thread_id=platform_thread_id,
                platform_server_id=platform_server_id,
                name=name,
                description=description,
                job_type=job_type,
                check_config=check_config,
                interval_seconds=interval_seconds,
                max_attempts=max_attempts,
                max_runs=max_runs,
                expires_at=expires_at_dt,
                attempts=0,
                consecutive_failures=0,
                runs_completed=0,
                on_success_message=on_success_message,
                on_failure_message=on_failure_message,
                on_complete=on_complete,
                workflow_id=wf_id,
                status="active",
                next_run_at=first_run_utc,
                created_at=now,
            )
            session.add(job)
            await session.commit()

        logger.info(
            "job_scheduled",
            job_id=str(job_id),
            job_type=job_type,
            on_complete=on_complete,
            workflow_id=workflow_id,
            user_id=user_id,
            interval=interval_seconds,
            max_attempts=max_attempts,
        )

        mode_desc = (
            "The conversation will resume automatically when the condition is met."
            if on_complete == "resume_conversation"
            else "I'll notify you when the condition is met."
        )

        result: dict = {
            "job_id": str(job_id),
            "workflow_id": workflow_id,
            "status": "active",
            "message": f"Job scheduled. {mode_desc}",
        }

        # For webhook jobs, communicate the endpoint URL
        if job_type == "webhook":
            result["webhook_url"] = f"{self.settings.orchestrator_url}/scheduler/webhook/{job_id}"
            result["note"] = "POST to webhook_url to trigger this job. Include X-Webhook-Signature header if a secret is configured."

        return result

    async def list_jobs(
        self,
        status_filter: str | None = None,
        workflow_id: str | None = None,
        user_id: str | None = None,
    ) -> list[dict]:
        """List scheduled jobs for the user."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)

        async with self.session_factory() as session:
            query = (
                select(ScheduledJob)
                .where(ScheduledJob.user_id == uid)
                .order_by(ScheduledJob.created_at.desc())
            )
            if status_filter:
                query = query.where(ScheduledJob.status == status_filter)
            if workflow_id:
                wf_id = uuid.UUID(workflow_id)
                query = query.where(ScheduledJob.workflow_id == wf_id)

            result = await session.execute(query)
            jobs = list(result.scalars().all())

        return [
            {
                "job_id": str(j.id),
                "name": j.name,
                "description": j.description,
                "job_type": j.job_type,
                "status": j.status,
                "on_complete": j.on_complete,
                "workflow_id": str(j.workflow_id) if j.workflow_id else None,
                "check_config": j.check_config,
                "attempts": j.attempts,
                "max_attempts": j.max_attempts,
                "runs_completed": j.runs_completed,
                "max_runs": j.max_runs,
                "interval_seconds": j.interval_seconds,
                "expires_at": j.expires_at.isoformat() if j.expires_at else None,
                "on_success_message": j.on_success_message,
                "last_result": j.last_result,
                "created_at": j.created_at.isoformat(),
                "next_run_at": j.next_run_at.isoformat() if j.next_run_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ]

    async def cancel_job(
        self,
        job_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Cancel an active scheduled job."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        jid = uuid.UUID(job_id)

        async with self.session_factory() as session:
            result = await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.id == jid,
                    ScheduledJob.user_id == uid,
                )
            )
            job = result.scalar_one_or_none()

            if not job:
                raise ValueError(f"Job not found: {job_id}")

            if job.status != "active":
                return {
                    "job_id": job_id,
                    "status": job.status,
                    "message": f"Job is already {job.status}, cannot cancel.",
                }

            job.status = "cancelled"
            job.completed_at = datetime.now(timezone.utc)
            await session.commit()

        logger.info("job_cancelled", job_id=job_id, user_id=user_id)
        return {
            "job_id": job_id,
            "status": "cancelled",
            "message": "Job has been cancelled.",
        }

    async def cancel_workflow(
        self,
        workflow_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Cancel all active jobs in a workflow."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        wf_id = uuid.UUID(workflow_id)
        now = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            result = await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.workflow_id == wf_id,
                    ScheduledJob.user_id == uid,
                    ScheduledJob.status == "active",
                )
            )
            active_jobs = list(result.scalars().all())

            for job in active_jobs:
                job.status = "cancelled"
                job.completed_at = now

            await session.commit()

        cancelled_count = len(active_jobs)
        logger.info(
            "workflow_cancelled",
            workflow_id=workflow_id,
            cancelled_count=cancelled_count,
            user_id=user_id,
        )
        return {
            "workflow_id": workflow_id,
            "cancelled_count": cancelled_count,
            "message": f"Cancelled {cancelled_count} active job(s) in workflow.",
        }

    async def create_workflow(
        self,
        name: str,
        description: str | None = None,
        platform: str | None = None,
        platform_channel_id: str | None = None,
        platform_thread_id: str | None = None,
        platform_server_id: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Create a named workflow for grouping related jobs.

        Returns the workflow_id to use when calling add_job.
        """
        if not user_id:
            raise ValueError("user_id is required")
        if not platform or not platform_channel_id:
            raise ValueError("platform and platform_channel_id are required")

        uid = uuid.UUID(user_id)
        wf_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            workflow = ScheduledWorkflow(
                id=wf_id,
                user_id=uid,
                name=name,
                description=description,
                platform=platform,
                platform_channel_id=platform_channel_id,
                platform_thread_id=platform_thread_id,
                platform_server_id=platform_server_id,
                status="active",
                created_at=now,
            )
            session.add(workflow)
            await session.commit()

        logger.info("workflow_created", workflow_id=str(wf_id), name=name, user_id=user_id)
        return {
            "workflow_id": str(wf_id),
            "name": name,
            "status": "active",
            "message": f"Workflow '{name}' created. Use workflow_id when calling add_job to group jobs.",
        }

    async def get_workflow_status(
        self,
        workflow_id: str,
        user_id: str | None = None,
    ) -> dict:
        """Get the status of a workflow and all its jobs."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        wf_id = uuid.UUID(workflow_id)

        async with self.session_factory() as session:
            # Try to load the named workflow record (may not exist for legacy plain-UUID workflows)
            wf_result = await session.execute(
                select(ScheduledWorkflow).where(
                    ScheduledWorkflow.id == wf_id,
                    ScheduledWorkflow.user_id == uid,
                )
            )
            workflow = wf_result.scalar_one_or_none()

            # Load all jobs with this workflow_id
            jobs_result = await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.workflow_id == wf_id,
                    ScheduledJob.user_id == uid,
                ).order_by(ScheduledJob.created_at)
            )
            jobs = list(jobs_result.scalars().all())

        if not jobs and workflow is None:
            raise ValueError(f"Workflow not found: {workflow_id}")

        # Derive overall workflow status from job statuses
        statuses = {j.status for j in jobs}
        if "active" in statuses:
            overall_status = "active"
        elif "failed" in statuses:
            overall_status = "failed"
        elif statuses == {"completed"} or statuses == {"completed", "cancelled"}:
            overall_status = "completed"
        elif "cancelled" in statuses:
            overall_status = "cancelled"
        else:
            overall_status = workflow.status if workflow else "unknown"

        job_summaries = [
            {
                "job_id": str(j.id),
                "name": j.name,
                "job_type": j.job_type,
                "status": j.status,
                "attempts": j.attempts,
                "max_attempts": j.max_attempts,
                "on_complete": j.on_complete,
                "last_result": j.last_result,
                "created_at": j.created_at.isoformat(),
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
            }
            for j in jobs
        ]

        return {
            "workflow_id": workflow_id,
            "name": workflow.name if workflow else None,
            "description": workflow.description if workflow else None,
            "overall_status": overall_status,
            "total_jobs": len(jobs),
            "active_jobs": sum(1 for j in jobs if j.status == "active"),
            "completed_jobs": sum(1 for j in jobs if j.status == "completed"),
            "failed_jobs": sum(1 for j in jobs if j.status == "failed"),
            "cancelled_jobs": sum(1 for j in jobs if j.status == "cancelled"),
            "jobs": job_summaries,
        }

    async def list_workflows(
        self,
        status_filter: str | None = None,
        user_id: str | None = None,
    ) -> list[dict]:
        """List named workflows for the user."""
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)

        async with self.session_factory() as session:
            query = (
                select(ScheduledWorkflow)
                .where(ScheduledWorkflow.user_id == uid)
                .order_by(ScheduledWorkflow.created_at.desc())
            )
            if status_filter:
                query = query.where(ScheduledWorkflow.status == status_filter)

            result = await session.execute(query)
            workflows = list(result.scalars().all())

        return [
            {
                "workflow_id": str(w.id),
                "name": w.name,
                "description": w.description,
                "status": w.status,
                "platform": w.platform,
                "created_at": w.created_at.isoformat(),
                "completed_at": w.completed_at.isoformat() if w.completed_at else None,
            }
            for w in workflows
        ]

    async def trigger_webhook(
        self,
        job_id: str,
        payload: dict | None = None,
        signature: str | None = None,
        user_id: str | None = None,
    ) -> dict:
        """Trigger a webhook job directly (for testing or internal use).

        For external webhook calls, use the POST /webhook/{job_id} endpoint on the
        scheduler service instead.
        """
        if not user_id:
            raise ValueError("user_id is required")

        uid = uuid.UUID(user_id)
        jid = uuid.UUID(job_id)
        now = datetime.now(timezone.utc)

        async with self.session_factory() as session:
            result = await session.execute(
                select(ScheduledJob).where(
                    ScheduledJob.id == jid,
                    ScheduledJob.user_id == uid,
                )
            )
            job = result.scalar_one_or_none()

            if not job:
                raise ValueError(f"Job not found: {job_id}")
            if job.job_type != "webhook":
                raise ValueError(f"Job {job_id} is not a webhook job (type: {job.job_type})")
            if job.status != "active":
                return {
                    "job_id": job_id,
                    "status": job.status,
                    "message": f"Job is already {job.status}, cannot trigger.",
                }

            # Validate HMAC signature if a secret is configured
            config = job.check_config or {}
            secret = config.get("secret")
            if secret and signature:
                import hashlib
                import hmac as hmac_mod
                import json
                body = json.dumps(payload or {}).encode()
                mac = hmac_mod.new(secret.encode(), body, hashlib.sha256)
                expected = "sha256=" + mac.hexdigest()
                if not hmac_mod.compare_digest(expected, signature):
                    raise ValueError("Invalid webhook signature")

            job.status = "completed"
            job.completed_at = now
            if payload:
                job.last_result = payload
            await session.commit()

        logger.info("webhook_job_triggered", job_id=job_id, user_id=user_id)
        return {
            "job_id": job_id,
            "status": "completed",
            "message": "Webhook job triggered successfully.",
        }
