# git_platform

GitHub and Bitbucket integration via provider pattern. Manage repositories, issues, pull requests, and CI status.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `git_platform.list_repos` | List accessible repositories | guest |
| `git_platform.get_repo` | Get repository metadata | guest |
| `git_platform.list_branches` | List branches with commit SHA and protection | guest |
| `git_platform.get_file` | Read a file or list directory without cloning | guest |
| `git_platform.list_issues` | List issues (excludes PRs) | guest |
| `git_platform.get_issue` | Get full issue details with comments | guest |
| `git_platform.create_issue` | Create a new issue | user |
| `git_platform.comment_on_issue` | Add a comment to an issue | user |
| `git_platform.list_pull_requests` | List PRs with head/base/draft status | user |
| `git_platform.get_pull_request` | Get PR details with diff stats and reviews | user |
| `git_platform.create_pull_request` | Create a new PR | user |
| `git_platform.comment_on_pull_request` | Add a comment to a PR | user |
| `git_platform.merge_pull_request` | Merge a PR (merge/squash/rebase) | admin |
| `git_platform.get_ci_status` | Get CI/CD status for branch or commit | user |

## Tool Details

### Repository Tools

**`git_platform.list_repos`**
- **per_page** (integer, optional) — default 30
- **sort** (string, optional) — `updated`, `created`, `pushed`, `full_name`
- **search** (string, optional) — filter by name

**`git_platform.get_repo`**
- **owner** (string, required), **repo** (string, required)
- Returns description, default_branch, language, stars, forks

**`git_platform.list_branches`**
- **owner**, **repo** (required), **per_page** (optional, default 30)

**`git_platform.get_file`**
- **owner**, **repo** (required), **path** (string, required)
- **ref** (string, optional) — branch/tag/SHA (defaults to repo default branch)
- Returns decoded text for files, listing for directories

### Issue Tools

**`git_platform.list_issues`**
- **owner**, **repo** (required)
- **state** (optional) — `open`, `closed`, `all`
- **labels** (string, optional) — comma-separated
- **per_page** (optional, default 20)

**`git_platform.get_issue`**
- **owner**, **repo** (required), **issue_number** (integer, required)

**`git_platform.create_issue`**
- **owner**, **repo**, **title** (required)
- **body** (optional), **labels** (optional, comma-separated), **assignee** (optional)

**`git_platform.comment_on_issue`**
- **owner**, **repo** (required), **issue_number** (integer, required), **body** (string, required)

### Pull Request Tools

**`git_platform.list_pull_requests`**
- **owner**, **repo** (required)
- **state** (optional) — `open`, `closed`, `all`
- **per_page** (optional, default 20)

**`git_platform.get_pull_request`**
- **owner**, **repo** (required), **pr_number** (integer, required)
- Returns diff stats, changed files, review comments

**`git_platform.create_pull_request`**
- **owner**, **repo**, **title**, **head**, **base** (required)
- **body** (optional), **draft** (boolean, optional)
- Head branch must exist with commits pushed

**`git_platform.comment_on_pull_request`**
- **owner**, **repo** (required), **pr_number** (integer, required), **body** (string, required)

**`git_platform.merge_pull_request`**
- **owner**, **repo** (required), **pr_number** (integer, required)
- **merge_method** (optional) — `merge`, `squash`, `rebase`
- Only works if PR is mergeable (no conflicts, checks passed)

### CI Tools

**`git_platform.get_ci_status`**
- **owner**, **repo** (required), **ref** (string, required) — branch/tag/SHA
- Returns both check runs (GitHub Actions) and commit statuses

## Implementation Notes

- Provider pattern: `providers/base.py` (abstract interface), `providers/github.py`, `providers/bitbucket.py`
- Each provider implements the same tool interface; routing in `main.py` selects based on config
- Uses `httpx` for async HTTP calls to platform APIs
- Per-user credential lookup from database

## Key Files

- `agent/modules/git_platform/manifest.py`
- `agent/modules/git_platform/tools.py`
- `agent/modules/git_platform/main.py`
- `agent/modules/git_platform/providers/base.py`
- `agent/modules/git_platform/providers/github.py`
- `agent/modules/git_platform/providers/bitbucket.py`
