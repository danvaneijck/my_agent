"""Error manager tool implementations."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy import func, select

from shared.database import get_session_factory
from shared.models.error_log import ErrorLog

logger = structlog.get_logger()


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


class ErrorManagerTools:
    """Tool implementations for error log management."""

    def __init__(self) -> None:
        self._session_factory = get_session_factory()

    async def list_errors(
        self,
        status: str = "open",
        service: str | None = None,
        error_type: str | None = None,
        limit: int = 20,
        **_,
    ) -> dict:
        """List errors with optional filters."""
        async with self._session_factory() as session:
            query = select(ErrorLog).order_by(ErrorLog.created_at.desc())

            if status:
                query = query.where(ErrorLog.status == status)
            if service:
                query = query.where(ErrorLog.service == service)
            if error_type:
                query = query.where(ErrorLog.error_type == error_type)

            query = query.limit(min(limit, 50))
            result = await session.execute(query)
            errors = result.scalars().all()

            # Also get total open count for context
            open_result = await session.execute(
                select(func.count()).where(ErrorLog.status == "open")
            )
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

    async def error_summary(self, **_) -> dict:
        """Get summary counts of errors by status and service."""
        async with self._session_factory() as session:
            # Counts by status
            for status_name in ("open", "dismissed", "resolved"):
                pass  # computed below

            total_open = await session.execute(
                select(func.count()).where(ErrorLog.status == "open")
            )
            total_dismissed = await session.execute(
                select(func.count()).where(ErrorLog.status == "dismissed")
            )
            total_resolved = await session.execute(
                select(func.count()).where(ErrorLog.status == "resolved")
            )

            # Breakdown of open errors by service and type
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

        return {
            "open": total_open.scalar_one(),
            "dismissed": total_dismissed.scalar_one(),
            "resolved": total_resolved.scalar_one(),
            "by_service_and_type": [
                {"service": r.service, "error_type": r.error_type, "count": r.count}
                for r in groups
            ],
        }

    async def get_error(self, error_id: str, **_) -> dict:
        """Get full details of a single error."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ErrorLog).where(ErrorLog.id == uuid.UUID(error_id))
            )
            err = result.scalar_one_or_none()
            if not err:
                raise ValueError(f"Error not found: {error_id}")
            return _format_error(err, include_trace=True)

    async def dismiss_error(self, error_id: str, **_) -> dict:
        """Mark a single error as dismissed."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ErrorLog).where(ErrorLog.id == uuid.UUID(error_id))
            )
            err = result.scalar_one_or_none()
            if not err:
                raise ValueError(f"Error not found: {error_id}")
            err.status = "dismissed"
            await session.commit()
            return {"id": error_id, "status": "dismissed"}

    async def resolve_error(self, error_id: str, **_) -> dict:
        """Mark a single error as resolved."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(ErrorLog).where(ErrorLog.id == uuid.UUID(error_id))
            )
            err = result.scalar_one_or_none()
            if not err:
                raise ValueError(f"Error not found: {error_id}")
            err.status = "resolved"
            err.resolved_at = datetime.now(timezone.utc)
            await session.commit()
            return {"id": error_id, "status": "resolved"}

    async def bulk_dismiss(self, error_ids: list[str], **_) -> dict:
        """Dismiss multiple errors at once."""
        dismissed = []
        not_found = []
        async with self._session_factory() as session:
            for eid in error_ids:
                result = await session.execute(
                    select(ErrorLog).where(ErrorLog.id == uuid.UUID(eid))
                )
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

    async def bulk_resolve(self, error_ids: list[str], **_) -> dict:
        """Resolve multiple errors at once."""
        resolved = []
        not_found = []
        now = datetime.now(timezone.utc)
        async with self._session_factory() as session:
            for eid in error_ids:
                result = await session.execute(
                    select(ErrorLog).where(ErrorLog.id == uuid.UUID(eid))
                )
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
