"""Health and system status endpoints."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends

from portal.auth import PortalUser, require_auth
from portal.services.module_client import check_module_health
from shared.config import get_settings

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
