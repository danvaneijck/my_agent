"""Admin analytics dashboard for the AI agent system."""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from shared.config import get_settings
from shared.database import get_session_factory
from shared.models.conversation import Conversation, Message
from shared.models.file import FileRecord
from shared.models.memory import MemorySummary
from shared.models.persona import Persona
from shared.models.token_usage import TokenLog
from shared.models.user import User, UserPlatformLink

app = FastAPI(title="Agent Admin Dashboard", version="1.0.0")
settings = get_settings()


async def _get_session() -> AsyncSession:
    factory = get_session_factory()
    async with factory() as session:
        yield session


@app.get("/api/overview")
async def overview():
    """High-level system stats."""
    factory = get_session_factory()
    async with factory() as s:
        now = datetime.now(timezone.utc)
        day_ago = now - timedelta(days=1)
        week_ago = now - timedelta(days=7)

        total_users = (await s.execute(select(func.count(User.id)))).scalar() or 0
        total_conversations = (await s.execute(select(func.count(Conversation.id)))).scalar() or 0
        total_messages = (await s.execute(select(func.count(Message.id)))).scalar() or 0

        active_conversations_24h = (await s.execute(
            select(func.count(Conversation.id)).where(Conversation.last_active_at > day_ago)
        )).scalar() or 0

        total_tokens = (await s.execute(
            select(func.coalesce(func.sum(TokenLog.input_tokens + TokenLog.output_tokens), 0))
        )).scalar() or 0

        total_cost = (await s.execute(
            select(func.coalesce(func.sum(TokenLog.cost_estimate), 0.0))
        )).scalar() or 0.0

        tokens_7d = (await s.execute(
            select(func.coalesce(func.sum(TokenLog.input_tokens + TokenLog.output_tokens), 0))
            .where(TokenLog.created_at > week_ago)
        )).scalar() or 0

        cost_7d = (await s.execute(
            select(func.coalesce(func.sum(TokenLog.cost_estimate), 0.0))
            .where(TokenLog.created_at > week_ago)
        )).scalar() or 0.0

        total_files = (await s.execute(select(func.count(FileRecord.id)))).scalar() or 0
        total_memories = (await s.execute(select(func.count(MemorySummary.id)))).scalar() or 0

        return {
            "total_users": total_users,
            "total_conversations": total_conversations,
            "total_messages": total_messages,
            "active_conversations_24h": active_conversations_24h,
            "total_tokens": total_tokens,
            "total_cost": round(total_cost, 4),
            "tokens_7d": tokens_7d,
            "cost_7d": round(cost_7d, 4),
            "total_files": total_files,
            "total_memories": total_memories,
        }


@app.get("/api/users")
async def users_list():
    """All users with platform links and usage stats."""
    factory = get_session_factory()
    async with factory() as s:
        users_result = await s.execute(
            select(User).order_by(User.created_at.desc())
        )
        users = users_result.scalars().all()

        data = []
        for u in users:
            links_result = await s.execute(
                select(UserPlatformLink).where(UserPlatformLink.user_id == u.id)
            )
            links = links_result.scalars().all()

            # Token usage stats
            usage = await s.execute(
                select(
                    func.coalesce(func.sum(TokenLog.input_tokens + TokenLog.output_tokens), 0),
                    func.coalesce(func.sum(TokenLog.cost_estimate), 0.0),
                    func.count(TokenLog.id),
                ).where(TokenLog.user_id == u.id)
            )
            row = usage.one()

            conv_count = (await s.execute(
                select(func.count(Conversation.id)).where(Conversation.user_id == u.id)
            )).scalar() or 0

            msg_count = (await s.execute(
                select(func.count(Message.id))
                .join(Conversation, Message.conversation_id == Conversation.id)
                .where(Conversation.user_id == u.id)
            )).scalar() or 0

            data.append({
                "id": str(u.id),
                "permission_level": u.permission_level,
                "token_budget_monthly": u.token_budget_monthly,
                "tokens_used_this_month": u.tokens_used_this_month,
                "budget_reset_at": u.budget_reset_at.isoformat() if u.budget_reset_at else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "total_tokens_all_time": row[0],
                "total_cost_all_time": round(row[1], 4),
                "total_requests": row[2],
                "total_conversations": conv_count,
                "total_messages": msg_count,
                "platforms": [
                    {
                        "platform": lnk.platform,
                        "platform_user_id": lnk.platform_user_id,
                        "platform_username": lnk.platform_username,
                    }
                    for lnk in links
                ],
            })

        return data


@app.get("/api/token-usage")
async def token_usage():
    """Token usage grouped by day and model for the last 30 days."""
    factory = get_session_factory()
    async with factory() as s:
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        # Daily totals
        daily = await s.execute(
            select(
                func.date_trunc("day", TokenLog.created_at).label("day"),
                func.sum(TokenLog.input_tokens).label("input_tokens"),
                func.sum(TokenLog.output_tokens).label("output_tokens"),
                func.sum(TokenLog.cost_estimate).label("cost"),
                func.count(TokenLog.id).label("requests"),
            )
            .where(TokenLog.created_at > cutoff)
            .group_by(text("1"))
            .order_by(text("1"))
        )
        daily_rows = daily.all()

        # By model
        by_model = await s.execute(
            select(
                TokenLog.model,
                func.sum(TokenLog.input_tokens + TokenLog.output_tokens).label("total_tokens"),
                func.sum(TokenLog.cost_estimate).label("total_cost"),
                func.count(TokenLog.id).label("requests"),
            )
            .where(TokenLog.created_at > cutoff)
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


@app.get("/api/conversations")
async def conversations_list(limit: int = 50):
    """Recent conversations with message counts."""
    factory = get_session_factory()
    async with factory() as s:
        convs = await s.execute(
            select(Conversation).order_by(Conversation.last_active_at.desc()).limit(limit)
        )
        conversations = convs.scalars().all()

        data = []
        for c in conversations:
            msg_count = (await s.execute(
                select(func.count(Message.id)).where(Message.conversation_id == c.id)
            )).scalar() or 0

            # Get user info
            link = (await s.execute(
                select(UserPlatformLink).where(UserPlatformLink.user_id == c.user_id).limit(1)
            )).scalar_one_or_none()

            tool_calls = (await s.execute(
                select(func.count(Message.id))
                .where(Message.conversation_id == c.id, Message.role == "tool_call")
            )).scalar() or 0

            data.append({
                "id": str(c.id),
                "user_id": str(c.user_id),
                "username": link.platform_username if link else None,
                "platform": c.platform,
                "channel_id": c.platform_channel_id,
                "message_count": msg_count,
                "tool_calls": tool_calls,
                "started_at": c.started_at.isoformat() if c.started_at else None,
                "last_active_at": c.last_active_at.isoformat() if c.last_active_at else None,
                "is_summarized": c.is_summarized,
            })

        return data


@app.get("/api/personas")
async def personas_list():
    """All configured personas."""
    factory = get_session_factory()
    async with factory() as s:
        result = await s.execute(select(Persona).order_by(Persona.created_at.desc()))
        personas = result.scalars().all()

        data = []
        for p in personas:
            conv_count = (await s.execute(
                select(func.count(Conversation.id)).where(Conversation.persona_id == p.id)
            )).scalar() or 0

            data.append({
                "id": str(p.id),
                "name": p.name,
                "platform": p.platform,
                "platform_server_id": p.platform_server_id,
                "allowed_modules": p.allowed_modules,
                "default_model": p.default_model,
                "max_tokens_per_request": p.max_tokens_per_request,
                "is_default": p.is_default,
                "total_conversations": conv_count,
                "created_at": p.created_at.isoformat() if p.created_at else None,
            })

        return data


@app.get("/api/tool-usage")
async def tool_usage():
    """Tool call frequency from messages."""
    factory = get_session_factory()
    async with factory() as s:
        # Count tool_call messages, parse the tool name from JSON content
        result = await s.execute(
            text("""
                SELECT
                    content::json->>'name' AS tool_name,
                    COUNT(*) AS call_count,
                    COUNT(DISTINCT m.conversation_id) AS conversations
                FROM messages m
                WHERE m.role = 'tool_call'
                  AND content IS NOT NULL
                GROUP BY 1
                ORDER BY 2 DESC
            """)
        )
        rows = result.all()

        return [
            {
                "tool_name": row[0],
                "call_count": row[1],
                "conversations": row[2],
            }
            for row in rows
        ]


@app.get("/api/platform-stats")
async def platform_stats():
    """Breakdown of usage by platform."""
    factory = get_session_factory()
    async with factory() as s:
        # Users per platform
        users_by_platform = await s.execute(
            select(
                UserPlatformLink.platform,
                func.count(UserPlatformLink.id).label("user_count"),
            ).group_by(UserPlatformLink.platform)
        )

        # Conversations per platform
        convs_by_platform = await s.execute(
            select(
                Conversation.platform,
                func.count(Conversation.id).label("conv_count"),
            ).group_by(Conversation.platform)
        )

        # Messages per platform
        msgs_by_platform = await s.execute(
            select(
                Conversation.platform,
                func.count(Message.id).label("msg_count"),
            )
            .join(Conversation, Message.conversation_id == Conversation.id)
            .group_by(Conversation.platform)
        )

        return {
            "users": {row.platform: row.user_count for row in users_by_platform.all()},
            "conversations": {row.platform: row.conv_count for row in convs_by_platform.all()},
            "messages": {row.platform: row.msg_count for row in msgs_by_platform.all()},
        }


@app.get("/api/system-health")
async def system_health():
    """Check health of all module services."""
    import httpx

    modules = settings.module_services
    results = {}
    async with httpx.AsyncClient(timeout=5.0) as client:
        for name, url in modules.items():
            try:
                resp = await client.get(f"{url}/health")
                results[name] = {
                    "status": "healthy" if resp.status_code == 200 else "unhealthy",
                    "status_code": resp.status_code,
                }
            except Exception as e:
                results[name] = {"status": "unreachable", "error": str(e)}

    # Check core orchestrator
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.orchestrator_url}/health")
            results["core"] = {
                "status": "healthy" if resp.status_code == 200 else "unhealthy",
                "status_code": resp.status_code,
            }
    except Exception as e:
        results["core"] = {"status": "unreachable", "error": str(e)}

    return results


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the dashboard HTML."""
    html_path = Path(__file__).parent / "static" / "index.html"
    return HTMLResponse(content=html_path.read_text())
