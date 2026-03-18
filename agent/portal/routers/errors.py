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


def _is_admin(user: PortalUser) -> bool:
    return user.permission_level in ADMIN_LEVELS


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


def _scope_query(query, user: PortalUser):
    """Scope a query to the user's own errors unless they are admin/owner."""
    if not _is_admin(user):
        query = query.where(ErrorLog.user_id == user.user_id)
    return query


def _scope_filter(user: PortalUser):
    """Return a WHERE clause for scoping counts to the user."""
    if _is_admin(user):
        return True  # no filter
    return ErrorLog.user_id == user.user_id


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

    Admins/owners see all errors. Regular users see only their own.
    """
    factory = get_session_factory()
    async with factory() as session:
        query = select(ErrorLog).order_by(ErrorLog.created_at.desc())
        query = _scope_query(query, user)

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

        # Open count (scoped)
        open_query = select(func.count()).where(ErrorLog.status == "open")
        scope = _scope_filter(user)
        if scope is not True:
            open_query = open_query.where(scope)
        open_result = await session.execute(open_query)
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
    """Count of open errors grouped by service and error_type.

    Admins/owners see all errors. Regular users see only their own.
    """
    factory = get_session_factory()
    async with factory() as session:
        scope = _scope_filter(user)

        def _scoped_count(status_val: str):
            q = select(func.count()).where(ErrorLog.status == status_val)
            if scope is not True:
                q = q.where(scope)
            return q

        total_open = await session.execute(_scoped_count("open"))
        total_dismissed = await session.execute(_scoped_count("dismissed"))
        total_resolved = await session.execute(_scoped_count("resolved"))

        breakdown = (
            select(
                ErrorLog.service,
                ErrorLog.error_type,
                func.count(ErrorLog.id).label("count"),
            )
            .where(ErrorLog.status == "open")
            .group_by(ErrorLog.service, ErrorLog.error_type)
            .order_by(func.count(ErrorLog.id).desc())
        )
        if scope is not True:
            breakdown = breakdown.where(scope)
        rows = await session.execute(breakdown)
        groups = rows.all()

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
    factory = get_session_factory()
    async with factory() as session:
        query = select(ErrorLog).where(ErrorLog.id == error_id)
        query = _scope_query(query, user)
        result = await session.execute(query)
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
    factory = get_session_factory()
    async with factory() as session:
        query = select(ErrorLog).where(ErrorLog.id == error_id)
        query = _scope_query(query, user)
        result = await session.execute(query)
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
    factory = get_session_factory()
    async with factory() as session:
        query = select(ErrorLog).where(ErrorLog.id == error_id)
        query = _scope_query(query, user)
        result = await session.execute(query)
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
    factory = get_session_factory()
    async with factory() as session:
        query = select(ErrorLog).where(ErrorLog.id == error_id)
        query = _scope_query(query, user)
        result = await session.execute(query)
        err = result.scalar_one_or_none()
        if not err:
            raise HTTPException(status_code=404, detail="Error not found")
        err.status = "open"
        err.resolved_at = None
        await session.commit()
        return {"status": "open", "id": str(error_id)}
