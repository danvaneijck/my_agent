"""Aggregated module health endpoint."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import APIRouter, Depends

from portal.auth import PortalUser, require_auth
from portal.services.module_client import check_module_health
from shared.config import get_settings

logger = structlog.get_logger()
router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def aggregated_health(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Concurrently check /health on every module service.

    Returns {module_name: {status, latency_ms, error}}.
    """
    settings = get_settings()
    module_names = list(settings.module_services.keys())
    results = await asyncio.gather(
        *[check_module_health(m) for m in module_names]
    )
    return {
        r["module"]: {
            "status": r["status"],
            "latency_ms": r.get("latency_ms"),
            "error": r.get("error"),
        }
        for r in results
    }
