"""Git repository browsing endpoints — proxies to git_platform module."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from portal.auth import PortalUser, require_auth
from portal.services.module_client import call_tool

logger = structlog.get_logger()
router = APIRouter(prefix="/api/repos", tags=["repos"])


async def _safe_call(module: str, tool_name: str, arguments: dict, user_id: str, timeout: float = 15.0):
    """Call a module tool and return (result, error_response)."""
    try:
        result = await call_tool(
            module=module,
            tool_name=tool_name,
            arguments=arguments,
            user_id=user_id,
            timeout=timeout,
        )
        return result.get("result", {}), None
    except Exception as e:
        msg = str(e)
        logger.warning("repos_proxy_error", tool=tool_name, error=msg)
        # Detect common credential / config issues
        if "no provider configured" in msg.lower() or "token" in msg.lower() or "credential" in msg.lower() or "auth" in msg.lower():
            detail = "Git platform credentials are not configured. Add a GitHub or Bitbucket token to use this feature."
        elif "Unknown module" in msg:
            detail = "Git platform module is not available."
        elif "connect" in msg.lower() or "timeout" in msg.lower():
            detail = "Git platform module is unreachable. Is it running?"
        else:
            detail = f"Git platform error: {msg}"
        return None, JSONResponse(status_code=502, content={"error": detail})


@router.get("")
async def list_repos(
    search: str | None = Query(None),
    per_page: int = Query(30, ge=1, le=100),
    sort: str = Query("updated"),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List repositories accessible to the authenticated git platform user."""
    args: dict = {"per_page": per_page, "sort": sort}
    if search:
        args["search"] = search
    result, err = await _safe_call("git_platform", "git_platform.list_repos", args, str(user.user_id))
    if err:
        return err
    return result


@router.get("/{owner}/{repo}")
async def get_repo(
    owner: str,
    repo: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get repository metadata."""
    result, err = await _safe_call("git_platform", "git_platform.get_repo", {"owner": owner, "repo": repo}, str(user.user_id))
    if err:
        return err
    return result


@router.get("/{owner}/{repo}/branches")
async def list_branches(
    owner: str,
    repo: str,
    per_page: int = Query(30, ge=1, le=100),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List branches in a repository."""
    result, err = await _safe_call("git_platform", "git_platform.list_branches", {"owner": owner, "repo": repo, "per_page": per_page}, str(user.user_id))
    if err:
        return err
    return result


@router.get("/{owner}/{repo}/issues")
async def list_issues(
    owner: str,
    repo: str,
    state: str = Query("open"),
    per_page: int = Query(20, ge=1, le=100),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List issues in a repository."""
    result, err = await _safe_call("git_platform", "git_platform.list_issues", {"owner": owner, "repo": repo, "state": state, "per_page": per_page}, str(user.user_id))
    if err:
        return err
    return result


@router.get("/{owner}/{repo}/pulls")
async def list_pull_requests(
    owner: str,
    repo: str,
    state: str = Query("open"),
    per_page: int = Query(20, ge=1, le=100),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List pull requests in a repository."""
    result, err = await _safe_call("git_platform", "git_platform.list_pull_requests", {"owner": owner, "repo": repo, "state": state, "per_page": per_page}, str(user.user_id))
    if err:
        return err
    return result
