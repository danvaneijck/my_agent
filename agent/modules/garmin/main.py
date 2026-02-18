"""Garmin Connect module - FastAPI service.

Supports per-user credentials: if a user has stored Garmin email/password
in portal settings, those are used instead of the global env vars.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import structlog
from fastapi import Depends, FastAPI

from modules.garmin.manifest import MANIFEST
from modules.garmin.tools import GarminTools
from shared.config import get_settings
from shared.credential_store import CredentialStore
from shared.database import get_session_factory
from shared.schemas.common import HealthResponse
from shared.auth import require_service_auth
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()
app = FastAPI(title="Garmin Connect Module", version="1.0.0")

TOOL_MAP = {
    "get_daily_summary",
    "get_heart_rate",
    "get_sleep",
    "get_body_composition",
    "get_activities",
    "get_stress",
    "get_steps",
}

# Credential store for per-user lookup
_credential_store: CredentialStore | None = None
_session_factory = None

# Fallback: global tools built from env vars
_fallback_tools: GarminTools | None = None

# Cache per-user GarminTools so Garmin token caches persist across requests
_user_tools_cache: dict[str, GarminTools] = {}


async def _get_tools_for_user(user_id: str | None) -> GarminTools | None:
    """Resolve a GarminTools instance for the given user.

    Priority:
    1. User's stored Garmin credentials from credential store
    2. Global GARMIN_EMAIL/GARMIN_PASSWORD env vars (fallback)
    """
    if user_id and _credential_store and _session_factory:
        # Return cached instance if available
        if user_id in _user_tools_cache:
            return _user_tools_cache[user_id]

        try:
            uid = uuid.UUID(user_id)
            async with _session_factory() as session:
                creds = await _credential_store.get_all(session, uid, "garmin")
            email = creds.get("email")
            password = creds.get("password")
            if email and password:
                token_path = Path(f"/app/.garmin_tokens_{user_id[:8]}")
                tools = GarminTools(email=email, password=password, tokenstore_path=token_path)
                _user_tools_cache[user_id] = tools
                return tools
        except Exception as e:
            logger.warning("user_credential_lookup_failed", user_id=user_id, error=str(e))

    return _fallback_tools


@app.on_event("startup")
async def startup():
    global _fallback_tools, _credential_store, _session_factory

    settings = get_settings()

    # Set up credential store for per-user lookup
    if settings.credential_encryption_key:
        try:
            _credential_store = CredentialStore(settings.credential_encryption_key)
            _session_factory = get_session_factory()
            logger.info("garmin_credential_store_ready")
        except Exception as e:
            logger.warning("credential_store_init_failed", error=str(e))

    # Set up fallback from env vars
    email = settings.garmin_email
    password = settings.garmin_password
    if email and password:
        _fallback_tools = GarminTools(email=email, password=password)
        logger.info("garmin_module_ready", mode="global_fallback")
    else:
        logger.info("garmin_no_global_creds", msg="No GARMIN_EMAIL/PASSWORD — will use per-user credentials only")


@app.get("/manifest", response_model=ModuleManifest)
async def manifest(_=Depends(require_service_auth)):
    """Return the module manifest."""
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall, _=Depends(require_service_auth)):
    """Execute a tool call."""
    try:
        tool_name = call.tool_name.split(".")[-1]
        args = dict(call.arguments)
        user_id = args.pop("user_id", None) or call.user_id

        if tool_name not in TOOL_MAP:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        tools = await _get_tools_for_user(user_id)
        if tools is None:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error="No Garmin credentials configured. Add Garmin email/password in Portal Settings, or set GARMIN_EMAIL and GARMIN_PASSWORD in .env.",
            )

        method = getattr(tools, tool_name)
        result = await method(**args)
        return ToolResult(tool_name=call.tool_name, success=True, result=result)

    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e), exc_info=True)
        return ToolResult(tool_name=call.tool_name, success=False, error="Internal error processing request")


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
