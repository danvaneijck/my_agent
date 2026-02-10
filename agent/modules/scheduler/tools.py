"""Scheduler module tool implementations — background job management."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.config import Settings
from shared.models.scheduled_job import ScheduledJob

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
        interval_seconds: int = 30,
        max_attempts: int = 120,
        platform: str | None = None,
        platform_channel_id: str | None = None,
        platform_thread_id: str | None = None,
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

        async with self.session_factory() as session:
            job = ScheduledJob(
                id=job_id,
                user_id=uid,
                platform=platform,
                platform_channel_id=platform_channel_id,
                platform_thread_id=platform_thread_id,
                job_type=job_type,
                check_config=check_config,
                interval_seconds=interval_seconds,
                max_attempts=max_attempts,
                attempts=0,
                on_success_message=on_success_message,
                on_failure_message=on_failure_message,
                status="active",
                next_run_at=now + timedelta(seconds=interval_seconds),
                created_at=now,
            )
            session.add(job)
            await session.commit()

        logger.info(
            "job_scheduled",
            job_id=str(job_id),
            job_type=job_type,
            user_id=user_id,
            interval=interval_seconds,
            max_attempts=max_attempts,
        )
        return {
            "job_id": str(job_id),
            "status": "active",
            "message": "Job scheduled. I'll notify you when the condition is met.",
        }

    async def list_jobs(
        self,
        status_filter: str | None = None,
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

            result = await session.execute(query)
            jobs = list(result.scalars().all())

        return [
            {
                "job_id": str(j.id),
                "job_type": j.job_type,
                "status": j.status,
                "attempts": j.attempts,
                "max_attempts": j.max_attempts,
                "interval_seconds": j.interval_seconds,
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
