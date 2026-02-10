"""Scheduler background worker — polls active jobs and sends notifications."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import redis.asyncio as aioredis
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.config import Settings
from shared.models.scheduled_job import ScheduledJob
from shared.schemas.notifications import Notification
from shared.schemas.tools import ToolCall, ToolResult

logger = structlog.get_logger()

# How often the main loop wakes up to check for due jobs
LOOP_INTERVAL_SECONDS = 10


async def scheduler_loop(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    redis_url: str,
) -> None:
    """Background loop that processes active scheduled jobs."""
    redis = aioredis.from_url(redis_url)
    logger.info("scheduler_worker_started")

    try:
        while True:
            try:
                await _process_due_jobs(session_factory, settings, redis)
            except Exception as e:
                logger.error("scheduler_loop_error", error=str(e))

            await asyncio.sleep(LOOP_INTERVAL_SECONDS)
    finally:
        await redis.aclose()


async def _process_due_jobs(
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
    redis: aioredis.Redis,
) -> None:
    """Query and evaluate all jobs that are due for checking."""
    now = datetime.now(timezone.utc)

    async with session_factory() as session:
        result = await session.execute(
            select(ScheduledJob).where(
                ScheduledJob.status == "active",
                ScheduledJob.next_run_at <= now,
            )
        )
        due_jobs = list(result.scalars().all())

    if not due_jobs:
        return

    logger.info("processing_due_jobs", count=len(due_jobs))

    for job in due_jobs:
        try:
            async with session_factory() as session:
                # Re-fetch within this session so changes are tracked
                result = await session.execute(
                    select(ScheduledJob).where(ScheduledJob.id == job.id)
                )
                job = result.scalar_one_or_none()
                if not job or job.status != "active":
                    continue

                await _evaluate_job(job, session, settings, redis)
                await session.commit()
        except Exception as e:
            logger.error(
                "job_evaluation_error",
                job_id=str(job.id),
                error=str(e),
            )


async def _evaluate_job(
    job: ScheduledJob,
    session: AsyncSession,
    settings: Settings,
    redis: aioredis.Redis,
) -> None:
    """Evaluate a single job and update its state."""
    job.attempts += 1
    now = datetime.now(timezone.utc)

    logger.info(
        "evaluating_job",
        job_id=str(job.id),
        job_type=job.job_type,
        attempt=job.attempts,
        max_attempts=job.max_attempts,
    )

    condition_met = False
    task_failed = False
    result_data = None

    try:
        if job.job_type == "poll_module":
            condition_met, task_failed, result_data = await _check_poll_module(
                job, settings
            )
        elif job.job_type == "delay":
            condition_met = _check_delay(job)
        elif job.job_type == "poll_url":
            condition_met = await _check_poll_url(job)
        else:
            logger.warning("unknown_job_type", job_type=job.job_type, job_id=str(job.id))
            job.status = "failed"
            job.completed_at = now
            return
    except Exception as e:
        # Transient error — don't fail the job, just schedule the next attempt
        logger.warning(
            "job_check_transient_error",
            job_id=str(job.id),
            attempt=job.attempts,
            error=str(e),
        )
        if job.attempts >= job.max_attempts:
            await _mark_failed(job, now, redis)
        else:
            job.next_run_at = now + timedelta(seconds=job.interval_seconds)
        return

    if condition_met:
        job.status = "completed"
        job.completed_at = now

        # Build notification message
        if task_failed and job.on_failure_message:
            message = job.on_failure_message
        else:
            message = job.on_success_message

        # Interpolate {result} placeholder if present
        if result_data is not None and "{result}" in message:
            message = message.replace("{result}", str(result_data))

        await _publish_notification(job, message, redis)
        logger.info("job_completed", job_id=str(job.id), task_failed=task_failed)

    elif job.attempts >= job.max_attempts:
        await _mark_failed(job, now, redis)

    else:
        # Not done yet, schedule next check
        job.next_run_at = now + timedelta(seconds=job.interval_seconds)


async def _check_poll_module(
    job: ScheduledJob,
    settings: Settings,
) -> tuple[bool, bool, dict | None]:
    """Poll a module tool and check if the success condition is met.

    Returns (condition_met, task_failed, result_data).
    """
    config = job.check_config
    module = config.get("module", "")
    tool = config.get("tool", "")
    args = config.get("args", {})
    success_field = config.get("success_field", "status")
    success_values = config.get("success_values", ["completed", "failed"])

    module_url = settings.module_services.get(module)
    if not module_url:
        raise ValueError(f"Unknown module: {module}")

    # Build a ToolCall and POST to the module's /execute endpoint
    call = ToolCall(
        tool_name=tool,
        arguments=args,
        user_id=str(job.user_id),
    )

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{module_url}/execute",
            json=call.model_dump(),
        )
        resp.raise_for_status()

    tool_result = ToolResult(**resp.json())

    if not tool_result.success:
        raise RuntimeError(f"Module returned error: {tool_result.error}")

    result_data = tool_result.result
    if not isinstance(result_data, dict):
        return False, False, result_data

    field_value = result_data.get(success_field)

    if field_value in success_values:
        # Determine if this is actually a failure status (e.g., "failed")
        task_failed = field_value in ("failed", "error", "errored")
        return True, task_failed, result_data

    return False, False, result_data


def _check_delay(job: ScheduledJob) -> bool:
    """Check if enough time has passed for a delay job."""
    config = job.check_config
    delay_seconds = config.get("delay_seconds", 0)
    elapsed = job.attempts * job.interval_seconds
    return elapsed >= delay_seconds


async def _check_poll_url(job: ScheduledJob) -> bool:
    """Check if an HTTP endpoint returns the expected status code."""
    config = job.check_config
    url = config.get("url", "")
    method = config.get("method", "GET").upper()
    expected_status = config.get("expected_status", 200)

    async with httpx.AsyncClient(timeout=15.0) as client:
        if method == "POST":
            resp = await client.post(url)
        else:
            resp = await client.get(url)

    return resp.status_code == expected_status


async def _mark_failed(
    job: ScheduledJob,
    now: datetime,
    redis: aioredis.Redis,
) -> None:
    """Mark a job as failed and send a failure notification."""
    job.status = "failed"
    job.completed_at = now

    message = job.on_failure_message or (
        f"Scheduled job timed out after {job.max_attempts} attempts "
        f"({job.max_attempts * job.interval_seconds // 60} minutes)."
    )
    await _publish_notification(job, message, redis)
    logger.info("job_failed_max_attempts", job_id=str(job.id))


async def _publish_notification(
    job: ScheduledJob,
    message: str,
    redis: aioredis.Redis,
) -> None:
    """Publish a notification to the Redis channel for the job's platform."""
    notification = Notification(
        platform=job.platform,
        platform_channel_id=job.platform_channel_id,
        platform_thread_id=job.platform_thread_id,
        content=message,
        user_id=str(job.user_id),
        job_id=str(job.id),
    )
    channel = f"notifications:{job.platform}"
    await redis.publish(channel, notification.model_dump_json())
    logger.info(
        "notification_published",
        channel=channel,
        job_id=str(job.id),
    )
