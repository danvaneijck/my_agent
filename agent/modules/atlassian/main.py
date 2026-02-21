"""Atlassian module — FastAPI service for Jira and Confluence integration.

Supports per-user credentials: if a user has stored Atlassian url/username/api_token
in portal settings, those are used instead of the global env vars.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import Depends, FastAPI

from modules.atlassian.manifest import MANIFEST
from modules.atlassian.tools import AtlassianTools
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
app = FastAPI(title="Atlassian Module", version="1.0.0")

settings = get_settings()

TOOL_MAP = {
    "jira_search",
    "jira_get_issue",
    "jira_create_issue",
    "jira_update_issue",
    "confluence_search",
    "confluence_get_page",
    "confluence_create_page",
    "confluence_update_page",
    "create_meeting_notes",
    "create_feature_doc",
}

# Credential store for per-user lookup
_credential_store: CredentialStore | None = None
_session_factory = None

# Fallback: global tools built from env vars
_fallback_tools: AtlassianTools | None = None


async def _get_tools_for_user(user_id: str | None) -> AtlassianTools | None:
    """Resolve an AtlassianTools instance for the given user.

    Priority:
    1. User's stored Atlassian credentials from credential store
    2. Global ATLASSIAN_* env vars (fallback)
    """
    if user_id and _credential_store and _session_factory:
        try:
            uid = uuid.UUID(user_id)
            async with _session_factory() as session:
                creds = await _credential_store.get_all(session, uid, "atlassian")
            url = creds.get("url")
            username = creds.get("username")
            api_token = creds.get("api_token")
            if url and username and api_token:
                return AtlassianTools(
                    url=url,
                    username=username,
                    api_token=api_token,
                    cloud=settings.atlassian_cloud,
                    default_space=settings.confluence_default_space,
                )
        except Exception as e:
            logger.warning("user_credential_lookup_failed", user_id=user_id, error=str(e))

    return _fallback_tools


@app.on_event("startup")
async def startup():
    global _fallback_tools, _credential_store, _session_factory

    # Set up credential store for per-user lookup
    if settings.credential_encryption_key:
        try:
            _credential_store = CredentialStore(settings.credential_encryption_key)
            _session_factory = get_session_factory()
            logger.info("atlassian_credential_store_ready")
        except Exception as e:
            logger.warning("credential_store_init_failed", error=str(e))

    # Set up fallback from env vars
    if settings.atlassian_url and settings.atlassian_api_token:
        _fallback_tools = AtlassianTools(
            url=settings.atlassian_url,
            username=settings.atlassian_username,
            api_token=settings.atlassian_api_token,
            cloud=settings.atlassian_cloud,
            default_space=settings.confluence_default_space,
        )
        logger.info("atlassian_ready", url=settings.atlassian_url, mode="global_fallback")
    else:
        logger.info("atlassian_no_global_creds", msg="No ATLASSIAN_URL/API_TOKEN — will use per-user credentials only")


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
                error="No Atlassian credentials configured. Add Atlassian URL/username/API token in Portal Settings, or set ATLASSIAN_URL and ATLASSIAN_API_TOKEN in .env.",
            )

        method = getattr(tools, tool_name)
        result = await method(**args)
        return ToolResult(tool_name=call.tool_name, success=True, result=result)

    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e), exc_info=True)
        return ToolResult(tool_name=call.tool_name, success=False, error=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
