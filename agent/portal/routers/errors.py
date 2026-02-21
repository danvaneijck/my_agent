"""Error log endpoints — list, inspect, dismiss, and resolve captured errors."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select

from portal.auth import PortalUser, require_auth
from shared.database import get_session_factory
from shared.models.error_log import ErrorLog

logger = structlog.get_logger()

router = APIRouter(prefix="/api/errors", tags=["errors"])

ADMIN_LEVELS = {"admin", "owner"}


def _require_admin(user: PortalUser) -> None:
    if user.permission_level not in ADMIN_LEVELS:
        raise HTTPException(status_code=403, detail="Admin or owner permission required")


def _format_error(err: ErrorLog) -> dict:
    return {
        "id": str(err.id),
        "service": err.service,
        "error_type": err.error_type,
        "tool_name": err.tool_name,
        "tool_arguments": err.tool_arguments,
        "error_message": err.error_message,
        "stack_trace": err.stack_trace,
        "user_id": str(err.user_id) if err.user_id else None,
        "conversation_id": str(err.conversation_id) if err.conversation_id else None,
        "status": err.status,
        "created_at": err.created_at.isoformat() if err.created_at else None,
        "resolved_at": err.resolved_at.isoformat() if err.resolved_at else None,
    }


@router.get("")
async def list_errors(
    status: str | None = None,
    service: str | None = None,
    error_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List error log entries with optional filters.

    Defaults to showing all errors (open, dismissed, resolved).
    Pass status=open to show only unresolved errors.
    """
    _require_admin(user)
    factory = get_session_factory()
    async with factory() as session:
        query = select(ErrorLog).order_by(ErrorLog.created_at.desc())

        if status:
            query = query.where(ErrorLog.status == status)
        if service:
            query = query.where(ErrorLog.service == service)
        if error_type:
            query = query.where(ErrorLog.error_type == error_type)

        # Total count (before pagination)
        count_result = await session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        # Open count
        open_result = await session.execute(
            select(func.count()).where(ErrorLog.status == "open")
        )
        open_count = open_result.scalar_one()

        paginated = query.offset(offset).limit(limit)
        result = await session.execute(paginated)
        errors = result.scalars().all()

    return {
        "errors": [_format_error(e) for e in errors],
        "total": total,
        "open_count": open_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/summary")
async def error_summary(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Count of open errors grouped by service and error_type."""
    _require_admin(user)
    factory = get_session_factory()
    async with factory() as session:
        rows = await session.execute(
            select(
                ErrorLog.service,
                ErrorLog.error_type,
                func.count(ErrorLog.id).label("count"),
            )
            .where(ErrorLog.status == "open")
            .group_by(ErrorLog.service, ErrorLog.error_type)
            .order_by(func.count(ErrorLog.id).desc())
        )
        groups = rows.all()

        total_open = await session.execute(
            select(func.count()).where(ErrorLog.status == "open")
        )
        total_dismissed = await session.execute(
            select(func.count()).where(ErrorLog.status == "dismissed")
        )
        total_resolved = await session.execute(
            select(func.count()).where(ErrorLog.status == "resolved")
        )

    return {
        "open": total_open.scalar_one(),
        "dismissed": total_dismissed.scalar_one(),
        "resolved": total_resolved.scalar_one(),
        "by_service_and_type": [
            {"service": r.service, "error_type": r.error_type, "count": r.count}
            for r in groups
        ],
    }


@router.get("/{error_id}")
async def get_error(
    error_id: uuid.UUID,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get full detail for a single error including stack trace."""
    _require_admin(user)
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ErrorLog).where(ErrorLog.id == error_id)
        )
        err = result.scalar_one_or_none()
        if not err:
            raise HTTPException(status_code=404, detail="Error not found")
        return _format_error(err)


@router.post("/{error_id}/dismiss")
async def dismiss_error(
    error_id: uuid.UUID,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Mark an error as dismissed (acknowledged, not necessarily fixed)."""
    _require_admin(user)
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ErrorLog).where(ErrorLog.id == error_id)
        )
        err = result.scalar_one_or_none()
        if not err:
            raise HTTPException(status_code=404, detail="Error not found")
        err.status = "dismissed"
        await session.commit()
        return {"status": "dismissed", "id": str(error_id)}


@router.post("/{error_id}/resolve")
async def resolve_error(
    error_id: uuid.UUID,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Mark an error as resolved (fix deployed)."""
    _require_admin(user)
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ErrorLog).where(ErrorLog.id == error_id)
        )
        err = result.scalar_one_or_none()
        if not err:
            raise HTTPException(status_code=404, detail="Error not found")
        err.status = "resolved"
        err.resolved_at = datetime.now(timezone.utc)
        await session.commit()
        return {"status": "resolved", "id": str(error_id)}


@router.post("/{error_id}/reopen")
async def reopen_error(
    error_id: uuid.UUID,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Reopen a previously dismissed or resolved error."""
    _require_admin(user)
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(ErrorLog).where(ErrorLog.id == error_id)
        )
        err = result.scalar_one_or_none()
        if not err:
            raise HTTPException(status_code=404, detail="Error not found")
        err.status = "open"
        err.resolved_at = None
        await session.commit()
        return {"status": "open", "id": str(error_id)}
