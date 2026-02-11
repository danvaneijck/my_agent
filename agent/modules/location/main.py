"""Location Module — FastAPI service with OwnTracks endpoint."""

from __future__ import annotations

import asyncio
import base64

import structlog
from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from modules.location.manifest import MANIFEST
from modules.location.owntracks import authenticate_owntracks, handle_owntracks_publish
from modules.location.tools import LocationTools
from modules.location.worker import geofence_loop
from shared.config import get_settings
from shared.database import get_session_factory
from shared.redis import get_redis
from shared.schemas.common import HealthResponse
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()
app = FastAPI(title="Location Module", version="1.0.0")

settings = get_settings()
tools: LocationTools | None = None
session_factory = None
redis_client = None


@app.on_event("startup")
async def startup():
    global tools, session_factory, redis_client
    session_factory = get_session_factory()
    redis_client = await get_redis()

    owntracks_url = getattr(settings, "owntracks_endpoint_url", "https://your-agent.com/pub")

    tools = LocationTools(session_factory, redis_client, owntracks_url)
    logger.info("location_module_ready")

    # Start background geofence worker
    asyncio.create_task(geofence_loop(session_factory, redis_client))


# --- OwnTracks endpoint (called by the phone app, not the LLM) ---


@app.post("/pub")
async def owntracks_publish(
    request: Request,
    authorization: str | None = Header(default=None),
    x_limit_u: str | None = Header(default=None),
):
    """Receive OwnTracks location/transition payloads.

    Authenticates via HTTP Basic auth, processes the payload,
    and returns OwnTracks commands (e.g. setWaypoints) in the response.
    """
    # Parse Basic auth
    username = None
    password = None

    if authorization and authorization.startswith("Basic "):
        try:
            decoded = base64.b64decode(authorization[6:]).decode("utf-8")
            username, password = decoded.split(":", 1)
        except Exception:
            return JSONResponse(status_code=401, content={"error": "Invalid authorization"})
    elif x_limit_u:
        # Fallback: X-Limit-U header (some OwnTracks configs)
        username = x_limit_u
        # Cannot verify without password — reject
        return JSONResponse(status_code=401, content={"error": "Password required"})

    if not username or not password:
        return JSONResponse(status_code=401, content={"error": "Authorization required"})

    # Authenticate
    async with session_factory() as session:
        user_id = await authenticate_owntracks(session, username, password)

    if user_id is None:
        return JSONResponse(status_code=403, content={"error": "Invalid credentials"})

    # Parse payload
    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"error": "Invalid JSON"})

    # Process
    async with session_factory() as session:
        response_cmds = await handle_owntracks_publish(
            session, redis_client, user_id, payload
        )

    # OwnTracks expects a JSON array response
    return JSONResponse(content=response_cmds)


# --- Standard module endpoints ---


@app.get("/manifest", response_model=ModuleManifest)
async def manifest():
    """Return the module manifest."""
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall):
    """Execute a tool call."""
    if tools is None:
        return ToolResult(tool_name=call.tool_name, success=False, error="Module not ready")

    try:
        tool_name = call.tool_name.split(".")[-1]
        args = dict(call.arguments)
        if call.user_id:
            args["user_id"] = call.user_id

        # The orchestrator injects platform context for all location.* tools,
        # but only create_reminder uses it. Strip for other tools.
        if tool_name != "create_reminder":
            for k in ("platform", "platform_channel_id", "platform_thread_id"):
                args.pop(k, None)

        if tool_name == "create_reminder":
            result = await tools.create_reminder(**args)
        elif tool_name == "list_reminders":
            result = await tools.list_reminders(**args)
        elif tool_name == "cancel_reminder":
            result = await tools.cancel_reminder(**args)
        elif tool_name == "delete_reminder":
            result = await tools.delete_reminder(**args)
        elif tool_name == "disable_reminder":
            result = await tools.disable_reminder(**args)
        elif tool_name == "enable_reminder":
            result = await tools.enable_reminder(**args)
        elif tool_name == "get_location":
            result = await tools.get_location(**args)
        elif tool_name == "set_named_place":
            result = await tools.set_named_place(**args)
        elif tool_name == "generate_pairing_credentials":
            result = await tools.generate_pairing_credentials(**args)
        else:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        return ToolResult(tool_name=call.tool_name, success=True, result=result)
    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e))
        return ToolResult(tool_name=call.tool_name, success=False, error=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
