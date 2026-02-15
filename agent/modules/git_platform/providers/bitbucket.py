"""Bitbucket Cloud provider — implements GitProvider using the Bitbucket REST API v2.

Bitbucket terminology mapping:
  - "owner" in the provider interface maps to Bitbucket "workspace"
  - "repo" maps to "repo_slug"
  - Issues must be explicitly enabled per-repository in Bitbucket settings
  - Auth uses Basic auth (username + app password)
"""

from __future__ import annotations

import httpx
import structlog

from modules.git_platform.providers.base import GitProvider

logger = structlog.get_logger()

_DEFAULT_BASE = "https://api.bitbucket.org/2.0"

# Bitbucket uses different state names than our common interface.
_PR_STATE_MAP = {
    "open": "OPEN",
    "closed": "MERGED,DECLINED,SUPERSEDED",
    "all": "",
}

_ISSUE_STATE_MAP = {
    "open": "new,open",
    "closed": "resolved,closed,wontfix,invalid,duplicate",
    "all": "",
}

# Bitbucket merge strategies map
_MERGE_METHOD_MAP = {
    "merge": "merge_commit",
    "squash": "squash",
    "rebase": "fast_forward",
}


class BitbucketProvider(GitProvider):
    """Bitbucket Cloud REST API v2 provider."""

    def __init__(self, username: str, app_password: str, base_url: str = _DEFAULT_BASE):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            auth=(username, app_password),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> dict | list | str:
        resp = await self._client.request(method, path, **kwargs)
        if resp.status_code == 404:
            raise ValueError(f"Not found: {path}")
        if resp.status_code >= 400:
            try:
                detail = resp.json().get("error", {}).get("message", resp.text[:500])
            except Exception:
                detail = resp.text[:500]
            raise ValueError(f"Bitbucket API error {resp.status_code}: {detail}")
        if resp.status_code == 204:
            return {}
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            return resp.json()
        # Raw content (used by /src endpoint for file reads)
        return resp.text

    async def _get(self, path: str, **params) -> dict | list | str:
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, json: dict | None = None) -> dict:
        return await self._request("POST", path, json=json or {})

    async def _put(self, path: str, json: dict | None = None) -> dict:
        return await self._request("PUT", path, json=json or {})

    async def _delete(self, path: str) -> dict | list | str:
        return await self._request("DELETE", path)

    def _repo_path(self, owner: str, repo: str) -> str:
        return f"/repositories/{owner}/{repo}"

    def _web_url(self, owner: str, repo: str) -> str:
        return f"https://bitbucket.org/{owner}/{repo}"

    # ------------------------------------------------------------------
    # Repository
    # ------------------------------------------------------------------

    async def list_repos(self, per_page: int = 30, sort: str = "updated", search: str | None = None) -> dict:
        params: dict = {"pagelen": min(per_page, 100), "role": "member"}
        if search:
            params["q"] = f'name ~ "{search}"'
        # Bitbucket sorts by -updated_on by default for /repositories endpoint
        data = await self._get("/repositories", **params)
        repos = [
            {
                "owner": (r.get("owner") or {}).get("username", r.get("workspace", {}).get("slug", "")),
                "repo": r.get("slug", ""),
                "full_name": r.get("full_name"),
                "description": r.get("description"),
                "url": r.get("links", {}).get("html", {}).get("href"),
                "clone_url": next(
                    (l["href"] for l in r.get("links", {}).get("clone", []) if l.get("name") == "https"),
                    None,
                ),
                "default_branch": (r.get("mainbranch") or {}).get("name"),
                "language": r.get("language"),
                "private": r.get("is_private"),
                "stars": None,
                "updated_at": r.get("updated_on"),
            }
            for r in data.get("values", [])
        ]
        return {"count": len(repos), "repos": repos}

    async def get_repo(self, owner: str, repo: str) -> dict:
        data = await self._get(self._repo_path(owner, repo))
        mainbranch = data.get("mainbranch") or {}
        return {
            "owner": owner,
            "repo": repo,
            "full_name": data.get("full_name"),
            "description": data.get("description"),
            "url": data.get("links", {}).get("html", {}).get("href"),
            "default_branch": mainbranch.get("name"),
            "language": data.get("language"),
            "stars": None,  # Bitbucket doesn't have stars
            "forks": None,
            "open_issues": None,
            "private": data.get("is_private"),
            "created_at": data.get("created_on"),
            "updated_at": data.get("updated_on"),
        }

    async def create_repo(
        self, name: str, description: str | None = None,
        private: bool = True, auto_init: bool = True,
    ) -> dict:
        # Bitbucket uses the workspace from the authenticated user
        # The owner is derived from the username used for auth
        slug = name.lower().replace(" ", "-")
        payload: dict = {"scm": "git", "is_private": private, "name": name}
        if description:
            payload["description"] = description
        # Bitbucket doesn't have auto_init — repos are always empty unless forked
        # We use PUT to create a repo under the authenticated user's workspace
        data = await self._put(f"/repositories/{self._client.auth[0]}/{slug}", json=payload)
        workspace = (data.get("owner") or {}).get("username", data.get("workspace", {}).get("slug", ""))
        mainbranch = (data.get("mainbranch") or {}).get("name", "main")
        clone_url = next(
            (l["href"] for l in data.get("links", {}).get("clone", []) if l.get("name") == "https"),
            None,
        )
        return {
            "owner": workspace,
            "repo": data.get("slug", slug),
            "full_name": data.get("full_name"),
            "description": data.get("description"),
            "url": data.get("links", {}).get("html", {}).get("href"),
            "clone_url": clone_url,
            "default_branch": mainbranch,
            "private": data.get("is_private"),
        }

    async def list_branches(self, owner: str, repo: str, per_page: int = 30) -> dict:
        data = await self._get(
            f"{self._repo_path(owner, repo)}/refs/branches",
            pagelen=min(per_page, 100),
        )
        branches = [
            {
                "name": b["name"],
                "sha": b.get("target", {}).get("hash", "")[:12],
                "protected": False,  # Bitbucket handles branch restrictions differently
                "updated_at": b.get("target", {}).get("date"),
            }
            for b in data.get("values", [])
        ]
        branches.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return {"count": len(branches), "branches": branches}

    async def delete_branch(self, owner: str, repo: str, branch: str) -> dict:
        await self._delete(f"{self._repo_path(owner, repo)}/refs/branches/{branch}")
        return {"deleted": True, "branch": branch}

    async def get_file(self, owner: str, repo: str, path: str, ref: str | None = None) -> dict:
        # Default to the repo's main branch if no ref given
        commit_ref = ref or "HEAD"

        # First get metadata to determine if it's a file or directory
        meta = await self._get(
            f"{self._repo_path(owner, repo)}/src/{commit_ref}/{path}",
            format="meta",
        )

        if isinstance(meta, dict) and meta.get("type") == "commit_directory":
            # Directory listing
            items = [
                {
                    "name": entry.get("path", "").rsplit("/", 1)[-1],
                    "type": "dir" if entry.get("type") == "commit_directory" else "file",
                    "path": entry.get("path"),
                }
                for entry in meta.get("values", [])
            ]
            return {"type": "directory", "path": path, "items": items}

        # It's a file — fetch the raw content
        content_resp = await self._get(
            f"{self._repo_path(owner, repo)}/src/{commit_ref}/{path}"
        )
        content = content_resp if isinstance(content_resp, str) else "[binary file]"
        size = meta.get("size") if isinstance(meta, dict) else None
        commit_hash = meta.get("commit", {}).get("hash", "") if isinstance(meta, dict) else ""

        return {
            "type": "file",
            "path": path,
            "size_bytes": size,
            "sha": commit_hash[:12],
            "content": content,
            "url": f"{self._web_url(owner, repo)}/src/{commit_ref}/{path}",
        }

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------

    async def list_issues(
        self, owner: str, repo: str, state: str = "open",
        labels: str | None = None, per_page: int = 20,
    ) -> dict:
        params: dict = {"pagelen": min(per_page, 50)}

        # Build query filter
        q_parts = []
        bb_states = _ISSUE_STATE_MAP.get(state, "")
        if bb_states:
            state_filters = " OR ".join(f'state="{s.strip()}"' for s in bb_states.split(","))
            q_parts.append(f"({state_filters})")
        if labels:
            # Bitbucket issues support component filtering, not labels directly.
            # We'll filter by component name as the closest equivalent.
            for label in labels.split(","):
                label = label.strip()
                if label:
                    q_parts.append(f'component.name="{label}"')

        if q_parts:
            params["q"] = " AND ".join(q_parts)

        try:
            data = await self._get(f"{self._repo_path(owner, repo)}/issues", **params)
        except ValueError as e:
            if "404" in str(e):
                raise ValueError(
                    "Issue tracker is not enabled for this repository. "
                    "Enable it in Repository settings > Features > Issue tracker."
                ) from e
            raise

        issues = [
            {
                "number": item["id"],
                "title": item.get("title", ""),
                "state": item.get("state", ""),
                "author": (item.get("reporter") or {}).get("display_name"),
                "assignee": (item.get("assignee") or {}).get("display_name"),
                "labels": [item.get("component", {}).get("name", "")] if item.get("component") else [],
                "comments": None,
                "created_at": item.get("created_on"),
                "url": item.get("links", {}).get("html", {}).get("href"),
            }
            for item in data.get("values", [])
        ]
        return {"count": len(issues), "issues": issues}

    async def get_issue(self, owner: str, repo: str, issue_number: int) -> dict:
        base = self._repo_path(owner, repo)

        try:
            data = await self._get(f"{base}/issues/{issue_number}")
        except ValueError as e:
            if "404" in str(e):
                raise ValueError(
                    "Issue not found. The issue tracker may not be enabled for this repository."
                ) from e
            raise

        # Fetch comments
        comments_data = await self._get(
            f"{base}/issues/{issue_number}/comments",
            pagelen=20,
        )
        comments = [
            {
                "author": (c.get("user") or {}).get("display_name"),
                "body": c.get("content", {}).get("raw", ""),
                "created_at": c.get("created_on"),
            }
            for c in comments_data.get("values", [])[:20]
            if c.get("content", {}).get("raw")  # skip empty system comments
        ]

        return {
            "number": data["id"],
            "title": data.get("title", ""),
            "state": data.get("state", ""),
            "body": data.get("content", {}).get("raw", ""),
            "author": (data.get("reporter") or {}).get("display_name"),
            "assignee": (data.get("assignee") or {}).get("display_name"),
            "labels": [data.get("component", {}).get("name", "")] if data.get("component") else [],
            "comments": comments,
            "created_at": data.get("created_on"),
            "updated_at": data.get("updated_on"),
            "url": data.get("links", {}).get("html", {}).get("href"),
        }

    async def create_issue(
        self, owner: str, repo: str, title: str, body: str | None = None,
        labels: str | None = None, assignee: str | None = None,
    ) -> dict:
        payload: dict = {"title": title, "priority": "major"}
        if body:
            payload["content"] = {"raw": body, "markup": "markdown"}
        if assignee:
            payload["assignee"] = {"username": assignee}
        if labels:
            # Use the first label as component (Bitbucket's closest equivalent)
            first_label = labels.split(",")[0].strip()
            if first_label:
                payload["component"] = {"name": first_label}

        try:
            data = await self._post(f"{self._repo_path(owner, repo)}/issues", json=payload)
        except ValueError as e:
            if "404" in str(e):
                raise ValueError(
                    "Cannot create issue. The issue tracker may not be enabled for this repository."
                ) from e
            raise

        return {
            "number": data["id"],
            "title": data.get("title", title),
            "url": data.get("links", {}).get("html", {}).get("href"),
        }

    async def comment_on_issue(self, owner: str, repo: str, issue_number: int, body: str) -> dict:
        data = await self._post(
            f"{self._repo_path(owner, repo)}/issues/{issue_number}/comments",
            json={"content": {"raw": body, "markup": "markdown"}},
        )
        return {
            "comment_id": data.get("id"),
            "url": data.get("links", {}).get("html", {}).get("href"),
        }

    # ------------------------------------------------------------------
    # Pull Requests
    # ------------------------------------------------------------------

    async def list_pull_requests(
        self, owner: str, repo: str, state: str = "open", per_page: int = 20,
    ) -> dict:
        params: dict = {"pagelen": min(per_page, 50)}

        bb_states = _PR_STATE_MAP.get(state, "")
        if bb_states:
            state_filters = " OR ".join(f'state="{s.strip()}"' for s in bb_states.split(","))
            params["q"] = f"({state_filters})"

        data = await self._get(
            f"{self._repo_path(owner, repo)}/pullrequests",
            **params,
        )
        prs = [
            {
                "number": pr["id"],
                "title": pr.get("title", ""),
                "state": pr.get("state", "").lower(),
                "author": (pr.get("author") or {}).get("display_name"),
                "head": pr.get("source", {}).get("branch", {}).get("name"),
                "base": pr.get("destination", {}).get("branch", {}).get("name"),
                "draft": False,  # Bitbucket doesn't have draft PRs
                "mergeable": None,
                "created_at": pr.get("created_on"),
                "url": pr.get("links", {}).get("html", {}).get("href"),
            }
            for pr in data.get("values", [])
        ]
        return {"count": len(prs), "pull_requests": prs}

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        base = self._repo_path(owner, repo)
        data = await self._get(f"{base}/pullrequests/{pr_number}")

        # Fetch comments
        comments_data = await self._get(
            f"{base}/pullrequests/{pr_number}/comments",
            pagelen=20,
        )
        comments = [
            {
                "author": (c.get("user") or {}).get("display_name"),
                "body": c.get("content", {}).get("raw", ""),
                "path": c.get("inline", {}).get("path") if c.get("inline") else None,
                "created_at": c.get("created_on"),
            }
            for c in comments_data.get("values", [])[:20]
            if c.get("content", {}).get("raw")
        ]

        # Fetch diffstat for changed files
        diffstat_data = await self._get(f"{base}/pullrequests/{pr_number}/diffstat", pagelen=50)
        files = []
        total_add = 0
        total_del = 0
        for f in diffstat_data.get("values", [])[:50]:
            adds = f.get("lines_added", 0)
            dels = f.get("lines_removed", 0)
            total_add += adds
            total_del += dels
            old_path = f.get("old", {}).get("path") if f.get("old") else None
            new_path = f.get("new", {}).get("path") if f.get("new") else None
            status = "modified"
            if not old_path:
                status = "added"
            elif not new_path:
                status = "removed"
            elif old_path != new_path:
                status = "renamed"
            files.append({
                "filename": new_path or old_path or "",
                "status": status,
                "additions": adds,
                "deletions": dels,
            })

        return {
            "number": data["id"],
            "title": data.get("title", ""),
            "state": data.get("state", "").lower(),
            "body": data.get("description", "") or "",
            "author": (data.get("author") or {}).get("display_name"),
            "head": data.get("source", {}).get("branch", {}).get("name"),
            "base": data.get("destination", {}).get("branch", {}).get("name"),
            "draft": False,
            "mergeable": None,
            "additions": total_add,
            "deletions": total_del,
            "changed_files": len(files),
            "review_comments": comments,
            "files": files,
            "created_at": data.get("created_on"),
            "updated_at": data.get("updated_on"),
            "merged_at": None,  # Bitbucket doesn't expose this directly
            "url": data.get("links", {}).get("html", {}).get("href"),
        }

    async def create_pull_request(
        self, owner: str, repo: str, title: str, head: str, base: str,
        body: str | None = None, draft: bool = False,
    ) -> dict:
        payload: dict = {
            "title": title,
            "source": {"branch": {"name": head}},
            "destination": {"branch": {"name": base}},
            "close_source_branch": True,
        }
        if body:
            payload["description"] = body

        data = await self._post(f"{self._repo_path(owner, repo)}/pullrequests", json=payload)
        return {
            "number": data["id"],
            "title": data.get("title", title),
            "head": data.get("source", {}).get("branch", {}).get("name"),
            "base": data.get("destination", {}).get("branch", {}).get("name"),
            "draft": False,
            "url": data.get("links", {}).get("html", {}).get("href"),
        }

    async def comment_on_pull_request(self, owner: str, repo: str, pr_number: int, body: str) -> dict:
        data = await self._post(
            f"{self._repo_path(owner, repo)}/pullrequests/{pr_number}/comments",
            json={"content": {"raw": body, "markup": "markdown"}},
        )
        return {
            "comment_id": data.get("id"),
            "url": data.get("links", {}).get("html", {}).get("href"),
        }

    async def merge_pull_request(
        self, owner: str, repo: str, pr_number: int, merge_method: str = "squash",
    ) -> dict:
        bb_strategy = _MERGE_METHOD_MAP.get(merge_method, "merge_commit")
        payload: dict = {
            "merge_strategy": bb_strategy,
            "close_source_branch": True,
        }
        data = await self._post(
            f"{self._repo_path(owner, repo)}/pullrequests/{pr_number}/merge",
            json=payload,
        )
        return {
            "merged": data.get("state", "").upper() == "MERGED",
            "message": f"Pull request merged via {bb_strategy}",
            "sha": data.get("merge_commit", {}).get("hash", "")[:12],
        }

    # ------------------------------------------------------------------
    # CI / Pipelines
    # ------------------------------------------------------------------

    async def get_ci_status(self, owner: str, repo: str, ref: str) -> dict:
        base = self._repo_path(owner, repo)

        # Fetch commit statuses (third-party CI integrations)
        try:
            statuses_data = await self._get(f"{base}/commit/{ref}/statuses", pagelen=30)
        except ValueError:
            statuses_data = {"values": []}

        statuses = [
            {
                "context": s.get("name", s.get("key", "")),
                "state": s.get("state", "").lower(),
                "description": s.get("description", ""),
                "url": s.get("url"),
            }
            for s in statuses_data.get("values", [])
        ]

        # Fetch Bitbucket Pipelines runs
        check_runs = []
        try:
            pipelines_data = await self._get(
                f"{base}/pipelines/",
                pagelen=10,
                sort="-created_on",
            )
            for p in pipelines_data.get("values", [])[:10]:
                target = p.get("target") or {}
                target_ref = target.get("ref_name", "")
                target_hash = (target.get("commit", {}).get("hash") or "")[:12]
                # Only include pipelines matching the requested ref
                if ref in (target_ref, target_hash) or ref.startswith(target_hash):
                    state = p.get("state", {})
                    stage = state.get("stage", {}).get("name", state.get("name", ""))
                    result = state.get("result", {}).get("name", "")
                    check_runs.append({
                        "name": f"pipeline #{p.get('build_number', '')}",
                        "status": stage.lower() if stage else "unknown",
                        "conclusion": result.lower() if result else None,
                        "url": p.get("links", {}).get("html", {}).get("href"),
                    })
        except ValueError:
            pass  # Pipelines may not be enabled

        # Determine overall state from commit statuses
        state_set = {s["state"] for s in statuses}
        if "failed" in state_set or "FAILED" in state_set:
            overall = "failure"
        elif all(s["state"] in ("successful", "SUCCESSFUL") for s in statuses) and statuses:
            overall = "success"
        elif statuses:
            overall = "pending"
        else:
            overall = "unknown"

        return {
            "ref": ref,
            "overall_state": overall,
            "statuses": statuses,
            "check_runs": check_runs,
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._client.aclose()
