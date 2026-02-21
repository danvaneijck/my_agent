"""Health and system status endpoints."""

from __future__ import annotations

import asyncio

import httpx
import structlog
from fastapi import APIRouter, Depends

from portal.auth import PortalUser, require_auth
from portal.services.module_client import check_module_health
from shared.config import get_settings

logger = structlog.get_logger()
router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Portal health check. Also validates the auth token."""
    return {
        "status": "ok",
        "user": {
            "username": user.username,
            "permission_level": user.permission_level,
        },
    }


@router.get("/system/modules")
async def module_status(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Check health of all configured modules."""
    settings = get_settings()
    tasks = [
        check_module_health(module) for module in settings.module_services
    ]
    results = await asyncio.gather(*tasks)
    return {"modules": results}


@router.get("/system/deploy-status")
async def deploy_status(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Check whether the configured deployment workflow is currently running.

    Uses the server-level git_platform_token so every portal user sees the
    same banner without needing their own GitHub credentials configured.
    Works on public repos even without a token (60 req/hr unauthenticated).

    Returns:
        {
            "active": bool,          # True when a run is queued or in_progress
            "run": {                 # Present when active=True, else null
                "id": int,
                "name": str,
                "status": str,       # "queued" | "in_progress"
                "url": str,          # Link to the GitHub Actions run page
                "created_at": str,
                "updated_at": str,
            } | null,
            "configured": bool,      # False when repo owner/name not set
        }
    """
    settings = get_settings()

    owner = settings.deploy_workflow_repo_owner
    repo = settings.deploy_workflow_repo_name
    workflow_name = settings.deploy_workflow_name

    if not owner or not repo:
        return {"active": False, "run": None, "configured": False}

    headers: dict[str, str] = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if settings.git_platform_token:
        headers["Authorization"] = f"Bearer {settings.git_platform_token}"

    base_url = f"https://api.github.com/repos/{owner}/{repo}/actions/runs"

    runs: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Fetch in_progress and queued runs in parallel
            in_progress_resp, queued_resp = await asyncio.gather(
                client.get(base_url, headers=headers, params={"per_page": "10", "status": "in_progress"}),
                client.get(base_url, headers=headers, params={"per_page": "10", "status": "queued"}),
            )
            if in_progress_resp.status_code == 200:
                runs += in_progress_resp.json().get("workflow_runs", [])
            if queued_resp.status_code == 200:
                runs += queued_resp.json().get("workflow_runs", [])
    except Exception as exc:
        logger.warning("deploy_status_fetch_failed", error=str(exc))
        return {"active": False, "run": None, "configured": True}

    # Find the first run matching the configured workflow name
    matching = next(
        (
            r for r in runs
            if r.get("name") == workflow_name
            and r.get("status") in ("in_progress", "queued")
        ),
        None,
    )

    if matching:
        return {
            "active": True,
            "configured": True,
            "run": {
                "id": matching["id"],
                "name": matching["name"],
                "status": matching["status"],
                "url": matching["html_url"],
                "created_at": matching.get("created_at", ""),
                "updated_at": matching.get("updated_at", ""),
            },
        }

    return {"active": False, "run": None, "configured": True}
