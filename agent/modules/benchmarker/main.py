"""Benchmarker module - FastAPI service.

Supports per-user credentials: if a user has stored Benchmarker API URL/Key
in portal settings, those are used instead of the global env vars.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import Depends, FastAPI

from modules.benchmarker.manifest import MANIFEST
from modules.benchmarker.tools import BenchmarkerClient
from shared.auth import require_service_auth
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
app = FastAPI(title="Benchmarker Module", version="1.0.0")

# Credential store for per-user lookup
_credential_store: CredentialStore | None = None
_session_factory = None

# Fallback: global client built from env vars
_fallback_client: BenchmarkerClient | None = None


async def _get_client_for_user(user_id: str | None) -> BenchmarkerClient | None:
    """Resolve a BenchmarkerClient instance for the given user.

    Always fetches credentials from the DB so that updates made via the portal
    are picked up immediately without restarting the module.

    Priority:
    1. User's stored Benchmarker credentials from credential store
    2. Global BENCHMARKER_API_URL/BENCHMARKER_API_KEY env vars (fallback)
    """
    if user_id and _credential_store and _session_factory:
        try:
            uid = uuid.UUID(user_id)
            async with _session_factory() as session:
                creds = await _credential_store.get_all(session, uid, "benchmarker")
            api_url = creds.get("api_url")
            api_key = creds.get("api_key")
            if api_url and api_key:
                return BenchmarkerClient(api_url=api_url, api_key=api_key)
        except Exception as e:
            logger.warning("user_credential_lookup_failed", user_id=user_id, error=str(e))

    return _fallback_client


@app.on_event("startup")
async def startup():
    global _fallback_client, _credential_store, _session_factory

    settings = get_settings()

    # Set up credential store for per-user lookup
    if settings.credential_encryption_key:
        try:
            _credential_store = CredentialStore(settings.credential_encryption_key)
            _session_factory = get_session_factory()
            logger.info("benchmarker_credential_store_ready")
        except Exception as e:
            logger.warning("credential_store_init_failed", error=str(e))

    # Set up fallback from env vars
    api_url = settings.benchmarker_api_url
    api_key = settings.benchmarker_api_key
    if api_url and api_key:
        _fallback_client = BenchmarkerClient(api_url=api_url, api_key=api_key)
        logger.info("benchmarker_module_ready", mode="global_fallback")
    else:
        logger.info(
            "benchmarker_no_global_creds",
            msg="No BENCHMARKER_API_URL/API_KEY — will use per-user credentials only"
        )


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

        # Resolve client for user
        client = await _get_client_for_user(user_id)
        if client is None:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error="No Benchmarker credentials configured. Add API URL and API Key in Portal Settings, or set BENCHMARKER_API_URL and BENCHMARKER_API_KEY in .env.",
            )

        # Route to appropriate tool method
        if tool_name == "device_lookup":
            result = await client.device_lookup(**args)
        elif tool_name == "send_downlink":
            result = await client.send_downlink(**args)
        elif tool_name == "organisation_summary":
            result = await client.organisation_summary(**args)
        elif tool_name == "site_overview":
            result = await client.site_overview(**args)
        elif tool_name == "silent_devices":
            result = await client.silent_devices(**args)
        elif tool_name == "low_battery_devices":
            result = await client.low_battery_devices(**args)
        elif tool_name == "device_issues":
            result = await client.device_issues(**args)
        elif tool_name == "org_issues_summary":
            result = await client.org_issues_summary(**args)
        elif tool_name == "provision_organisation":
            result = await client.provision_organisation(**args)
        else:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        return ToolResult(tool_name=call.tool_name, success=True, result=result)

    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e), exc_info=True)
        return ToolResult(tool_name=call.tool_name, success=False, error="Internal error processing request")


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
