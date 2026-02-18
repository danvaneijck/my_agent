"""Git Platform module — FastAPI service for GitHub/Bitbucket integration.

Supports per-user credentials: if a user has stored a GitHub PAT in the
portal settings, it is used instead of the global GIT_PLATFORM_TOKEN env var.
"""

from __future__ import annotations

import uuid

import structlog
from fastapi import Depends, FastAPI

from modules.git_platform.manifest import MANIFEST
from modules.git_platform.providers.bitbucket import BitbucketProvider
from modules.git_platform.providers.github import GitHubProvider
from modules.git_platform.tools import GitPlatformTools
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
app = FastAPI(title="Git Platform Module", version="1.0.0")

settings = get_settings()

# All tool method names that the /execute endpoint can dispatch to.
TOOL_MAP = {
    "list_repos",
    "create_repo",
    "get_repo",
    "list_branches",
    "delete_branch",
    "get_file",
    "list_issues",
    "get_issue",
    "create_issue",
    "comment_on_issue",
    "list_pull_requests",
    "get_pull_request",
    "create_pull_request",
    "comment_on_pull_request",
    "merge_pull_request",
    "get_ci_status",
}

# Credential store for per-user token lookup
_credential_store: CredentialStore | None = None
_session_factory = None

# Fallback: global provider built from env vars (used when no user creds found)
_fallback_tools: GitPlatformTools | None = None


def _build_provider(token: str, provider_type: str = "github") -> GitHubProvider | BitbucketProvider | None:
    """Create a provider instance from a token."""
    if provider_type == "github":
        return GitHubProvider(token=token, base_url=settings.git_platform_base_url)
    elif provider_type == "bitbucket":
        username = settings.git_platform_username
        if not username:
            return None
        base_url = settings.git_platform_base_url
        if base_url == "https://api.github.com":
            base_url = "https://api.bitbucket.org/2.0"
        return BitbucketProvider(username=username, app_password=token, base_url=base_url)
    return None


async def _get_tools_for_user(user_id: str | None, provider: str = "github") -> GitPlatformTools | None:
    """Resolve a GitPlatformTools instance for the given user and provider.

    Priority:
    1. User's stored credentials for the specified provider
    2. Global GIT_PLATFORM_TOKEN env var (fallback)

    Args:
        user_id: User ID for credential lookup
        provider: Git platform provider ("github" or "bitbucket")
    """
    # Try per-user credentials
    if user_id and _credential_store and _session_factory:
        try:
            uid = uuid.UUID(user_id)
            async with _session_factory() as session:
                if provider == "github":
                    token = await _credential_store.get(session, uid, "github", "github_token")
                    if token:
                        git_provider = _build_provider(token, provider_type="github")
                        if git_provider:
                            return GitPlatformTools(provider=git_provider)
                elif provider == "bitbucket":
                    # Use Atlassian credentials for Bitbucket access
                    username = await _credential_store.get(session, uid, "atlassian", "username")
                    api_token = await _credential_store.get(session, uid, "atlassian", "api_token")
                    if username and api_token:
                        git_provider = BitbucketProvider(
                            username=username,
                            app_password=api_token,  # API token works as app password
                            base_url="https://api.bitbucket.org/2.0"
                        )
                        return GitPlatformTools(provider=git_provider)
        except Exception as e:
            logger.warning("user_credential_lookup_failed", user_id=user_id, provider=provider, error=str(e))

    # Fall back to global provider (only if provider matches global config)
    if _fallback_tools and provider == settings.git_platform_provider:
        return _fallback_tools

    return None


@app.on_event("startup")
async def startup():
    global _fallback_tools, _credential_store, _session_factory

    # Set up credential store for per-user token lookup
    if settings.credential_encryption_key:
        try:
            _credential_store = CredentialStore(settings.credential_encryption_key)
            _session_factory = get_session_factory()
            logger.info("git_platform_credential_store_ready")
        except Exception as e:
            logger.warning("credential_store_init_failed", error=str(e))

    # Set up fallback global provider from env var
    provider_type = settings.git_platform_provider
    token = settings.git_platform_token

    if not token:
        logger.info(
            "git_platform_no_global_token",
            msg="No GIT_PLATFORM_TOKEN — will use per-user credentials only",
        )
        return

    provider = _build_provider(token, provider_type)
    if provider:
        _fallback_tools = GitPlatformTools(provider=provider)
        logger.info("git_platform_ready", provider=provider_type, mode="global_fallback")


@app.on_event("shutdown")
async def shutdown():
    if _fallback_tools is not None:
        await _fallback_tools.provider.close()


@app.get("/manifest", response_model=ModuleManifest)
async def manifest(_=Depends(require_service_auth)):
    """Return the module manifest."""
    return MANIFEST


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall, _=Depends(require_service_auth)):
    """Execute a tool call."""
    try:
        tool_name = call.tool_name.split(".")[-1]
        args = dict(call.arguments)
        user_id = args.pop("user_id", None) or call.user_id

        # Extract provider from arguments (default to "github" for backward compatibility)
        provider = args.pop("provider", "github")

        if tool_name not in TOOL_MAP:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        tools = await _get_tools_for_user(user_id, provider)
        if tools is None:
            provider_name = "GitHub" if provider == "github" else "Bitbucket"
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"No {provider_name} credentials configured. Add credentials in Portal Settings.",
            )

        method = getattr(tools, tool_name)
        result = await method(**args)

        # Close per-user providers after use (don't close the global fallback)
        if tools is not _fallback_tools:
            await tools.provider.close()

        return ToolResult(tool_name=call.tool_name, success=True, result=result)

    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e), exc_info=True)
        return ToolResult(tool_name=call.tool_name, success=False, error="Internal error processing request")
