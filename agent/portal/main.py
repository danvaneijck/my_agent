"""Web portal — FastAPI app serving the React frontend and API."""

from __future__ import annotations

import asyncio
from pathlib import Path

import redis.asyncio as aioredis
import structlog
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from portal.auth import verify_ws_auth
from portal.routers import auth, chat, deployments, files, projects, repos, schedule, settings, skills, system, tasks, usage
from portal.services.terminal_service import get_terminal_service
from shared.config import get_settings
from shared.database import get_session_factory
from shared.models.conversation import Conversation
from shared.schemas.notifications import Notification
from sqlalchemy import select

logger = structlog.get_logger()

app = FastAPI(title="Agent Portal", version="1.0.0")

# --------------- Routers ---------------

app.include_router(auth.router)
app.include_router(system.router)
app.include_router(tasks.router)
app.include_router(repos.router)
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(schedule.router)
app.include_router(deployments.router)
app.include_router(settings.router)
app.include_router(usage.router)
app.include_router(projects.router)
app.include_router(skills.router)

# --------------- Notification WebSocket ---------------

# Connected portal WebSocket clients keyed by user_id
_notification_clients: dict[str, list[WebSocket]] = {}
_notification_task: asyncio.Task | None = None


async def _notification_listener() -> None:
    """Subscribe to Redis notifications:web and forward to connected WS clients."""
    settings = get_settings()
    r = aioredis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe("notifications:web")
    logger.info("portal_notification_listener_started")

    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                notification = Notification.model_validate_json(message["data"])
                # Resolve platform_channel_id to conversation_id
                conversation_id = None
                try:
                    factory = get_session_factory()
                    async with factory() as session:
                        result = await session.execute(
                            select(Conversation.id)
                            .where(
                                Conversation.platform == "web",
                                Conversation.platform_channel_id
                                == notification.platform_channel_id,
                            )
                            .order_by(Conversation.last_active_at.desc())
                            .limit(1)
                        )
                        row = result.scalar_one_or_none()
                        if row:
                            conversation_id = str(row)
                except Exception:
                    pass
                payload = {
                    "type": "notification",
                    "content": notification.content,
                    "job_id": notification.job_id,
                    "platform_channel_id": notification.platform_channel_id,
                    "conversation_id": conversation_id,
                }
                # Send to all connected clients for this user
                user_id = notification.user_id or ""
                clients = _notification_clients.get(user_id, [])
                # Also broadcast to all clients (in case user_id matching is loose)
                all_clients = [ws for wss in _notification_clients.values() for ws in wss]
                sent_to: set[int] = set()
                for ws in clients + all_clients:
                    if id(ws) in sent_to:
                        continue
                    sent_to.add(id(ws))
                    try:
                        await ws.send_json(payload)
                    except Exception:
                        pass
                logger.info(
                    "portal_notification_forwarded",
                    user_id=user_id,
                    job_id=notification.job_id,
                    clients=len(sent_to),
                )
            except Exception as e:
                logger.error("portal_notification_error", error=str(e))
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe("notifications:web")
        await r.aclose()


@app.on_event("startup")
async def startup() -> None:
    global _notification_task
    _notification_task = asyncio.create_task(_notification_listener())

    # Start terminal session cleanup loop
    terminal_service = get_terminal_service()
    await terminal_service.start_cleanup_loop()
    logger.info("portal_startup_complete")


@app.on_event("shutdown")
async def shutdown() -> None:
    if _notification_task:
        _notification_task.cancel()
        try:
            await _notification_task
        except asyncio.CancelledError:
            pass


@app.websocket("/ws/notifications")
async def ws_notifications(websocket: WebSocket) -> None:
    """WebSocket for receiving proactive notifications (scheduler, workflows)."""
    user = await verify_ws_auth(websocket)
    await websocket.accept()

    user_key = str(user.user_id)
    _notification_clients.setdefault(user_key, []).append(websocket)
    logger.info("notification_ws_connected", user_id=user_key)

    try:
        while True:
            # Keep connection alive; client may send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        clients = _notification_clients.get(user_key, [])
        if websocket in clients:
            clients.remove(websocket)
        if not clients:
            _notification_clients.pop(user_key, None)
        logger.info("notification_ws_disconnected", user_id=user_key)

# --------------- Static files (React SPA) ---------------

STATIC_DIR = Path(__file__).parent / "static" / "dist"

if STATIC_DIR.exists():
    # Serve Vite's hashed asset files (JS, CSS, images)
    app.mount(
        "/assets",
        StaticFiles(directory=STATIC_DIR / "assets"),
        name="assets",
    )

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str) -> FileResponse:
        """Serve the React SPA. Non-API/WS routes return index.html."""
        # Don't serve SPA for API or WebSocket paths
        if full_path.startswith(("api/", "ws/")):
            return FileResponse(STATIC_DIR / "index.html", status_code=404)
        file_path = STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(STATIC_DIR / "index.html")
