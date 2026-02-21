"""Scheduler module - FastAPI service with background worker."""

from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

from modules.scheduler.manifest import MANIFEST
from modules.scheduler.tools import SchedulerTools
from modules.scheduler.worker import scheduler_loop, validate_webhook_signature
from shared.config import get_settings
from shared.database import get_session_factory
from shared.schemas.common import HealthResponse
from shared.auth import require_service_auth
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()
app = FastAPI(title="Scheduler Module", version="2.0.0")

tools: SchedulerTools | None = None
_worker_task: asyncio.Task | None = None


@app.on_event("startup")
async def startup():
    global tools, _worker_task
    settings = get_settings()
    session_factory = get_session_factory()
    tools = SchedulerTools(session_factory, settings)

    # Start the background worker loop
    _worker_task = asyncio.create_task(
        scheduler_loop(session_factory, settings, settings.redis_url)
    )
    logger.info("scheduler_module_ready")


@app.on_event("shutdown")
async def shutdown():
    global _worker_task
    if _worker_task and not _worker_task.done():
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
    logger.info("scheduler_module_shutdown")


@app.get("/manifest", response_model=ModuleManifest)
async def manifest(_=Depends(require_service_auth)):
    """Return the module manifest."""
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall, _=Depends(require_service_auth)):
    """Execute a tool call."""
    if tools is None:
        return ToolResult(tool_name=call.tool_name, success=False, error="Module not ready")

    try:
        tool_name = call.tool_name.split(".")[-1]
        # Inject user_id from orchestrator context
        args = dict(call.arguments)
        if call.user_id:
            args["user_id"] = call.user_id

        # The orchestrator injects platform/conversation context for all scheduler.*
        # tools, but only add_job and create_workflow use it. Strip for other tools.
        _platform_keys = ("platform", "platform_channel_id", "platform_thread_id",
                          "platform_server_id", "conversation_id")
        _tools_needing_platform = ("add_job", "create_workflow")
        if tool_name not in _tools_needing_platform:
            for k in _platform_keys:
                args.pop(k, None)

        if tool_name == "add_job":
            result = await tools.add_job(**args)
        elif tool_name == "list_jobs":
            result = await tools.list_jobs(**args)
        elif tool_name == "cancel_job":
            result = await tools.cancel_job(**args)
        elif tool_name == "cancel_workflow":
            result = await tools.cancel_workflow(**args)
        elif tool_name == "create_workflow":
            result = await tools.create_workflow(**args)
        elif tool_name == "get_workflow_status":
            result = await tools.get_workflow_status(**args)
        elif tool_name == "list_workflows":
            result = await tools.list_workflows(**args)
        elif tool_name == "trigger_webhook":
            result = await tools.trigger_webhook(**args)
        else:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        return ToolResult(tool_name=call.tool_name, success=True, result=result)
    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e), exc_info=True)
        return ToolResult(tool_name=call.tool_name, success=False, error=str(e))


class WebhookResponse(BaseModel):
    job_id: str
    status: str
    message: str


@app.post("/webhook/{job_id}", response_model=WebhookResponse)
async def receive_webhook(
    job_id: str,
    request: Request,
    x_webhook_signature: str | None = Header(None, alias="X-Webhook-Signature"),
):
    """Receive an external webhook trigger for a webhook-type job.

    The job must already exist and be in 'active' status.  This endpoint is
    intentionally unauthenticated (no service token required) because it is
    called by external systems (CI, GitHub Actions, etc.).

    If the job was created with a ``secret`` in its check_config, the caller
    must include a valid ``X-Webhook-Signature: sha256=<hex>`` header computed
    over the raw request body using HMAC-SHA256 with that secret.
    """
    if tools is None:
        raise HTTPException(status_code=503, detail="Module not ready")

    try:
        job_uuid = job_id  # validate below in trigger_webhook
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job_id")

    # Read raw body for signature validation
    body_bytes = await request.body()
    payload: dict | None = None
    if body_bytes:
        try:
            payload = json.loads(body_bytes)
        except Exception:
            payload = {"raw": body_bytes.decode(errors="replace")}

    # We need to validate the signature before calling trigger_webhook so we
    # can look up the secret.  trigger_webhook performs the same check internally;
    # the external endpoint just needs the user_id, which we get from the job record.
    # Rather than duplicate DB logic here, we rely on trigger_webhook to validate.
    # Pass signature through so trigger_webhook can verify it.

    try:
        # Fetch job to get user_id (needed for trigger_webhook)
        from sqlalchemy import select as sa_select
        from shared.database import get_session_factory as _gsf
        from shared.models.scheduled_job import ScheduledJob
        import uuid as _uuid

        sf = _gsf()
        async with sf() as session:
            r = await session.execute(
                sa_select(ScheduledJob).where(ScheduledJob.id == _uuid.UUID(job_id))
            )
            job = r.scalar_one_or_none()

        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        if job.status != "active":
            return WebhookResponse(
                job_id=job_id,
                status=job.status,
                message=f"Job is already {job.status}.",
            )

        # Validate HMAC signature if secret is configured
        secret = (job.check_config or {}).get("secret")
        if secret:
            if not x_webhook_signature:
                raise HTTPException(status_code=401, detail="X-Webhook-Signature header required")
            if not validate_webhook_signature(secret, body_bytes, x_webhook_signature):
                raise HTTPException(status_code=403, detail="Invalid webhook signature")

        result = await tools.trigger_webhook(
            job_id=job_id,
            payload=payload,
            signature=x_webhook_signature,
            user_id=str(job.user_id),
        )
        return WebhookResponse(**result)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("webhook_error", job_id=job_id, error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
