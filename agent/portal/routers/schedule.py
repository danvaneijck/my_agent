"""Scheduler job management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from portal.auth import PortalUser, require_auth
from portal.services.module_client import call_tool

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


@router.get("")
async def list_jobs(
    status: str | None = Query(None, alias="status"),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List scheduled jobs for the current user."""
    args: dict = {"user_id": str(user.user_id)}
    if status:
        args["status_filter"] = status
    result = await call_tool(
        module="scheduler",
        tool_name="scheduler.list_jobs",
        arguments=args,
        timeout=15.0,
    )
    return {"jobs": result.get("result", [])}


@router.delete("/{job_id}")
async def cancel_job(
    job_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Cancel an active scheduled job."""
    result = await call_tool(
        module="scheduler",
        tool_name="scheduler.cancel_job",
        arguments={"job_id": job_id, "user_id": str(user.user_id)},
        timeout=15.0,
    )
    return result.get("result", {})


@router.delete("/workflow/{workflow_id}")
async def cancel_workflow(
    workflow_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Cancel all active jobs in a workflow."""
    result = await call_tool(
        module="scheduler",
        tool_name="scheduler.cancel_workflow",
        arguments={"workflow_id": workflow_id, "user_id": str(user.user_id)},
        timeout=15.0,
    )
    return result.get("result", {})
