"""Chat endpoints — REST and WebSocket for orchestrator interaction."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from portal.auth import PortalUser, require_auth, verify_ws_auth
from portal.services.core_client import send_message
from shared.config import get_settings
from shared.database import get_session_factory
from shared.models.conversation import Conversation, Message
from shared.models.memory import MemorySummary
from shared.models.scheduled_job import ScheduledJob
from shared.models.token_usage import TokenLog
from sqlalchemy import case, delete, func, select, update

logger = structlog.get_logger()

router = APIRouter(tags=["chat"])


def _parse_uuid(value: str) -> uuid.UUID | None:
    """Return a UUID if value is valid, else None."""
    try:
        return uuid.UUID(value) if value else None
    except ValueError:
        return None


async def _resolve_conversation_id(platform_channel_id: str) -> str | None:
    """Look up the real conversation ID from a platform_channel_id."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Conversation.id)
            .where(
                Conversation.platform == "web",
                Conversation.platform_channel_id == platform_channel_id,
            )
            .order_by(Conversation.last_active_at.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return str(row) if row else None


async def _resolve_platform_channel_id(conversation_id: str) -> str | None:
    """Look up the platform_channel_id from a real conversation ID."""
    parsed = _parse_uuid(conversation_id)
    if not parsed:
        return None
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Conversation.platform_channel_id).where(
                Conversation.id == parsed,
            )
        )
        return result.scalar_one_or_none()


async def _generate_title(conversation_id: str) -> None:
    """Generate an intelligent title for a conversation using LLM."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        return

    try:
        import anthropic

        factory = get_session_factory()
        async with factory() as session:
            # Get the first user message
            result = await session.execute(
                select(Message.content)
                .where(
                    Message.conversation_id == uuid.UUID(conversation_id),
                    Message.role == "user",
                )
                .order_by(Message.created_at.asc())
                .limit(1)
            )
            first_msg = result.scalar_one_or_none()
            if not first_msg:
                return

            client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            resp = await client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=30,
                messages=[
                    {
                        "role": "user",
                        "content": f"Generate a concise 3-6 word title for a conversation that starts with this message. Reply with ONLY the title, no quotes or punctuation:\n\n{first_msg[:500]}",
                    }
                ],
            )
            title = resp.content[0].text.strip().strip('"').strip("'")

            # Update the conversation title
            conv_result = await session.execute(
                select(Conversation).where(
                    Conversation.id == uuid.UUID(conversation_id)
                )
            )
            conv = conv_result.scalar_one_or_none()
            if conv and not conv.title:
                conv.title = title
                await session.commit()
                logger.info(
                    "conversation_title_generated",
                    conversation_id=conversation_id,
                    title=title,
                )
    except Exception as e:
        logger.error("title_generation_failed", error=str(e))


# --------------- Request schemas ---------------


class ChatSendRequest(BaseModel):
    content: str
    conversation_id: str | None = None
    attachments: list[dict] | None = None


class ConversationUpdateRequest(BaseModel):
    title: str


# --------------- REST endpoints ---------------


@router.get("/api/chat/conversations")
async def list_conversations(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List web platform conversations for the authenticated user."""
    factory = get_session_factory()
    async with factory() as session:
        # Unread count: if last_read_at is NULL, count all assistant messages;
        # otherwise count only those after last_read_at.
        all_assistant_subq = (
            select(func.count(Message.id))
            .where(
                Message.conversation_id == Conversation.id,
                Message.role == "assistant",
            )
            .correlate(Conversation)
            .scalar_subquery()
        )
        since_read_subq = (
            select(func.count(Message.id))
            .where(
                Message.conversation_id == Conversation.id,
                Message.role == "assistant",
                Message.created_at > Conversation.last_read_at,
            )
            .correlate(Conversation)
            .scalar_subquery()
        )
        unread_expr = case(
            (Conversation.last_read_at.is_(None), all_assistant_subq),
            else_=since_read_subq,
        ).label("unread_count")

        result = await session.execute(
            select(Conversation, unread_expr)
            .where(
                Conversation.platform == "web",
                Conversation.user_id == user.user_id,
            )
            .order_by(Conversation.last_active_at.desc())
            .limit(50)
        )
        rows = result.all()
        return {
            "conversations": [
                {
                    "id": str(c.id),
                    "platform_channel_id": c.platform_channel_id,
                    "title": c.title,
                    "started_at": c.started_at.isoformat() if c.started_at else None,
                    "last_active_at": (
                        c.last_active_at.isoformat() if c.last_active_at else None
                    ),
                    "last_read_at": (
                        c.last_read_at.isoformat() if c.last_read_at else None
                    ),
                    "unread_count": unread or 0,
                }
                for c, unread in rows
            ]
        }


@router.get("/api/chat/conversations/{conversation_id}/messages")
async def get_conversation_messages(
    conversation_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get messages for a specific conversation."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Message)
            .where(Message.conversation_id == uuid.UUID(conversation_id))
            .order_by(Message.created_at.asc())
            .limit(200)
        )
        msgs = result.scalars().all()

        # Build messages with tool call metadata for assistant responses
        output_messages = []
        pending_tool_calls = []

        for m in msgs:
            if m.role == "tool_call":
                # Parse and track tool call
                try:
                    tc_data = json.loads(m.content)
                    pending_tool_calls.append({
                        "name": tc_data.get("name"),
                        "tool_use_id": tc_data.get("tool_use_id"),
                        "success": None,  # Will be set by tool_result
                    })
                except (json.JSONDecodeError, KeyError):
                    pass
            elif m.role == "tool_result":
                # Match result to pending call and mark success
                try:
                    tr_data = json.loads(m.content)
                    tool_use_id = tr_data.get("tool_use_id")
                    success = tr_data.get("error") is None
                    for tc in pending_tool_calls:
                        if tc["tool_use_id"] == tool_use_id:
                            tc["success"] = success
                            break
                except (json.JSONDecodeError, KeyError):
                    pass
            elif m.role == "assistant":
                # Build metadata from pending tool calls
                tool_metadata = None
                if pending_tool_calls:
                    # Filter out calls with unknown success status
                    valid_calls = [tc for tc in pending_tool_calls if tc["success"] is not None]
                    if valid_calls:
                        unique_names = set(tc["name"] for tc in valid_calls)
                        tool_metadata = {
                            "total_count": len(valid_calls),
                            "unique_tools": len(unique_names),
                            "tools_sequence": [
                                {
                                    "name": tc["name"],
                                    "success": tc["success"],
                                    "tool_use_id": tc["tool_use_id"],
                                }
                                for tc in valid_calls
                            ],
                        }
                    pending_tool_calls = []  # Reset for next assistant message

                output_messages.append({
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "model_used": m.model_used,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                    "tool_calls_metadata": tool_metadata,
                })
            elif m.role == "user":
                output_messages.append({
                    "id": str(m.id),
                    "role": m.role,
                    "content": m.content,
                    "model_used": m.model_used,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                })

        return {"messages": output_messages}


@router.patch("/api/chat/conversations/{conversation_id}")
async def rename_conversation(
    conversation_id: str,
    body: ConversationUpdateRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Rename a conversation."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Conversation).where(
                Conversation.id == uuid.UUID(conversation_id),
                Conversation.user_id == user.user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return {"error": "Conversation not found"}
        conv.title = body.title
        await session.commit()
        return {"id": str(conv.id), "title": conv.title}


@router.delete("/api/chat/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Delete a conversation and all its messages."""
    factory = get_session_factory()
    conv_id = uuid.UUID(conversation_id)
    async with factory() as session:
        result = await session.execute(
            select(Conversation).where(
                Conversation.id == conv_id,
                Conversation.user_id == user.user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return {"error": "Conversation not found"}

        # Clear FK references from other tables before deleting
        await session.execute(
            update(MemorySummary)
            .where(MemorySummary.conversation_id == conv_id)
            .values(conversation_id=None)
        )
        await session.execute(
            update(ScheduledJob)
            .where(ScheduledJob.conversation_id == conv_id)
            .values(conversation_id=None)
        )
        await session.execute(
            delete(TokenLog).where(TokenLog.conversation_id == conv_id)
        )

        await session.delete(conv)
        await session.commit()
        return {"deleted": True}


@router.post("/api/chat/conversations/{conversation_id}/read")
async def mark_conversation_read(
    conversation_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Mark a conversation as read (set last_read_at to now)."""
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Conversation).where(
                Conversation.id == uuid.UUID(conversation_id),
                Conversation.user_id == user.user_id,
            )
        )
        conv = result.scalar_one_or_none()
        if not conv:
            return {"error": "Conversation not found"}
        conv.last_read_at = datetime.now(timezone.utc)
        await session.commit()
        return {"id": str(conv.id), "last_read_at": conv.last_read_at.isoformat()}


@router.post("/api/chat/conversations/{conversation_id}/generate-title")
async def generate_conversation_title(
    conversation_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Generate an intelligent title for a conversation."""
    await _generate_title(conversation_id)
    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(Conversation.title).where(
                Conversation.id == uuid.UUID(conversation_id),
            )
        )
        title = result.scalar_one_or_none()
        return {"title": title}


@router.post("/api/chat/send")
async def send_chat_message(
    body: ChatSendRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Send a message to the orchestrator (synchronous fallback)."""
    is_new = not body.conversation_id

    if body.conversation_id:
        resolved = await _resolve_platform_channel_id(body.conversation_id)
        channel_id = resolved or body.conversation_id
    else:
        channel_id = str(uuid.uuid4())

    response = await send_message(
        content=body.content,
        platform_user_id=str(user.user_id),
        platform_channel_id=channel_id,
        attachments=body.attachments,
    )
    real_conv_id = body.conversation_id or await _resolve_conversation_id(channel_id)

    # Auto-generate title for new conversations
    if is_new and real_conv_id:
        asyncio.create_task(_generate_title(real_conv_id))

    return {
        "conversation_id": real_conv_id or channel_id,
        "content": response.get("content", ""),
        "files": response.get("files", []),
        "error": response.get("error"),
        "tool_calls_metadata": response.get("tool_calls_metadata"),
    }


# --------------- WebSocket ---------------


@router.websocket("/ws/chat")
async def ws_chat(websocket: WebSocket) -> None:
    """Bidirectional chat via WebSocket.

    Client sends: {"type": "message", "content": "...", "conversation_id": "...", "attachments": [...]}
    Server sends: {"type": "response", "content": "...", "files": [...], "conversation_id": "..."}
    Server sends: {"type": "heartbeat"} every 10s while processing
    Server sends: {"type": "error", "message": "..."}
    """
    user = await verify_ws_auth(websocket)
    await websocket.accept()

    try:
        while True:
            data = await websocket.receive_json()

            if data.get("type") != "message":
                continue

            content = data.get("content", "").strip()
            if not content:
                continue

            client_conv_id = data.get("conversation_id")
            attachments = data.get("attachments", [])
            is_new = not client_conv_id

            channel_id: str
            if client_conv_id:
                resolved = await _resolve_platform_channel_id(client_conv_id)
                channel_id = resolved or client_conv_id
            else:
                channel_id = str(uuid.uuid4())

            # Send heartbeats while waiting for core response
            async def heartbeat_loop():
                while True:
                    await asyncio.sleep(10)
                    try:
                        await websocket.send_json({"type": "heartbeat"})
                    except Exception:
                        break

            heartbeat_task = asyncio.create_task(heartbeat_loop())
            try:
                response = await send_message(
                    content=content,
                    platform_user_id=str(user.user_id),
                    platform_channel_id=channel_id,
                    attachments=attachments,
                )
                real_conv_id = client_conv_id or await _resolve_conversation_id(
                    channel_id
                )
                await websocket.send_json(
                    {
                        "type": "response",
                        "conversation_id": real_conv_id or channel_id,
                        "content": response.get("content", ""),
                        "files": response.get("files", []),
                        "error": response.get("error"),
                        "tool_calls_metadata": response.get("tool_calls_metadata"),
                    }
                )

                # Auto-generate title for new conversations
                if is_new and real_conv_id:
                    asyncio.create_task(_generate_title(real_conv_id))

            except WebSocketDisconnect:
                raise
            except Exception as e:
                logger.error("chat_ws_error", error=str(e))
                try:
                    await websocket.send_json({"type": "error", "message": str(e)})
                except Exception:
                    break  # WebSocket already closed
            finally:
                heartbeat_task.cancel()

    except WebSocketDisconnect:
        logger.info("chat_ws_client_disconnected")
