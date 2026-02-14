"""Account settings endpoints — credentials, profile, connected accounts."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from portal.auth import PortalUser, require_auth
from shared.config import get_settings
from shared.credential_store import CredentialStore
from shared.database import get_session_factory
from shared.models.user import User, UserPlatformLink

logger = structlog.get_logger()

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Credential service definitions — describes which keys each service accepts
SERVICE_DEFINITIONS = {
    "claude_code": {
        "label": "Claude Code",
        "keys": [
            {"key": "credentials_json", "label": "Claude CLI Credentials JSON", "type": "textarea"},
        ],
    },
    "github": {
        "label": "GitHub",
        "keys": [
            {"key": "github_token", "label": "GitHub Token (PAT)", "type": "password"},
            {"key": "ssh_private_key", "label": "SSH Private Key", "type": "textarea"},
            {"key": "git_author_name", "label": "Git Author Name", "type": "text"},
            {"key": "git_author_email", "label": "Git Author Email", "type": "text"},
        ],
    },
    "garmin": {
        "label": "Garmin Connect",
        "keys": [
            {"key": "email", "label": "Email", "type": "text"},
            {"key": "password", "label": "Password", "type": "password"},
        ],
    },
    "renpho": {
        "label": "Renpho",
        "keys": [
            {"key": "email", "label": "Email", "type": "text"},
            {"key": "password", "label": "Password", "type": "password"},
        ],
    },
    "atlassian": {
        "label": "Atlassian",
        "keys": [
            {"key": "url", "label": "Instance URL", "type": "text"},
            {"key": "username", "label": "Username", "type": "text"},
            {"key": "api_token", "label": "API Token", "type": "password"},
        ],
    },
}


def _get_credential_store() -> CredentialStore:
    settings = get_settings()
    if not settings.credential_encryption_key:
        raise HTTPException(503, "Credential storage not configured")
    return CredentialStore(settings.credential_encryption_key)


# ---------------------------------------------------------------------------
# Credentials
# ---------------------------------------------------------------------------


@router.get("/credentials")
async def list_credentials(user: PortalUser = Depends(require_auth)) -> dict:
    """List configured services with metadata (no secret values returned)."""
    store = _get_credential_store()
    factory = get_session_factory()
    async with factory() as session:
        configured = await store.list_services(session, user.user_id)

    # Merge with service definitions so frontend knows all available services
    result = []
    configured_map = {s["service"]: s for s in configured}
    for svc_name, svc_def in SERVICE_DEFINITIONS.items():
        entry = {
            "service": svc_name,
            "label": svc_def["label"],
            "keys": [k["key"] for k in svc_def["keys"]],
            "key_definitions": svc_def["keys"],
            "configured": svc_name in configured_map,
            "configured_keys": configured_map[svc_name]["keys"]
            if svc_name in configured_map
            else [],
            "configured_at": configured_map[svc_name]["configured_at"]
            if svc_name in configured_map
            else None,
        }
        result.append(entry)

    return {"services": result}


class CredentialUpdate(BaseModel):
    credentials: dict[str, str]


@router.put("/credentials/{service}")
async def upsert_credentials(
    service: str,
    body: CredentialUpdate,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Upsert credentials for a service. Values are encrypted before storage."""
    if service not in SERVICE_DEFINITIONS:
        raise HTTPException(400, f"Unknown service: {service}")

    valid_keys = {k["key"] for k in SERVICE_DEFINITIONS[service]["keys"]}
    invalid = set(body.credentials.keys()) - valid_keys
    if invalid:
        raise HTTPException(400, f"Invalid keys for {service}: {invalid}")

    # Filter out empty values — don't store blanks
    to_store = {k: v for k, v in body.credentials.items() if v.strip()}
    if not to_store:
        raise HTTPException(400, "No non-empty credentials provided")

    store = _get_credential_store()
    factory = get_session_factory()
    async with factory() as session:
        await store.set_many(session, user.user_id, service, to_store)

    logger.info(
        "credentials_updated",
        user_id=str(user.user_id),
        service=service,
        keys=list(to_store.keys()),
    )
    return {"status": "ok", "service": service, "keys": list(to_store.keys())}


@router.delete("/credentials/{service}")
async def delete_service_credentials(
    service: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Delete all credentials for a service."""
    store = _get_credential_store()
    factory = get_session_factory()
    async with factory() as session:
        count = await store.delete(session, user.user_id, service)
    return {"status": "ok", "deleted": count}


@router.delete("/credentials/{service}/{key}")
async def delete_credential_key(
    service: str,
    key: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Delete a single credential key for a service."""
    store = _get_credential_store()
    factory = get_session_factory()
    async with factory() as session:
        count = await store.delete(session, user.user_id, service, key)
    return {"status": "ok", "deleted": count}


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------


@router.get("/profile")
async def get_profile(user: PortalUser = Depends(require_auth)) -> dict:
    """Get user profile info."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(User).where(User.id == user.user_id)
        )
        db_user = result.scalar_one_or_none()

    if not db_user:
        raise HTTPException(404, "User not found")

    return {
        "user_id": str(db_user.id),
        "username": user.username,
        "permission_level": db_user.permission_level,
        "token_budget_monthly": db_user.token_budget_monthly,
        "tokens_used_this_month": db_user.tokens_used_this_month,
        "created_at": db_user.created_at.isoformat() if db_user.created_at else None,
    }


# ---------------------------------------------------------------------------
# Connected accounts
# ---------------------------------------------------------------------------


@router.get("/connected-accounts")
async def get_connected_accounts(user: PortalUser = Depends(require_auth)) -> dict:
    """List linked OAuth platform accounts."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(UserPlatformLink).where(
                UserPlatformLink.user_id == user.user_id
            )
        )
        links = result.scalars().all()

    accounts = [
        {
            "platform": link.platform,
            "username": link.platform_username,
            "platform_user_id": link.platform_user_id,
        }
        for link in links
        if link.platform != "web"  # hide internal web link
    ]

    return {"accounts": accounts}
