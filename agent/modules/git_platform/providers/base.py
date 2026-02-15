"""Base provider interface for git platform integrations.

Each provider (GitHub, Bitbucket, GitLab, etc.) implements this interface
so the tools layer remains platform-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class GitProvider(ABC):
    """Abstract base class for git hosting platform providers."""

    @abstractmethod
    async def list_repos(self, per_page: int = 30, sort: str = "updated", search: str | None = None) -> dict:
        """List repositories accessible to the authenticated user."""

    @abstractmethod
    async def get_repo(self, owner: str, repo: str) -> dict:
        """Get repository metadata."""

    @abstractmethod
    async def list_branches(self, owner: str, repo: str, per_page: int = 30) -> dict:
        """List branches in a repository."""

    @abstractmethod
    async def delete_branch(self, owner: str, repo: str, branch: str) -> dict:
        """Delete a branch from a repository."""

    @abstractmethod
    async def get_file(self, owner: str, repo: str, path: str, ref: str | None = None) -> dict:
        """Read a file from a repository."""

    @abstractmethod
    async def list_issues(
        self, owner: str, repo: str, state: str = "open", labels: str | None = None, per_page: int = 20
    ) -> dict:
        """List issues in a repository."""

    @abstractmethod
    async def get_issue(self, owner: str, repo: str, issue_number: int) -> dict:
        """Get a single issue with comments."""

    @abstractmethod
    async def create_issue(
        self, owner: str, repo: str, title: str, body: str | None = None,
        labels: str | None = None, assignee: str | None = None,
    ) -> dict:
        """Create a new issue."""

    @abstractmethod
    async def comment_on_issue(self, owner: str, repo: str, issue_number: int, body: str) -> dict:
        """Add a comment to an issue."""

    @abstractmethod
    async def list_pull_requests(
        self, owner: str, repo: str, state: str = "open", per_page: int = 20
    ) -> dict:
        """List pull requests in a repository."""

    @abstractmethod
    async def get_pull_request(self, owner: str, repo: str, pr_number: int) -> dict:
        """Get a pull request with details."""

    @abstractmethod
    async def create_pull_request(
        self, owner: str, repo: str, title: str, head: str, base: str,
        body: str | None = None, draft: bool = False,
    ) -> dict:
        """Create a new pull request."""

    @abstractmethod
    async def comment_on_pull_request(self, owner: str, repo: str, pr_number: int, body: str) -> dict:
        """Add a comment to a pull request."""

    @abstractmethod
    async def merge_pull_request(
        self, owner: str, repo: str, pr_number: int, merge_method: str = "squash",
    ) -> dict:
        """Merge a pull request."""

    @abstractmethod
    async def create_repo(
        self, name: str, description: str | None = None,
        private: bool = True, auto_init: bool = True,
    ) -> dict:
        """Create a new repository."""

    @abstractmethod
    async def get_ci_status(self, owner: str, repo: str, ref: str) -> dict:
        """Get CI/check status for a commit or branch."""

    async def close(self) -> None:
        """Clean up resources. Override if the provider holds connections."""
