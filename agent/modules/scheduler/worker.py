"""Scheduler background worker — polls active jobs and sends notifications."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
import redis.asyncio as aioredis
import structlog
from croniter import croniter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from shared.auth import get_service_auth_headers
from shared.config import Settings
from shared.models.scheduled_job import ScheduledJob
from shared.schemas.notifications import Notification
from shared.schemas.tools import ToolCall, ToolResult

logger = structlog.get_logger()

# How often the main loop wakes up to check for due jobs
LOOP_INTERVAL_SECONDS = 10

# Maximum backoff cap for transient errors (seconds)
_MAX_BACKOFF_SECONDS = 300

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

    # Check wall-clock expiry (alternative to max_attempts)
    if job.expires_at and now >= job.expires_at:
        logger.info("job_expired", job_id=str(job.id))
        await _mark_failed(job, now, redis, settings, session=session, reason="expired")
        return

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
            condition_met = _check_delay(job, now)
        elif job.job_type == "poll_url":
            condition_met, result_data = await _check_poll_url(job)
        elif job.job_type == "cron":
            # Cron jobs always fire on schedule
            condition_met = True
        elif job.job_type == "webhook":
            # Webhook jobs are triggered externally via POST /webhook/{job_id}.
            # The worker periodically checks whether the webhook has already fired
            # by inspecting job.last_result; normally the endpoint marks the job
            # directly, so here we just reschedule the heartbeat.
            condition_met = False
        else:
            logger.warning("unknown_job_type", job_type=job.job_type, job_id=str(job.id))
            job.status = "failed"
            job.completed_at = now
            return

        # On a successful poll reset the consecutive-failure counter
        if job.job_type == "poll_module":
            job.consecutive_failures = 0

    except _PermanentCheckError as e:
        logger.warning(
            "job_check_permanent_error",
            job_id=str(job.id),
            attempt=job.attempts,
            error=str(e),
        )
        await _mark_failed(job, now, redis, settings, session=session)
        return
    except Exception as e:
        # Transient error — don't fail the job, just back off
        job.consecutive_failures += 1
        backoff = min(
            job.interval_seconds * (2 ** job.consecutive_failures),
            _MAX_BACKOFF_SECONDS,
        )
        logger.warning(
            "job_check_transient_error",
            job_id=str(job.id),
            attempt=job.attempts,
            consecutive_failures=job.consecutive_failures,
            next_backoff_seconds=backoff,
            error=str(e),
        )
        if job.attempts >= job.max_attempts:
            await _mark_failed(job, now, redis, settings, session=session)
        else:
            job.next_run_at = now + timedelta(seconds=backoff)
        return

    if condition_met:
        if job.job_type == "cron":
            # Recurring job — fire the action then reschedule
            job.runs_completed += 1
            message = _interpolate_result(
                job.on_success_message, result_data, str(job.id), str(job.workflow_id) if job.workflow_id else None
            )
            if job.on_complete == "resume_conversation":
                await _resume_conversation(job, message, result_data, settings, redis)
            else:
                await _publish_notification(job, message, redis)

            # Check max_runs
            if job.max_runs is not None and job.runs_completed >= job.max_runs:
                job.status = "completed"
                job.completed_at = now
                logger.info("cron_job_max_runs_reached", job_id=str(job.id), runs=job.runs_completed)
            else:
                # Schedule next cron run
                cron_expr = job.check_config.get("cron_expr", "0 * * * *")
                tz_name = job.check_config.get("timezone", "UTC")
                try:
                    import zoneinfo
                    tz = zoneinfo.ZoneInfo(tz_name)
                    now_local = now.astimezone(tz)
                    next_dt = croniter(cron_expr, now_local).get_next(datetime)
                    # Store as UTC
                    job.next_run_at = next_dt.astimezone(timezone.utc)
                except Exception as cron_err:
                    logger.error("cron_reschedule_error", job_id=str(job.id), error=str(cron_err))
                    job.next_run_at = now + timedelta(hours=1)
                job.consecutive_failures = 0
        else:
            # One-shot job
            job.status = "completed"
            job.completed_at = now

            # Store last result for observability
            if result_data is not None:
                job.last_result = result_data

            # Build message
            if task_failed and job.on_failure_message:
                message = job.on_failure_message
            else:
                message = job.on_success_message

            # Interpolate placeholders
            message = _interpolate_result(
                message, result_data, str(job.id), str(job.workflow_id) if job.workflow_id else None
            )

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
        await _mark_failed(job, now, redis, settings, session=session)

    else:
        # Not done yet, schedule next check
        if result_data is not None:
            job.last_result = result_data
        job.next_run_at = now + timedelta(seconds=job.interval_seconds)


# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

_RESULT_SUMMARY_KEYS = (
    "task_id", "status", "workspace", "mode", "error",
    "elapsed_seconds", "exit_code",
)


def _summarize_result(result_data: dict | None, summary_fields: list[str] | None = None) -> str:
    """Return a compact summary of result_data for chat display.

    Strips bulky fields like json_output (which can contain an entire
    Claude Code session transcript) and keeps only essential metadata.

    If ``summary_fields`` is provided (from check_config.result_summary_fields),
    those keys are used instead of the defaults.
    """
    if not isinstance(result_data, dict):
        return str(result_data)

    keys = summary_fields if summary_fields else _RESULT_SUMMARY_KEYS
    summary = {k: v for k, v in result_data.items() if k in keys and v is not None}
    if not summary:
        # Fallback: include top-level scalar fields only (skip large nested objects/lists)
        summary = {
            k: v for k, v in result_data.items()
            if isinstance(v, (str, int, float, bool)) and len(str(v)) < 500
        }
    return str(summary) if summary else "(completed)"


_RESULT_PLACEHOLDER_RE = re.compile(r"\{result(?:\.([\w.]+))?\}|\{job_id\}|\{workflow_id\}")


def _interpolate_result(
    message: str,
    result_data: dict | None,
    job_id: str | None = None,
    workflow_id: str | None = None,
) -> str:
    """Replace placeholders in a message.

    Supported placeholders:
    - ``{result}``             → compact summary of the full result dict
    - ``{result.field}``       → value of ``result_data["field"]``
    - ``{result.nested.field}``→ value of ``result_data["nested"]["field"]`` (dot path)
    - ``{job_id}``             → the job's UUID
    - ``{workflow_id}``        → the workflow's UUID (if set)
    """
    if not isinstance(result_data, dict):
        # No result data — replace {result} with a simple string
        result_str = str(result_data) if result_data is not None else "(completed)"

        def _replace_simple(m: re.Match) -> str:
            text = m.group(0)
            if text == "{job_id}":
                return job_id or text
            if text == "{workflow_id}":
                return workflow_id or text
            return result_str

        return _RESULT_PLACEHOLDER_RE.sub(_replace_simple, message)

    def _get_nested(data: dict, path: str) -> Any:
        """Traverse a dot-separated key path into a nested dict."""
        parts = path.split(".")
        current: Any = data
        for part in parts:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    def _replace(m: re.Match) -> str:
        text = m.group(0)
        if text == "{job_id}":
            return job_id or text
        if text == "{workflow_id}":
            return workflow_id or text
        # {result} or {result.field} or {result.nested.field}
        field_path = m.group(1)
        if field_path is None:
            # bare {result}
            return _summarize_result(result_data)
        value = _get_nested(result_data, field_path)
        return str(value) if value is not None else m.group(0)

    return _RESULT_PLACEHOLDER_RE.sub(_replace, message)


# ---------------------------------------------------------------------------
# Check implementations
# ---------------------------------------------------------------------------

def _get_nested_value(data: dict, path: str) -> Any:
    """Traverse a dot-separated key path into a nested dict."""
    parts = path.split(".")
    current: Any = data
    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def _evaluate_condition(field_value: Any, operator: str, target: Any) -> bool:
    """Evaluate a field value against a target using the given operator."""
    try:
        if operator == "in":
            return field_value in target
        if operator == "eq":
            return field_value == target
        if operator == "neq":
            return field_value != target
        if operator in ("gt", ">"):
            return float(field_value) > float(target)
        if operator in ("gte", ">="):
            return float(field_value) >= float(target)
        if operator in ("lt", "<"):
            return float(field_value) < float(target)
        if operator in ("lte", "<="):
            return float(field_value) <= float(target)
        if operator == "contains":
            return target in str(field_value)
    except (TypeError, ValueError):
        pass
    return False


async def _check_poll_module(
    job: ScheduledJob,
    settings: Settings,
) -> tuple[bool, bool, dict | None]:
    """Poll a module tool and check if the success condition is met.

    Returns (condition_met, task_failed, result_data).

    check_config fields:
    - module (str): module name
    - tool (str): tool name (with or without dot separator)
    - args (dict): arguments to pass to the tool
    - success_field (str): dot-path to the field to check (default: "status")
    - success_values (list): values that indicate success (used with "in" operator)
    - success_operator (str): "in" (default), "eq", "neq", "gt", "gte", "lt", "lte", "contains"
    - success_value (any): target for operators other than "in"
    - result_summary_fields (list[str]): override keys used by _summarize_result
    """
    config = job.check_config
    module = config.get("module", "")
    tool = config.get("tool", "")
    args = config.get("args", {})
    success_field = config.get("success_field", "status")
    success_values = config.get("success_values", ["completed", "failed"])
    success_operator = config.get("success_operator", "in")
    success_value = config.get("success_value")  # for non-"in" operators

    # Normalize tool name to "module.method" format.
    # LLMs sometimes write "claude_code_task_status" (underscores) instead of
    # "claude_code.task_status" (dot).  The module's /execute endpoint splits
    # on "." to extract the method name, so we must ensure the dot is present.
    if "." not in tool and module:
        prefix = module + "_"
        if tool.startswith(prefix):
            tool = f"{module}.{tool[len(prefix):]}"
        else:
            tool = f"{module}.{tool}"

    module_url = settings.module_services.get(module)
    if not module_url:
        raise ValueError(f"Unknown module: {module}")

    call = ToolCall(
        tool_name=tool,
        arguments=args,
        user_id=str(job.user_id),
    )

    headers = get_service_auth_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{module_url}/execute",
            json=call.model_dump(),
            headers=headers,
        )
        # HTTP 4xx (excluding 429) are permanent errors — the resource is gone
        if resp.status_code in (404, 410):
            raise _PermanentCheckError(f"Module returned HTTP {resp.status_code}")
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

    # Support dot-path field access
    field_value = _get_nested_value(result_data, success_field)

    # Evaluate using the configured operator
    if success_operator == "in":
        condition_met = field_value in success_values
    else:
        target = success_value
        condition_met = _evaluate_condition(field_value, success_operator, target)

    if condition_met:
        task_failed = field_value in ("failed", "error", "errored")
        return True, task_failed, result_data

    return False, False, result_data


def _check_delay(job: ScheduledJob, now: datetime) -> bool:
    """Check if enough wall-clock time has passed for a delay job.

    Uses created_at for accuracy instead of attempts × interval_seconds,
    which drifts when the worker loop is delayed.
    """
    config = job.check_config
    delay_seconds = config.get("delay_seconds", 0)
    elapsed = (now - job.created_at).total_seconds()
    return elapsed >= delay_seconds


async def _check_poll_url(job: ScheduledJob) -> tuple[bool, dict | None]:
    """Check if an HTTP endpoint returns the expected status code and/or body.

    check_config fields:
    - url (str): the URL to poll
    - method (str): GET or POST (default: GET)
    - expected_status (int): expected HTTP status code (default: 200)
    - response_field (str, optional): dot-path into the JSON response body to check
    - response_value (any, optional): expected value of response_field
    - response_operator (str, optional): comparison operator (default: "eq")
    """
    config = job.check_config
    url = config.get("url", "")
    method = config.get("method", "GET").upper()
    expected_status = config.get("expected_status", 200)
    response_field = config.get("response_field")
    response_value = config.get("response_value")
    response_operator = config.get("response_operator", "eq")

    async with httpx.AsyncClient(timeout=15.0) as client:
        if method == "POST":
            resp = await client.post(url)
        else:
            resp = await client.get(url)

    status_ok = resp.status_code == expected_status
    result_data: dict | None = None

    if not status_ok:
        return False, None

    # Optionally inspect the JSON response body
    if response_field is not None:
        try:
            body = resp.json()
            result_data = body if isinstance(body, dict) else {"body": body}
            field_val = _get_nested_value(result_data, response_field) if isinstance(result_data, dict) else None
            body_ok = _evaluate_condition(field_val, response_operator, response_value)
            return body_ok, result_data
        except Exception:
            return False, None

    return True, result_data


# ---------------------------------------------------------------------------
# Lifecycle helpers
# ---------------------------------------------------------------------------

async def _resume_conversation(
    job: ScheduledJob,
    message: str,
    result_data: dict | None,
    settings: Settings,
    redis: aioredis.Redis,
) -> None:
    """Re-enter the agent loop via core /continue endpoint."""
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
        headers = get_service_auth_headers()
        async with httpx.AsyncClient(timeout=180.0) as client:
            resp = await client.post(
                f"{settings.orchestrator_url}/continue",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            response_data = resp.json()

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
        fallback = f"{message}\n\n(Note: automatic follow-up failed — {e})"
        await _publish_notification(job, fallback, redis)


async def _cancel_workflow_siblings(
    job: ScheduledJob,
    session: AsyncSession,
    now: datetime,
) -> None:
    """Cancel all other active jobs that share the same workflow_id."""
    if not job.workflow_id:
        return
    result = await session.execute(
        select(ScheduledJob).where(
            ScheduledJob.workflow_id == job.workflow_id,
            ScheduledJob.status == "active",
            ScheduledJob.id != job.id,
        )
    )
    siblings = list(result.scalars().all())
    for sibling in siblings:
        sibling.status = "cancelled"
        sibling.completed_at = now
    if siblings:
        logger.info(
            "workflow_siblings_cancelled",
            workflow_id=str(job.workflow_id),
            count=len(siblings),
        )


async def _mark_failed(
    job: ScheduledJob,
    now: datetime,
    redis: aioredis.Redis,
    settings: Settings,
    session: AsyncSession | None = None,
    reason: str = "max_attempts",
) -> None:
    """Mark a job as failed, cancel workflow siblings, and send failure notification."""
    job.status = "failed"
    job.completed_at = now

    # Auto-cancel sibling jobs in the same workflow so they don't keep polling
    if session is not None:
        await _cancel_workflow_siblings(job, session, now)

    if reason == "expired":
        default_msg = (
            f"Scheduled job expired after {int((now - job.created_at).total_seconds() // 60)} minutes."
        )
    else:
        default_msg = (
            f"Scheduled job timed out after {job.max_attempts} attempts "
            f"({job.max_attempts * job.interval_seconds // 60} minutes)."
        )

    message = job.on_failure_message or default_msg

    if job.on_complete == "resume_conversation":
        fail_message = f"[WORKFLOW FAILED] {message}"
        await _resume_conversation(job, fail_message, None, settings, redis)
    else:
        await _publish_notification(job, message, redis)

    logger.info("job_failed", job_id=str(job.id), reason=reason)


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
        platform_server_id=job.platform_server_id,
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


# ---------------------------------------------------------------------------
# Webhook helpers (used by the /webhook/{job_id} endpoint in main.py)
# ---------------------------------------------------------------------------

def validate_webhook_signature(secret: str, body: bytes, signature: str) -> bool:
    """Validate an HMAC-SHA256 webhook signature.

    The caller is expected to send ``X-Webhook-Signature: sha256=<hex>`` header.
    """
    mac = hmac.new(secret.encode(), body, hashlib.sha256)
    expected = "sha256=" + mac.hexdigest()
    return hmac.compare_digest(expected, signature)
