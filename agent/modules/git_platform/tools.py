"""Git Platform tool implementations.

Delegates to the configured provider (GitHub, Bitbucket, etc.).
"""

from __future__ import annotations

import structlog

from modules.git_platform.providers.base import GitProvider

logger = structlog.get_logger()


class GitPlatformTools:
    """Tool implementations that delegate to a GitProvider."""

    def __init__(self, provider: GitProvider):
        self.provider = provider

    # ---- Repository ----

    async def get_repo(self, owner: str, repo: str) -> dict:
        return await self.provider.get_repo(owner, repo)

    async def list_branches(self, owner: str, repo: str, per_page: int = 30) -> dict:
        return await self.provider.list_branches(owner, repo, per_page=per_page)

    async def get_file(self, owner: str, repo: str, path: str, ref: str | None = None) -> dict:
        return await self.provider.get_file(owner, repo, path, ref=ref)

    # ---- Issues ----

    async def list_issues(
        self, owner: str, repo: str, state: str = "open",
        labels: str | None = None, per_page: int = 20,
    ) -> dict:
        return await self.provider.list_issues(owner, repo, state=state, labels=labels, per_page=per_page)

    async def get_issue(self, owner: str, repo: str, issue_number: int) -> dict:
        return await self.provider.get_issue(owner, repo, issue_number)

    async def create_issue(
        self, owner: str, repo: str, title: str, body: str | None = None,
        labels: str | None = None, assignee: str | None = None,
    ) -> dict:
        return await self.provider.create_issue(
            owner, repo, title, body=body, labels=labels, assignee=assignee,
        )

    async def comment_on_issue(self, owner: str, repo: str, issue_number: int, body: str) -> dict:
        return await self.provider.comment_on_issue(owner, repo, issue_number, body)

    # ---- Pull Requests ----

    async def list_pull_requests(
        self, owner: str, repo: str, state: str = "open", per_page: int = 20,
    ) -> dict:
        return await self.provider.list_pull_requests(owner, repo, state=state, per_page=per_page)

    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        return await self.provider.get_pull_request(owner, repo, pr_number)

    async def create_pull_request(
        self, owner: str, repo: str, title: str, head: str, base: str,
        body: str | None = None, draft: bool = False,
    ) -> dict:
        return await self.provider.create_pull_request(
            owner, repo, title, head, base, body=body, draft=draft,
        )

    async def comment_on_pull_request(self, owner: str, repo: str, pr_number: int, body: str) -> dict:
        return await self.provider.comment_on_pull_request(owner, repo, pr_number, body)

    async def merge_pull_request(
        self, owner: str, repo: str, pr_number: int, merge_method: str = "squash",
    ) -> dict:
        return await self.provider.merge_pull_request(owner, repo, pr_number, merge_method=merge_method)

    # ---- CI / Checks ----

    async def get_ci_status(self, owner: str, repo: str, ref: str) -> dict:
        return await self.provider.get_ci_status(owner, repo, ref)
