"""Async helper for persisting errors to the error_logs table.

Usage (fire-and-forget from async code):
    import asyncio
    from shared.error_capture import capture_error

    asyncio.create_task(capture_error(
        session_factory,
        service="research",
        error_type="tool_execution",
        error_message=str(e),
        tool_name="research.web_search",
        tool_arguments={"query": "..."},
        user_id=str(user_id),
    ))

The function is wrapped in a broad try/except so it can never propagate
exceptions to the caller — error capturing must not break normal flow.
"""

from __future__ import annotations

import re
import uuid

import structlog

from shared.models.error_log import ErrorLog

logger = structlog.get_logger()

# Keys whose values should be redacted before storing in the DB.
_SECRET_KEY_PATTERN = re.compile(
    r"(token|key|secret|password|credential|auth|api_key|access_key)",
    re.IGNORECASE,
)


def _sanitize_args(args: dict | None) -> dict | None:
    """Strip secret-looking values from a dict before persisting."""
    if not args:
        return args
    sanitized = {}
    for k, v in args.items():
        if _SECRET_KEY_PATTERN.search(k):
            sanitized[k] = "[REDACTED]"
        else:
            sanitized[k] = v
    return sanitized


async def capture_error(
    session_factory,
    *,
    service: str,
    error_type: str,
    error_message: str,
    tool_name: str | None = None,
    tool_arguments: dict | None = None,
    stack_trace: str | None = None,
    user_id: str | None = None,
    conversation_id: str | None = None,
) -> None:
    """Persist an error to the error_logs table.

    Safe to call with asyncio.create_task() — never raises.
    """
    try:
        parsed_user_id: uuid.UUID | None = None
        parsed_conv_id: uuid.UUID | None = None

        if user_id:
            try:
                parsed_user_id = uuid.UUID(user_id)
            except (ValueError, AttributeError):
                pass

        if conversation_id:
            try:
                parsed_conv_id = uuid.UUID(conversation_id)
            except (ValueError, AttributeError):
                pass

        async with session_factory() as session:
            record = ErrorLog(
                service=service,
                error_type=error_type,
                error_message=error_message,
                tool_name=tool_name,
                tool_arguments=_sanitize_args(tool_arguments),
                stack_trace=stack_trace,
                user_id=parsed_user_id,
                conversation_id=parsed_conv_id,
            )
            session.add(record)
            await session.commit()

        logger.debug(
            "error_captured",
            service=service,
            error_type=error_type,
            tool_name=tool_name,
        )
    except Exception:
        # Never let error capturing crash the caller.
        logger.warning("error_capture_failed", exc_info=True)
