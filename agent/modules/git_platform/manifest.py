"""Git Platform module manifest — tool definitions.

Provides repository, issue, pull request, and CI status tools
for GitHub (with Bitbucket/GitLab support planned via provider pattern).
"""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

# Common parameters reused across tools
_OWNER = ToolParameter(name="owner", type="string", description="Repository owner or organisation name.")
_REPO = ToolParameter(name="repo", type="string", description="Repository name.")

MANIFEST = ModuleManifest(
    module_name="git_platform",
    description="Interact with Git hosting platforms (GitHub, Bitbucket). Manage repositories, issues, pull requests, and CI status.",
    tools=[
        # ---- Repository ----
        ToolDefinition(
            name="git_platform.list_repos",
            description="List repositories accessible to the authenticated user. Returns name, description, language, stars, and clone URL for each repo.",
            parameters=[
                ToolParameter(name="per_page", type="integer", description="Max repos to return (default 30).", required=False),
                ToolParameter(name="sort", type="string", description="Sort order.", enum=["updated", "created", "pushed", "full_name"], required=False),
                ToolParameter(name="search", type="string", description="Filter repos by name.", required=False),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="git_platform.get_repo",
            description="Get repository metadata including description, default branch, language, stars, and fork count.",
            parameters=[_OWNER, _REPO],
            required_permission="guest",
        ),
        ToolDefinition(
            name="git_platform.list_branches",
            description="List branches in a repository with their latest commit SHA and protection status.",
            parameters=[
                _OWNER,
                _REPO,
                ToolParameter(name="per_page", type="integer", description="Max branches to return (default 30).", required=False),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="git_platform.delete_branch",
            description="Delete a branch from a repository. Cannot delete protected or default branches.",
            parameters=[
                _OWNER,
                _REPO,
                ToolParameter(name="branch", type="string", description="Branch name to delete."),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="git_platform.get_file",
            description="Read a file (or list a directory) from a repository without cloning. Returns the decoded text content for files or a listing for directories.",
            parameters=[
                _OWNER,
                _REPO,
                ToolParameter(name="path", type="string", description="File or directory path within the repository."),
                ToolParameter(name="ref", type="string", description="Branch, tag, or commit SHA (defaults to the repo's default branch).", required=False),
            ],
            required_permission="guest",
        ),
        # ---- Issues ----
        ToolDefinition(
            name="git_platform.list_issues",
            description="List issues in a repository, optionally filtered by state and labels. Does not include pull requests.",
            parameters=[
                _OWNER,
                _REPO,
                ToolParameter(name="state", type="string", description="Filter by state.", enum=["open", "closed", "all"], required=False),
                ToolParameter(name="labels", type="string", description="Comma-separated label names to filter by.", required=False),
                ToolParameter(name="per_page", type="integer", description="Max issues to return (default 20).", required=False),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="git_platform.get_issue",
            description="Get full details of an issue including body, labels, assignee, and recent comments.",
            parameters=[
                _OWNER,
                _REPO,
                ToolParameter(name="issue_number", type="integer", description="Issue number."),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="git_platform.create_issue",
            description="Create a new issue in a repository.",
            parameters=[
                _OWNER,
                _REPO,
                ToolParameter(name="title", type="string", description="Issue title."),
                ToolParameter(name="body", type="string", description="Issue body (markdown).", required=False),
                ToolParameter(name="labels", type="string", description="Comma-separated label names.", required=False),
                ToolParameter(name="assignee", type="string", description="Username to assign.", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="git_platform.comment_on_issue",
            description="Add a comment to an existing issue.",
            parameters=[
                _OWNER,
                _REPO,
                ToolParameter(name="issue_number", type="integer", description="Issue number."),
                ToolParameter(name="body", type="string", description="Comment body (markdown)."),
            ],
            required_permission="user",
        ),
        # ---- Pull Requests ----
        ToolDefinition(
            name="git_platform.list_pull_requests",
            description="List pull requests in a repository. Returns PR number, title, author, head/base branches, and draft status.",
            parameters=[
                _OWNER,
                _REPO,
                ToolParameter(name="state", type="string", description="Filter by state.", enum=["open", "closed", "all"], required=False),
                ToolParameter(name="per_page", type="integer", description="Max PRs to return (default 20).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="git_platform.get_pull_request",
            description="Get full details of a pull request including diff stats, changed files, and review comments.",
            parameters=[
                _OWNER,
                _REPO,
                ToolParameter(name="pr_number", type="integer", description="Pull request number."),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="git_platform.create_pull_request",
            description="Create a new pull request. The head branch must already exist with commits pushed.",
            parameters=[
                _OWNER,
                _REPO,
                ToolParameter(name="title", type="string", description="PR title."),
                ToolParameter(name="head", type="string", description="Branch containing changes (e.g. 'feature/my-change')."),
                ToolParameter(name="base", type="string", description="Branch to merge into (e.g. 'main')."),
                ToolParameter(name="body", type="string", description="PR description (markdown).", required=False),
                ToolParameter(name="draft", type="boolean", description="Create as draft PR (default false).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="git_platform.comment_on_pull_request",
            description="Add a comment to an existing pull request.",
            parameters=[
                _OWNER,
                _REPO,
                ToolParameter(name="pr_number", type="integer", description="Pull request number."),
                ToolParameter(name="body", type="string", description="Comment body (markdown)."),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="git_platform.merge_pull_request",
            description="Merge a pull request. Only works if the PR is mergeable (no conflicts, checks passed).",
            parameters=[
                _OWNER,
                _REPO,
                ToolParameter(name="pr_number", type="integer", description="Pull request number."),
                ToolParameter(name="merge_method", type="string", description="Merge strategy.", enum=["merge", "squash", "rebase"], required=False),
            ],
            required_permission="admin",
        ),
        # ---- CI / Checks ----
        ToolDefinition(
            name="git_platform.get_ci_status",
            description="Get the CI/CD pipeline status for a branch or commit. Returns both check runs (GitHub Actions) and commit statuses.",
            parameters=[
                _OWNER,
                _REPO,
                ToolParameter(name="ref", type="string", description="Branch name, tag, or commit SHA to check."),
            ],
            required_permission="user",
        ),
    ],
)
