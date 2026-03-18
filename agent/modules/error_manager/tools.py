"""Error manager tool implementations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select

from shared.database import get_session_factory
from shared.models.error_log import ErrorLog

logger = structlog.get_logger()

# Admin permission levels — users with these levels see all errors.
# Regular users only see errors associated with their own user_id.
_ADMIN_LEVELS = {"admin", "owner"}


def _format_error(err: ErrorLog, include_trace: bool = False) -> dict:
    """Format an ErrorLog row for tool output."""
    data = {
        "id": str(err.id),
        "service": err.service,
        "error_type": err.error_type,
        "tool_name": err.tool_name,
        "error_message": err.error_message,
        "status": err.status,
        "created_at": err.created_at.isoformat() if err.created_at else None,
    }
    if include_trace:
        data["tool_arguments"] = err.tool_arguments
        data["stack_trace"] = err.stack_trace
        data["user_id"] = str(err.user_id) if err.user_id else None
        data["conversation_id"] = str(err.conversation_id) if err.conversation_id else None
        data["resolved_at"] = err.resolved_at.isoformat() if err.resolved_at else None
    return data


async def _get_user_permission(session, user_id: str) -> str:
    """Look up the user's permission level."""
    from shared.models.user import User

    result = await session.execute(
        select(User.permission_level).where(User.id == uuid.UUID(user_id))
    )
    row = result.scalar_one_or_none()
    return row or "guest"


class ErrorManagerTools:
    """Tool implementations for error log management."""

    def __init__(self) -> None:
        self._session_factory = get_session_factory()

    def _scope_query(self, query, user_id: str | None, is_admin: bool):
        """Scope a query to the user's own errors unless admin."""
        if not is_admin and user_id:
            query = query.where(ErrorLog.user_id == uuid.UUID(user_id))
        return query

    async def list_errors(
        self,
        status: str = "open",
        service: str | None = None,
        error_type: str | None = None,
        limit: int = 20,
        user_id: str | None = None,
        **_,
    ) -> dict:
        """List errors with optional filters."""
        async with self._session_factory() as session:
            is_admin = (await _get_user_permission(session, user_id)) in _ADMIN_LEVELS if user_id else False

            query = select(ErrorLog).order_by(ErrorLog.created_at.desc())
            query = self._scope_query(query, user_id, is_admin)

            if status:
                query = query.where(ErrorLog.status == status)
            if service:
                query = query.where(ErrorLog.service == service)
            if error_type:
                query = query.where(ErrorLog.error_type == error_type)

            query = query.limit(min(limit, 50))
            result = await session.execute(query)
            errors = result.scalars().all()

            # Scoped open count
            open_query = select(func.count()).where(ErrorLog.status == "open")
            if not is_admin and user_id:
                open_query = open_query.where(ErrorLog.user_id == uuid.UUID(user_id))
            open_result = await session.execute(open_query)
            open_count = open_result.scalar_one()

        return {
            "errors": [_format_error(e) for e in errors],
            "count": len(errors),
            "open_count": open_count,
            "filters": {
                "status": status,
                "service": service,
                "error_type": error_type,
            },
        }

    async def error_summary(self, user_id: str | None = None, **_) -> dict:
        """Get summary counts of errors by status and service."""
        async with self._session_factory() as session:
            is_admin = (await _get_user_permission(session, user_id)) in _ADMIN_LEVELS if user_id else False

            def _scoped_count(status_val: str):
                q = select(func.count()).where(ErrorLog.status == status_val)
                if not is_admin and user_id:
                    q = q.where(ErrorLog.user_id == uuid.UUID(user_id))
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
            if not is_admin and user_id:
                breakdown = breakdown.where(ErrorLog.user_id == uuid.UUID(user_id))
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

    async def get_error(self, error_id: str, user_id: str | None = None, **_) -> dict:
        """Get full details of a single error."""
        async with self._session_factory() as session:
            is_admin = (await _get_user_permission(session, user_id)) in _ADMIN_LEVELS if user_id else False

            query = select(ErrorLog).where(ErrorLog.id == uuid.UUID(error_id))
            query = self._scope_query(query, user_id, is_admin)
            result = await session.execute(query)
            err = result.scalar_one_or_none()
            if not err:
                raise ValueError(f"Error not found: {error_id}")
            return _format_error(err, include_trace=True)

    async def dismiss_error(self, error_id: str, user_id: str | None = None, **_) -> dict:
        """Mark a single error as dismissed."""
        async with self._session_factory() as session:
            is_admin = (await _get_user_permission(session, user_id)) in _ADMIN_LEVELS if user_id else False

            query = select(ErrorLog).where(ErrorLog.id == uuid.UUID(error_id))
            query = self._scope_query(query, user_id, is_admin)
            result = await session.execute(query)
            err = result.scalar_one_or_none()
            if not err:
                raise ValueError(f"Error not found: {error_id}")
            err.status = "dismissed"
            await session.commit()
            return {"id": error_id, "status": "dismissed"}

    async def resolve_error(self, error_id: str, user_id: str | None = None, **_) -> dict:
        """Mark a single error as resolved."""
        async with self._session_factory() as session:
            is_admin = (await _get_user_permission(session, user_id)) in _ADMIN_LEVELS if user_id else False

            query = select(ErrorLog).where(ErrorLog.id == uuid.UUID(error_id))
            query = self._scope_query(query, user_id, is_admin)
            result = await session.execute(query)
            err = result.scalar_one_or_none()
            if not err:
                raise ValueError(f"Error not found: {error_id}")
            err.status = "resolved"
            err.resolved_at = datetime.now(timezone.utc)
            await session.commit()
            return {"id": error_id, "status": "resolved"}

    async def bulk_dismiss(self, error_ids: list[str], user_id: str | None = None, **_) -> dict:
        """Dismiss multiple errors at once."""
        dismissed = []
        not_found = []
        async with self._session_factory() as session:
            is_admin = (await _get_user_permission(session, user_id)) in _ADMIN_LEVELS if user_id else False

            for eid in error_ids:
                query = select(ErrorLog).where(ErrorLog.id == uuid.UUID(eid))
                query = self._scope_query(query, user_id, is_admin)
                result = await session.execute(query)
                err = result.scalar_one_or_none()
                if err:
                    err.status = "dismissed"
                    dismissed.append(eid)
                else:
                    not_found.append(eid)
            await session.commit()
        return {
            "dismissed": len(dismissed),
            "not_found": not_found,
        }

    async def bulk_resolve(self, error_ids: list[str], user_id: str | None = None, **_) -> dict:
        """Resolve multiple errors at once."""
        resolved = []
        not_found = []
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            is_admin = (await _get_user_permission(session, user_id)) in _ADMIN_LEVELS if user_id else False

            for eid in error_ids:
                query = select(ErrorLog).where(ErrorLog.id == uuid.UUID(eid))
                query = self._scope_query(query, user_id, is_admin)
                result = await session.execute(query)
                err = result.scalar_one_or_none()
                if err:
                    err.status = "resolved"
                    err.resolved_at = now
                    resolved.append(eid)
                else:
                    not_found.append(eid)
            await session.commit()
        return {
            "resolved": len(resolved),
            "not_found": not_found,
        }
