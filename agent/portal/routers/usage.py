"""Usage analytics endpoints — token usage from DB + Anthropic API usage."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx
import structlog
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select, text

from portal.auth import PortalUser, require_auth
from portal.claude_oauth import (
    build_credentials_json,
    parse_credentials_json,
    refresh_access_token,
)
from shared.config import get_settings
from shared.credential_store import CredentialStore
from shared.database import get_session_factory
from shared.models.token_usage import TokenLog
from shared.models.user import User

logger = structlog.get_logger()

router = APIRouter(prefix="/api/usage", tags=["usage"])


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------


@router.get("/summary")
async def usage_summary(user: PortalUser = Depends(require_auth)) -> dict:
    """Token usage summary for the current user."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(User).where(User.id == user.user_id)
        )
        db_user = result.scalar_one_or_none()
        if not db_user:
            raise HTTPException(404, "User not found")

        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # All-time totals
        all_time = await session.execute(
            select(
                func.coalesce(func.sum(TokenLog.input_tokens), 0),
                func.coalesce(func.sum(TokenLog.output_tokens), 0),
                func.coalesce(func.sum(TokenLog.cost_estimate), 0.0),
                func.count(TokenLog.id),
            ).where(TokenLog.user_id == user.user_id)
        )
        at = all_time.one()

        # This month totals
        this_month = await session.execute(
            select(
                func.coalesce(func.sum(TokenLog.input_tokens), 0),
                func.coalesce(func.sum(TokenLog.output_tokens), 0),
                func.coalesce(func.sum(TokenLog.cost_estimate), 0.0),
                func.count(TokenLog.id),
            ).where(
                TokenLog.user_id == user.user_id,
                TokenLog.created_at >= month_start,
            )
        )
        tm = this_month.one()

    return {
        "token_budget_monthly": db_user.token_budget_monthly,
        "tokens_used_this_month": db_user.tokens_used_this_month,
        "budget_reset_at": db_user.budget_reset_at.isoformat()
        if db_user.budget_reset_at
        else None,
        "all_time": {
            "input_tokens": at[0],
            "output_tokens": at[1],
            "total_tokens": at[0] + at[1],
            "cost": round(at[2], 4),
            "requests": at[3],
        },
        "this_month": {
            "input_tokens": tm[0],
            "output_tokens": tm[1],
            "total_tokens": tm[0] + tm[1],
            "cost": round(tm[2], 4),
            "requests": tm[3],
        },
    }


# ---------------------------------------------------------------------------
# History (last 30 days)
# ---------------------------------------------------------------------------


@router.get("/history")
async def usage_history(user: PortalUser = Depends(require_auth)) -> dict:
    """Daily usage breakdown for the last 30 days, plus by-model totals."""
    factory = get_session_factory()
    async with factory() as session:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        daily = await session.execute(
            select(
                func.date_trunc("day", TokenLog.created_at).label("day"),
                func.sum(TokenLog.input_tokens).label("input_tokens"),
                func.sum(TokenLog.output_tokens).label("output_tokens"),
                func.sum(TokenLog.cost_estimate).label("cost"),
                func.count(TokenLog.id).label("requests"),
            )
            .where(
                TokenLog.user_id == user.user_id,
                TokenLog.created_at > cutoff,
            )
            .group_by(text("1"))
            .order_by(text("1"))
        )
        daily_rows = daily.all()

        by_model = await session.execute(
            select(
                TokenLog.model,
                func.sum(TokenLog.input_tokens + TokenLog.output_tokens).label(
                    "total_tokens"
                ),
                func.sum(TokenLog.cost_estimate).label("total_cost"),
                func.count(TokenLog.id).label("requests"),
            )
            .where(
                TokenLog.user_id == user.user_id,
                TokenLog.created_at > cutoff,
            )
            .group_by(TokenLog.model)
            .order_by(text("2 DESC"))
        )
        model_rows = by_model.all()

    return {
        "daily": [
            {
                "date": row.day.isoformat() if row.day else None,
                "input_tokens": row.input_tokens or 0,
                "output_tokens": row.output_tokens or 0,
                "cost": round(row.cost or 0, 4),
                "requests": row.requests or 0,
            }
            for row in daily_rows
        ],
        "by_model": [
            {
                "model": row.model,
                "total_tokens": row.total_tokens or 0,
                "total_cost": round(row.total_cost or 0, 4),
                "requests": row.requests or 0,
            }
            for row in model_rows
        ],
    }


# ---------------------------------------------------------------------------
# Anthropic API usage (via user's stored Claude CLI OAuth credentials)
# ---------------------------------------------------------------------------


@router.get("/anthropic")
async def anthropic_usage(user: PortalUser = Depends(require_auth)) -> dict:
    """Claude API usage (5-hour and weekly) via stored OAuth credentials."""
    settings = get_settings()
    not_available = {"available": False, "five_hour": None, "seven_day": None}

    if not settings.credential_encryption_key:
        logger.info("anthropic_usage_skip", reason="no_encryption_key")
        return not_available

    store = CredentialStore(settings.credential_encryption_key)
    factory = get_session_factory()

    async with factory() as session:
        creds_raw = await store.get(
            session, user.user_id, "claude_code", "credentials_json"
        )

    if not creds_raw:
        logger.info("anthropic_usage_skip", reason="no_credentials_stored")
        return not_available

    # Extract OAuth tokens using shared parser
    oauth = parse_credentials_json(creds_raw)
    if not oauth:
        logger.warning("anthropic_usage_bad_credentials", user_id=str(user.user_id))
        return not_available

    access_token = oauth.get("accessToken") or oauth.get("access_token")
    refresh_tok = oauth.get("refreshToken") or oauth.get("refresh_token")
    if not access_token:
        logger.warning("anthropic_usage_no_access_token", user_id=str(user.user_id))
        return not_available

    async def _fetch_usage(token: str) -> httpx.Response:
        return await client.get(
            "https://api.anthropic.com/api/oauth/usage",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "anthropic-beta": "oauth-2025-04-20",
            },
        )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await _fetch_usage(access_token)

            # If 401 and we have a refresh token, try refreshing
            if resp.status_code == 401 and refresh_tok:
                logger.info("anthropic_usage_refreshing_token", user_id=str(user.user_id))
                new_tokens = await refresh_access_token(refresh_tok)
                if new_tokens:
                    # Update stored credentials with new tokens
                    updated_creds = build_credentials_json(new_tokens)
                    async with factory() as session:
                        await store.set(
                            session,
                            user.user_id,
                            "claude_code",
                            "credentials_json",
                            updated_creds,
                        )

                    resp = await _fetch_usage(new_tokens["access_token"])

            logger.info(
                "anthropic_usage_response",
                status=resp.status_code,
                body=resp.text[:500],
            )
            if resp.status_code != 200:
                return not_available

            data = resp.json()
            return {
                "available": True,
                "five_hour": _normalize_window(data.get("five_hour")),
                "seven_day": _normalize_window(data.get("seven_day")),
            }
    except Exception as e:
        logger.error("anthropic_usage_exception", error=str(e))
        return not_available


def _normalize_window(window: dict | None) -> dict | None:
    """Map Anthropic API fields to what the frontend expects."""
    if not window:
        return None
    reset_iso = window.get("resets_at")
    reset_ts = 0
    if reset_iso:
        try:
            reset_ts = int(
                datetime.fromisoformat(reset_iso).timestamp() * 1000
            )
        except (ValueError, TypeError):
            pass
    return {
        "utilization_percent": window.get("utilization", 0),
        "reset_timestamp": reset_ts,
    }
