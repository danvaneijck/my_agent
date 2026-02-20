"""GitHub provider — implements GitProvider using the GitHub REST API."""

from __future__ import annotations

import asyncio
import base64

import httpx
import structlog

from modules.git_platform.providers.base import GitProvider

logger = structlog.get_logger()

# GitHub API base
_DEFAULT_BASE = "https://api.github.com"


class GitHubProvider(GitProvider):
    """GitHub REST API v3 provider."""

    def __init__(self, token: str, base_url: str = _DEFAULT_BASE):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _request(self, method: str, path: str, **kwargs) -> dict | list:
        """Make an API request and return parsed JSON."""
        resp = await self._client.request(method, path, **kwargs)
        if resp.status_code == 404:
            raise ValueError(f"Not found: {path}")
        if resp.status_code == 422:
            detail = resp.json().get("message", resp.text)
            errors = resp.json().get("errors", [])
            msg = detail
            if errors:
                msg += " — " + "; ".join(e.get("message", str(e)) for e in errors)
            raise ValueError(msg)
        if resp.status_code >= 400:
            raise ValueError(f"GitHub API error {resp.status_code}: {resp.text[:500]}")
        if resp.status_code == 204:
            return {}
        return resp.json()

    async def _get(self, path: str, **params) -> dict | list:
        return await self._request("GET", path, params=params)

    async def _post(self, path: str, json: dict) -> dict:
        return await self._request("POST", path, json=json)

    async def _patch(self, path: str, json: dict) -> dict:
        return await self._request("PATCH", path, json=json)

    async def _put(self, path: str, json: dict | None = None) -> dict:
        return await self._request("PUT", path, json=json or {})

    async def _delete(self, path: str) -> dict:
        return await self._request("DELETE", path)

    def _repo_url(self, owner: str, repo: str) -> str:
        return f"https://github.com/{owner}/{repo}"

    # ------------------------------------------------------------------
    # Repository
    # ------------------------------------------------------------------

    async def list_repos(self, per_page: int = 30, sort: str = "updated", search: str | None = None) -> dict:
        params = {"per_page": min(per_page, 100), "sort": sort, "direction": "desc"}
        if search:
            # Use the search API for filtering by name
            data = await self._get(
                "/search/repositories",
                q=f"{search} in:name user:@me",
                per_page=min(per_page, 100),
                sort=sort,
            )
            items = data.get("items", [])
        else:
            items = await self._get("/user/repos", **params)

        repos = [
            {
                "owner": (r.get("owner") or {}).get("login", ""),
                "repo": r.get("name", ""),
                "full_name": r.get("full_name"),
                "description": r.get("description"),
                "url": r.get("html_url"),
                "clone_url": r.get("clone_url"),
                "default_branch": r.get("default_branch"),
                "language": r.get("language"),
                "private": r.get("private"),
                "stars": r.get("stargazers_count", 0),
                "updated_at": r.get("updated_at"),
            }
            for r in items
        ]
        return {"count": len(repos), "repos": repos}

    async def get_repo(self, owner: str, repo: str) -> dict:
        data = await self._get(f"/repos/{owner}/{repo}")
        return {
            "owner": owner,
            "repo": repo,
            "full_name": data.get("full_name"),
            "description": data.get("description"),
            "url": data.get("html_url"),
            "default_branch": data.get("default_branch"),
            "language": data.get("language"),
            "stars": data.get("stargazers_count"),
            "forks": data.get("forks_count"),
            "open_issues": data.get("open_issues_count"),
            "private": data.get("private"),
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
        }

    async def create_repo(
        self, name: str, description: str | None = None,
        private: bool = True, auto_init: bool = True,
    ) -> dict:
        payload: dict = {"name": name, "private": private, "auto_init": auto_init}
        if description:
            payload["description"] = description
        data = await self._post("/user/repos", json=payload)
        return {
            "owner": (data.get("owner") or {}).get("login", ""),
            "repo": data.get("name", ""),
            "full_name": data.get("full_name"),
            "description": data.get("description"),
            "url": data.get("html_url"),
            "clone_url": data.get("clone_url"),
            "default_branch": data.get("default_branch"),
            "private": data.get("private"),
        }

    async def list_branches(self, owner: str, repo: str, per_page: int = 30) -> dict:
        data = await self._get(f"/repos/{owner}/{repo}/branches", per_page=per_page)

        # Limit concurrent enrichment requests to avoid GitHub secondary rate limits
        sem = asyncio.Semaphore(5)

        async def _enrich(b: dict) -> dict:
            sha = b["commit"]["sha"]
            date = None
            try:
                async with sem:
                    commit = await self._get(f"/repos/{owner}/{repo}/git/commits/{sha}")
                date = commit.get("committer", {}).get("date")
            except Exception:
                pass
            return {
                "name": b["name"],
                "sha": sha[:12],
                "protected": b.get("protected", False),
                "updated_at": date,
            }

        branches = list(await asyncio.gather(*[_enrich(b) for b in data]))
        branches.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return {"count": len(branches), "branches": branches}

    async def delete_branch(self, owner: str, repo: str, branch: str) -> dict:
        await self._delete(f"/repos/{owner}/{repo}/git/refs/heads/{branch}")
        return {"deleted": True, "branch": branch}

    async def get_file(self, owner: str, repo: str, path: str, ref: str | None = None) -> dict:
        params = {}
        if ref:
            params["ref"] = ref
        data = await self._get(f"/repos/{owner}/{repo}/contents/{path}", **params)
        if isinstance(data, list):
            # It's a directory listing
            items = [
                {"name": item["name"], "type": item["type"], "path": item["path"]}
                for item in data
            ]
            return {"type": "directory", "path": path, "items": items}

        content = ""
        if data.get("encoding") == "base64" and data.get("content"):
            try:
                content = base64.b64decode(data["content"]).decode("utf-8")
            except (UnicodeDecodeError, ValueError):
                content = "[binary file]"
        return {
            "type": "file",
            "path": data.get("path", path),
            "size_bytes": data.get("size"),
            "sha": data.get("sha", "")[:12],
            "content": content,
            "url": data.get("html_url"),
        }

    # ------------------------------------------------------------------
    # Issues
    # ------------------------------------------------------------------

    async def list_issues(
        self, owner: str, repo: str, state: str = "open", labels: str | None = None, per_page: int = 20,
    ) -> dict:
        params: dict = {"state": state, "per_page": per_page}
        if labels:
            params["labels"] = labels
        data = await self._get(f"/repos/{owner}/{repo}/issues", **params)
        issues = []
        for item in data:
            # Skip pull requests (GitHub includes them in /issues)
            if item.get("pull_request"):
                continue
            issues.append({
                "number": item["number"],
                "title": item["title"],
                "state": item["state"],
                "author": (item.get("user") or {}).get("login"),
                "assignee": (item.get("assignee") or {}).get("login"),
                "labels": [l["name"] for l in item.get("labels", [])],
                "comments": item.get("comments", 0),
                "created_at": item.get("created_at"),
                "url": item.get("html_url"),
            })
        return {"count": len(issues), "issues": issues}

    async def get_issue(self, owner: str, repo: str, issue_number: int) -> dict:
        data = await self._get(f"/repos/{owner}/{repo}/issues/{issue_number}")
        # Fetch comments
        comments_data = await self._get(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments", per_page=20
        )
        comments = [
            {
                "author": (c.get("user") or {}).get("login"),
                "body": c.get("body", ""),
                "created_at": c.get("created_at"),
            }
            for c in comments_data[:20]
        ]
        return {
            "number": data["number"],
            "title": data["title"],
            "state": data["state"],
            "body": data.get("body") or "",
            "author": (data.get("user") or {}).get("login"),
            "assignee": (data.get("assignee") or {}).get("login"),
            "labels": [l["name"] for l in data.get("labels", [])],
            "comments": comments,
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "url": data.get("html_url"),
        }

    async def create_issue(
        self, owner: str, repo: str, title: str, body: str | None = None,
        labels: str | None = None, assignee: str | None = None,
    ) -> dict:
        payload: dict = {"title": title}
        if body:
            payload["body"] = body
        if labels:
            payload["labels"] = [l.strip() for l in labels.split(",") if l.strip()]
        if assignee:
            payload["assignees"] = [assignee]
        data = await self._post(f"/repos/{owner}/{repo}/issues", json=payload)
        return {
            "number": data["number"],
            "title": data["title"],
            "url": data.get("html_url"),
        }

    async def comment_on_issue(self, owner: str, repo: str, issue_number: int, body: str) -> dict:
        data = await self._post(
            f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body},
        )
        return {
            "comment_id": data["id"],
            "url": data.get("html_url"),
        }

    # ------------------------------------------------------------------
    # Pull Requests
    # ------------------------------------------------------------------

    async def list_pull_requests(
        self, owner: str, repo: str, state: str = "open", per_page: int = 20,
    ) -> dict:
        data = await self._get(f"/repos/{owner}/{repo}/pulls", state=state, per_page=per_page)
        prs = [
            {
                "number": pr["number"],
                "title": pr["title"],
                "state": pr["state"],
                "author": (pr.get("user") or {}).get("login"),
                "head": pr.get("head", {}).get("ref"),
                "base": pr.get("base", {}).get("ref"),
                "draft": pr.get("draft", False),
                "mergeable": pr.get("mergeable"),
                "created_at": pr.get("created_at"),
                "url": pr.get("html_url"),
            }
            for pr in data
        ]
        return {"count": len(prs), "pull_requests": prs}

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        data = await self._get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        # Fetch review comments
        comments_data = await self._get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/comments", per_page=20
        )
        comments = [
            {
                "author": (c.get("user") or {}).get("login"),
                "body": c.get("body", ""),
                "path": c.get("path"),
                "created_at": c.get("created_at"),
            }
            for c in comments_data[:20]
        ]
        # Fetch changed files summary
        files_data = await self._get(f"/repos/{owner}/{repo}/pulls/{pr_number}/files", per_page=50)
        files = [
            {
                "filename": f["filename"],
                "status": f["status"],
                "additions": f.get("additions", 0),
                "deletions": f.get("deletions", 0),
            }
            for f in files_data[:50]
        ]
        return {
            "number": data["number"],
            "title": data["title"],
            "state": data["state"],
            "body": data.get("body") or "",
            "author": (data.get("user") or {}).get("login"),
            "head": data.get("head", {}).get("ref"),
            "base": data.get("base", {}).get("ref"),
            "draft": data.get("draft", False),
            "mergeable": data.get("mergeable"),
            "additions": data.get("additions"),
            "deletions": data.get("deletions"),
            "changed_files": data.get("changed_files"),
            "review_comments": comments,
            "files": files,
            "created_at": data.get("created_at"),
            "updated_at": data.get("updated_at"),
            "merged_at": data.get("merged_at"),
            "url": data.get("html_url"),
        }

    async def create_pull_request(
        self, owner: str, repo: str, title: str, head: str, base: str,
        body: str | None = None, draft: bool = False,
    ) -> dict:
        payload: dict = {"title": title, "head": head, "base": base, "draft": draft}
        if body:
            payload["body"] = body
        data = await self._post(f"/repos/{owner}/{repo}/pulls", json=payload)
        return {
            "number": data["number"],
            "title": data["title"],
            "head": data.get("head", {}).get("ref"),
            "base": data.get("base", {}).get("ref"),
            "draft": data.get("draft", False),
            "url": data.get("html_url"),
        }

    async def comment_on_pull_request(self, owner: str, repo: str, pr_number: int, body: str) -> dict:
        # PR comments go through the issues API
        data = await self._post(
            f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
            json={"body": body},
        )
        return {
            "comment_id": data["id"],
            "url": data.get("html_url"),
        }

    async def merge_pull_request(
        self, owner: str, repo: str, pr_number: int, merge_method: str = "squash",
    ) -> dict:
        payload: dict = {"merge_method": merge_method}
        data = await self._put(f"/repos/{owner}/{repo}/pulls/{pr_number}/merge", json=payload)
        return {
            "merged": data.get("merged", True),
            "message": data.get("message", "Pull request merged"),
            "sha": (data.get("sha") or "")[:12],
        }

    # ------------------------------------------------------------------
    # CI / Checks
    # ------------------------------------------------------------------

    async def get_ci_status(self, owner: str, repo: str, ref: str) -> dict:
        # Combined status (legacy status API)
        status_data = await self._get(f"/repos/{owner}/{repo}/commits/{ref}/status")
        # Check runs (newer checks API)
        try:
            checks_data = await self._get(f"/repos/{owner}/{repo}/commits/{ref}/check-runs")
        except ValueError:
            checks_data = {"check_runs": []}

        check_runs = [
            {
                "name": cr["name"],
                "status": cr["status"],
                "conclusion": cr.get("conclusion"),
                "url": cr.get("html_url"),
            }
            for cr in checks_data.get("check_runs", [])[:30]
        ]
        statuses = [
            {
                "context": s["context"],
                "state": s["state"],
                "description": s.get("description", ""),
                "url": s.get("target_url"),
            }
            for s in status_data.get("statuses", [])
        ]
        return {
            "ref": ref,
            "overall_state": status_data.get("state", "unknown"),
            "statuses": statuses,
            "check_runs": check_runs,
        }

    async def list_workflow_runs(
        self, owner: str, repo: str,
        status: str | None = None,
        branch: str | None = None,
        per_page: int = 20,
    ) -> dict:
        params: dict = {"per_page": min(per_page, 100)}
        if status:
            params["status"] = status
        if branch:
            params["branch"] = branch
        data = await self._get(f"/repos/{owner}/{repo}/actions/runs", **params)
        runs = [
            {
                "id": r["id"],
                "name": r["name"],
                "display_title": r.get("display_title", r["name"]),
                "status": r["status"],
                "conclusion": r.get("conclusion"),
                "event": r.get("event"),
                "branch": r.get("head_branch"),
                "sha": (r.get("head_sha") or "")[:12],
                "created_at": r.get("created_at"),
                "updated_at": r.get("updated_at"),
                "url": r.get("html_url"),
            }
            for r in data.get("workflow_runs", [])
        ]
        return {"total_count": data.get("total_count", len(runs)), "workflow_runs": runs}

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._client.aclose()
