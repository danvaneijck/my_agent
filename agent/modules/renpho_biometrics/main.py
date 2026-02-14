"""Renpho biometrics module - FastAPI service.

Supports per-user credentials: if a user has stored Renpho email/password
in portal settings, those are used instead of the global env vars.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import FastAPI

from modules.renpho_biometrics.manifest import MANIFEST
from modules.renpho_biometrics.tools import RenphoBiometricsTools
from shared.config import get_settings
from shared.credential_store import CredentialStore
from shared.database import get_session_factory
from shared.schemas.common import HealthResponse
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()
app = FastAPI(title="Renpho Biometrics Module", version="1.0.0")

TOOL_MAP = {
    "get_measurements",
    "get_latest",
    "get_trend",
}

# Credential store for per-user lookup
_credential_store: CredentialStore | None = None
_session_factory = None

# Fallback: global tools built from env vars
_fallback_tools: RenphoBiometricsTools | None = None


async def _get_tools_for_user(user_id: str | None) -> RenphoBiometricsTools | None:
    """Resolve a RenphoBiometricsTools instance for the given user.

    Priority:
    1. User's stored Renpho credentials from credential store
    2. Global RENPHO_EMAIL/RENPHO_PASSWORD env vars (fallback)
    """
    if user_id and _credential_store and _session_factory:
        try:
            uid = uuid.UUID(user_id)
            async with _session_factory() as session:
                creds = await _credential_store.get_all(session, uid, "renpho")
            email = creds.get("email")
            password = creds.get("password")
            if email and password:
                return RenphoBiometricsTools(email=email, password=password)
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
            logger.info("renpho_credential_store_ready")
        except Exception as e:
            logger.warning("credential_store_init_failed", error=str(e))

    # Set up fallback from env vars
    email = settings.renpho_email
    password = settings.renpho_password
    if email and password:
        _fallback_tools = RenphoBiometricsTools(email=email, password=password)
        logger.info("renpho_biometrics_module_ready", mode="global_fallback")
    else:
        logger.info("renpho_no_global_creds", msg="No RENPHO_EMAIL/PASSWORD — will use per-user credentials only")


@app.get("/manifest", response_model=ModuleManifest)
async def manifest():
    """Return the module manifest."""
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall):
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
                error="No Renpho credentials configured. Add Renpho email/password in Portal Settings, or set RENPHO_EMAIL and RENPHO_PASSWORD in .env.",
            )

        method = getattr(tools, tool_name)
        result = await method(**args)
        return ToolResult(tool_name=call.tool_name, success=True, result=result)

    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e))
        return ToolResult(tool_name=call.tool_name, success=False, error=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
