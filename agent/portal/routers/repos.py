"""Git repository browsing endpoints — proxies to git_platform module."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from portal.auth import PortalUser, require_auth
from portal.services.module_client import call_tool
from shared.database import get_session_factory
from shared.models.project import Project
from shared.models.project_task import ProjectTask

logger = structlog.get_logger()
router = APIRouter(prefix="/api/repos", tags=["repos"])


async def _safe_call(
    module: str, tool_name: str, arguments: dict, user_id: str, timeout: float = 15.0
):
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
        if (
            "no provider configured" in msg.lower()
            or "token" in msg.lower()
            or "credential" in msg.lower()
            or "auth" in msg.lower()
        ):
            detail = "Git platform credentials are not configured. Add a GitHub or Bitbucket token to use this feature."
        elif "Unknown module" in msg:
            detail = "Git platform module is not available."
        elif "connect" in msg.lower() or "timeout" in msg.lower():
            detail = "Git platform module is unreachable. Is it running?"
        else:
            detail = f"Git platform error: {msg}"
        return None, JSONResponse(status_code=502, content={"error": detail})


class CreateRepoBody(BaseModel):
    name: str
    description: str | None = None
    private: bool = True


@router.post("")
async def create_repo(
    body: CreateRepoBody,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Create a new git repository."""
    args: dict = {"name": body.name, "private": body.private}
    if body.description:
        args["description"] = body.description
    result, err = await _safe_call(
        "git_platform", "git_platform.create_repo", args, str(user.user_id), timeout=30.0
    )
    if err:
        return err
    return result


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
    result, err = await _safe_call(
        "git_platform", "git_platform.list_repos", args, str(user.user_id)
    )
    if err:
        return err
    return result


@router.get("/pulls/all")
async def list_all_pull_requests(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List open pull requests across all repos."""
    repos_result, err = await _safe_call(
        "git_platform",
        "git_platform.list_repos",
        {"per_page": 20, "sort": "updated"},
        str(user.user_id),
    )
    if err:
        return err

    repos = repos_result.get("repos", [])
    if not repos:
        return {"count": 0, "pull_requests": []}

    async def _fetch_prs(repo: dict) -> list[dict]:
        owner = repo.get("owner", "")
        name = repo.get("repo", "")
        try:
            result = await call_tool(
                module="git_platform",
                tool_name="git_platform.list_pull_requests",
                arguments={
                    "owner": owner,
                    "repo": name,
                    "state": "open",
                    "per_page": 50,
                },
                user_id=str(user.user_id),
                timeout=10.0,
            )
            prs = result.get("result", {}).get("pull_requests", [])
            for pr in prs:
                pr["owner"] = owner
                pr["repo"] = name
            return prs
        except Exception:
            return []

    all_prs_nested = await asyncio.gather(*[_fetch_prs(r) for r in repos])
    all_prs = [pr for batch in all_prs_nested for pr in batch]
    all_prs.sort(key=lambda p: p.get("created_at", ""), reverse=True)

    return {"count": len(all_prs), "pull_requests": all_prs}


@router.get("/{owner}/{repo}")
async def get_repo(
    owner: str,
    repo: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get repository metadata."""
    result, err = await _safe_call(
        "git_platform",
        "git_platform.get_repo",
        {"owner": owner, "repo": repo},
        str(user.user_id),
    )
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
    result, err = await _safe_call(
        "git_platform",
        "git_platform.list_branches",
        {"owner": owner, "repo": repo, "per_page": per_page},
        str(user.user_id),
    )
    if err:
        return err
    return result


@router.delete("/{owner}/{repo}/branches/{branch_name:path}")
async def delete_branch(
    owner: str,
    repo: str,
    branch_name: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Delete a branch from a repository."""
    result, err = await _safe_call(
        "git_platform",
        "git_platform.delete_branch",
        {"owner": owner, "repo": repo, "branch": branch_name},
        str(user.user_id),
    )
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
    result, err = await _safe_call(
        "git_platform",
        "git_platform.list_issues",
        {"owner": owner, "repo": repo, "state": state, "per_page": per_page},
        str(user.user_id),
    )
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
    result, err = await _safe_call(
        "git_platform",
        "git_platform.list_pull_requests",
        {"owner": owner, "repo": repo, "state": state, "per_page": per_page},
        str(user.user_id),
    )
    if err:
        return err
    return result


class CreatePRBody(BaseModel):
    title: str
    head: str
    base: str
    body: str | None = None
    draft: bool = False


@router.post("/{owner}/{repo}/pulls")
async def create_pull_request(
    owner: str,
    repo: str,
    pr_body: CreatePRBody,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Create a pull request."""
    result, err = await _safe_call(
        "git_platform",
        "git_platform.create_pull_request",
        {
            "owner": owner,
            "repo": repo,
            "title": pr_body.title,
            "head": pr_body.head,
            "base": pr_body.base,
            "body": pr_body.body,
            "draft": pr_body.draft,
        },
        str(user.user_id),
    )
    if err:
        return err
    return result


@router.get("/{owner}/{repo}/pulls/{pr_number}")
async def get_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get full pull request details."""
    result, err = await _safe_call(
        "git_platform",
        "git_platform.get_pull_request",
        {"owner": owner, "repo": repo, "pr_number": pr_number},
        str(user.user_id),
        timeout=20.0,
    )
    if err:
        return err
    return result


class MergeBody(BaseModel):
    merge_method: str = "squash"


@router.post("/{owner}/{repo}/pulls/{pr_number}/merge")
async def merge_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    body: MergeBody = MergeBody(),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Merge a pull request and update any linked project tasks."""
    result, err = await _safe_call(
        "git_platform",
        "git_platform.merge_pull_request",
        {
            "owner": owner,
            "repo": repo,
            "pr_number": pr_number,
            "merge_method": body.merge_method,
        },
        str(user.user_id),
        timeout=20.0,
    )
    if err:
        return err

    # After successful merge, transition linked project tasks in_review → done
    if result.get("success") or result.get("result", {}).get("merged"):
        asyncio.create_task(
            _on_pr_merged(pr_number=pr_number, user_id=user.user_id)
        )

    return result


async def _on_pr_merged(pr_number: int, user_id) -> None:
    """Move project tasks linked to this PR from in_review → done.

    If all tasks in the project are now done, mark the project as completed.
    """
    try:
        factory = get_session_factory()
        async with factory() as session:
            # Find tasks linked to this PR that are in_review
            tasks_result = await session.execute(
                select(ProjectTask).where(
                    ProjectTask.pr_number == pr_number,
                    ProjectTask.user_id == user_id,
                    ProjectTask.status == "in_review",
                )
            )
            tasks = list(tasks_result.scalars().all())

            if not tasks:
                return

            now = datetime.now(timezone.utc)
            project_ids = set()
            for task in tasks:
                task.status = "done"
                task.completed_at = now
                task.updated_at = now
                project_ids.add(task.project_id)

            await session.commit()
            logger.info(
                "tasks_marked_done_on_merge",
                pr_number=pr_number,
                task_count=len(tasks),
            )

            # Check if any linked projects are now fully done
            for pid in project_ids:
                remaining = await session.execute(
                    select(func.count(ProjectTask.id)).where(
                        ProjectTask.project_id == pid,
                        ProjectTask.status.notin_(["done", "failed"]),
                    )
                )
                if remaining.scalar() == 0:
                    project = await session.get(Project, pid)
                    if project and project.status != "completed":
                        project.status = "completed"
                        project.updated_at = now
                        await session.commit()
                        logger.info(
                            "project_completed",
                            project_id=str(pid),
                            project_name=project.name,
                        )
    except Exception as e:
        logger.error("on_pr_merged_failed", pr_number=pr_number, error=str(e))


class CommentBody(BaseModel):
    body: str


@router.post("/{owner}/{repo}/pulls/{pr_number}/comment")
async def comment_on_pull_request(
    owner: str,
    repo: str,
    pr_number: int,
    body: CommentBody,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Add a comment to a pull request."""
    result, err = await _safe_call(
        "git_platform",
        "git_platform.comment_on_pull_request",
        {"owner": owner, "repo": repo, "pr_number": pr_number, "body": body.body},
        str(user.user_id),
    )
    if err:
        return err
    return result
