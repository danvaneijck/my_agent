"""Scheduler background worker — polls active jobs and sends notifications."""

from __future__ import annotations

import asyncio
import re
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

# Error patterns that indicate the target will never be found — no point retrying
_PERMANENT_ERROR_PATTERNS = ("not found", "does not exist", "unknown tool")


class _PermanentCheckError(Exception):
    """Raised when a check fails with an error that will never resolve on retry."""


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
    except _PermanentCheckError as e:
        # Permanent error — target will never become available, fail immediately
        logger.warning(
            "job_check_permanent_error",
            job_id=str(job.id),
            attempt=job.attempts,
            error=str(e),
        )
        await _mark_failed(job, now, redis, settings)
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
            await _mark_failed(job, now, redis, settings)
        else:
            job.next_run_at = now + timedelta(seconds=job.interval_seconds)
        return

    if condition_met:
        job.status = "completed"
        job.completed_at = now

        # Build message
        if task_failed and job.on_failure_message:
            message = job.on_failure_message
        else:
            message = job.on_success_message

        # Interpolate {result} and {result.field} placeholders
        if result_data is not None:
            message = _interpolate_result(message, result_data)

        # Decide completion action
        if job.on_complete == "resume_conversation" and not task_failed:
            await _resume_conversation(job, message, result_data, settings, redis)
        else:
            # For task failures or notify mode, just send a notification
            await _publish_notification(job, message, redis)

        logger.info(
            "job_completed",
            job_id=str(job.id),
            task_failed=task_failed,
            on_complete=job.on_complete,
        )

    elif job.attempts >= job.max_attempts:
        await _mark_failed(job, now, redis, settings)

    else:
        # Not done yet, schedule next check
        job.next_run_at = now + timedelta(seconds=job.interval_seconds)


_RESULT_SUMMARY_KEYS = (
    "task_id", "status", "workspace", "mode", "error",
    "elapsed_seconds", "exit_code",
)


def _summarize_result(result_data: dict | None) -> str:
    """Return a compact summary of result_data for chat display.

    Strips bulky fields like json_output (which can contain an entire
    Claude Code session transcript) and keeps only essential metadata.
    """
    if not isinstance(result_data, dict):
        return str(result_data)

    summary = {k: v for k, v in result_data.items() if k in _RESULT_SUMMARY_KEYS and v is not None}
    if not summary:
        # Fallback: include top-level scalar fields only (skip large nested objects/lists)
        summary = {
            k: v for k, v in result_data.items()
            if isinstance(v, (str, int, float, bool)) and len(str(v)) < 500
        }
    return str(summary) if summary else "(completed)"


_RESULT_PLACEHOLDER_RE = re.compile(r"\{result(?:\.(\w+))?\}")


def _interpolate_result(message: str, result_data: dict | None) -> str:
    """Replace {result} and {result.field} placeholders in a message.

    - ``{result}``       → compact summary of the full result dict
    - ``{result.status}`` → value of ``result_data["status"]``
    """
    if not isinstance(result_data, dict):
        return message.replace("{result}", str(result_data) if result_data is not None else "(completed)")

    def _replace(m: re.Match) -> str:
        field = m.group(1)
        if field is None:
            # bare {result}
            return _summarize_result(result_data)
        value = result_data.get(field)
        return str(value) if value is not None else m.group(0)

    return _RESULT_PLACEHOLDER_RE.sub(_replace, message)


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

    # Normalize tool name to "module.method" format.
    # LLMs sometimes write "claude_code_task_status" (underscores) instead of
    # "claude_code.task_status" (dot).  The module's /execute endpoint splits
    # on "." to extract the method name, so we must ensure the dot is present.
    if "." not in tool and module:
        # Strip the module prefix (with underscore) if present, then re-add with dot
        prefix = module + "_"
        if tool.startswith(prefix):
            tool = f"{module}.{tool[len(prefix):]}"
        else:
            tool = f"{module}.{tool}"

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
        error_msg = tool_result.error or ""
        error_lower = error_msg.lower()
        if any(pat in error_lower for pat in _PERMANENT_ERROR_PATTERNS):
            raise _PermanentCheckError(f"Module returned error: {error_msg}")
        raise RuntimeError(f"Module returned error: {error_msg}")

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


async def _resume_conversation(
    job: ScheduledJob,
    message: str,
    result_data: dict | None,
    settings: Settings,
    redis: aioredis.Redis,
) -> None:
    """Re-enter the agent loop via core /continue endpoint.

    This allows the LLM to continue with follow-up actions (e.g. deploy
    after a build completes) using the original conversation context.
    """
    payload = {
        "platform": job.platform,
        "platform_channel_id": job.platform_channel_id,
        "platform_thread_id": job.platform_thread_id,
        "user_id": str(job.user_id),
        "content": message,
        "job_id": str(job.id),
        "workflow_id": str(job.workflow_id) if job.workflow_id else None,
        "result_data": result_data,
    }

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{settings.orchestrator_url}/continue",
                json=payload,
            )
            resp.raise_for_status()
            response_data = resp.json()

        # The agent loop response is sent as a notification so the user sees it
        agent_content = response_data.get("content", "")
        if agent_content:
            await _publish_notification(job, agent_content, redis)

        logger.info(
            "conversation_resumed",
            job_id=str(job.id),
            response_length=len(agent_content),
        )
    except Exception as e:
        logger.error(
            "resume_conversation_failed",
            job_id=str(job.id),
            error=str(e),
        )
        # Fall back to a plain notification so the user isn't left hanging
        fallback = f"{message}\n\n(Note: automatic follow-up failed — {e})"
        await _publish_notification(job, fallback, redis)


async def _mark_failed(
    job: ScheduledJob,
    now: datetime,
    redis: aioredis.Redis,
    settings: Settings,
) -> None:
    """Mark a job as failed and send a failure notification."""
    job.status = "failed"
    job.completed_at = now

    message = job.on_failure_message or (
        f"Scheduled job timed out after {job.max_attempts} attempts "
        f"({job.max_attempts * job.interval_seconds // 60} minutes)."
    )

    # For resume_conversation jobs, try to resume so the LLM can handle the failure
    if job.on_complete == "resume_conversation":
        fail_message = f"[WORKFLOW FAILED] {message}"
        await _resume_conversation(job, fail_message, None, settings, redis)
    else:
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
