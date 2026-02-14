"""Deployment management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from portal.auth import PortalUser, require_auth
from portal.services.module_client import call_tool

router = APIRouter(prefix="/api/deployments", tags=["deployments"])


@router.get("")
async def list_deployments(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List all active deployments."""
    result = await call_tool(
        module="deployer",
        tool_name="deployer.list_deployments",
        arguments={},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.delete("/{deploy_id}")
async def teardown_deployment(
    deploy_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Tear down a single deployment."""
    result = await call_tool(
        module="deployer",
        tool_name="deployer.teardown",
        arguments={"deploy_id": deploy_id},
        user_id=str(user.user_id),
        timeout=30.0,
    )
    return result.get("result", {})


@router.delete("")
async def teardown_all(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Tear down all deployments."""
    result = await call_tool(
        module="deployer",
        tool_name="deployer.teardown_all",
        arguments={},
        user_id=str(user.user_id),
        timeout=60.0,
    )
    return result.get("result", {})


@router.get("/{deploy_id}/logs")
async def get_deployment_logs(
    deploy_id: str,
    lines: int = Query(50, ge=1, le=500),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get logs from a deployment container."""
    result = await call_tool(
        module="deployer",
        tool_name="deployer.get_logs",
        arguments={"deploy_id": deploy_id, "lines": lines},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.get("/{deploy_id}/services")
async def get_deployment_services(
    deploy_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get services for a compose deployment."""
    result = await call_tool(
        module="deployer",
        tool_name="deployer.get_services",
        arguments={"deploy_id": deploy_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.get("/{deploy_id}/services/{service_name}/logs")
async def get_service_logs(
    deploy_id: str,
    service_name: str,
    lines: int = Query(50, ge=1, le=500),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get logs for a specific service in a compose deployment."""
    result = await call_tool(
        module="deployer",
        tool_name="deployer.get_service_logs",
        arguments={
            "deploy_id": deploy_id,
            "service_name": service_name,
            "lines": lines,
        },
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


@router.get("/{deploy_id}/env")
async def get_deployment_env(
    deploy_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get environment variables for a deployment."""
    result = await call_tool(
        module="deployer",
        tool_name="deployer.get_env_vars",
        arguments={"deploy_id": deploy_id},
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})


class UpdateEnvBody(BaseModel):
    env_vars: dict[str, str]
    restart: bool = True


@router.put("/{deploy_id}/env")
async def update_deployment_env(
    deploy_id: str,
    body: UpdateEnvBody,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Update environment variables and optionally restart."""
    result = await call_tool(
        module="deployer",
        tool_name="deployer.update_env_vars",
        arguments={
            "deploy_id": deploy_id,
            "env_vars": body.env_vars,
            "restart": body.restart,
        },
        user_id=str(user.user_id),
        timeout=120.0,
    )
    return result.get("result", {})


@router.post("/{deploy_id}/restart")
async def restart_deployment(
    deploy_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Restart a deployment."""
    result = await call_tool(
        module="deployer",
        tool_name="deployer.restart",
        arguments={"deploy_id": deploy_id},
        user_id=str(user.user_id),
        timeout=120.0,
    )
    return result.get("result", {})
