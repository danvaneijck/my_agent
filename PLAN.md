# Investigation Plan: Auto Push Failing When Git Creds Configured via OAuth Flow

## Problem Statement

When a user configures GitHub credentials via the OAuth flow (portal settings), `auto_push` in Claude tasks fails to push to the remote repository, even though the credentials appear to be configured correctly.

---

## Root Cause Analysis

After examining the codebase thoroughly, **multiple bugs and design gaps** have been identified that collectively cause this failure. They are ordered by most-likely to least-likely impact.

---

### Bug 1 (CRITICAL): `_run_git_in_workspace` uses `task.id` for workspace path, not the actual workspace directory name

**File:** `agent/modules/claude_code/tools.py:2431-2432`

```python
# WRONG — uses task.id, not the actual workspace dir name
host_workspace = os.path.join(TASK_VOLUME, task.id)
container_workspace = os.path.join(TASK_BASE_DIR, task.id)
```

Compare with the correct implementation in `_build_docker_cmd` at lines 1943-1944:

```python
# CORRECT — uses basename of workspace path
workspace_dir_name = os.path.basename(task.workspace)
host_workspace = os.path.join(TASK_VOLUME, workspace_dir_name)
container_workspace = task.workspace
```

**Why this causes failure:**

`continue_task` creates a new task with a new `task.id` but reuses the **parent task's workspace directory** (named after the parent's `task.id`). When `_auto_push_branch` is called for a continuation task, it computes `host_workspace = TASK_VOLUME / new_task.id`, but that directory does not exist — only `TASK_VOLUME / parent_task.id` does. The Docker container either fails to start or starts in an empty workspace with no `.git` directory, causing the push to fail silently or with a confusing error.

This also affects the `git_push`, `git_status`, `git_diff`, and `git_log` tool methods which all call `_run_git_in_workspace`.

**The `-w task.workspace` flag (line 2439)** makes this even worse: the container working directory is set to `task.workspace` (the correct path inside the container) but the volume is mounted at the wrong path (`container_workspace = TASK_BASE_DIR/task.id` instead of the actual parent's workspace), so there is no `.git` to work with.

---

### Bug 2 (HIGH): `_auto_push_branch` is NOT called when `task.status` is `"failed"` — but credentials are cleaned up before push in the `finally` block

**File:** `agent/modules/claude_code/tools.py:1561-1588`

```python
# Auto-push on final successful exit
if task.auto_push and task.repo_url and task.status in ("completed", "awaiting_input"):
    await self._auto_push_branch(task, user_mounts)

except Exception as e:
    ...
    task.status = "failed"
    task.error = str(e)
finally:
    task.completed_at = ...
    task.save()
    ...
    # Clean up decrypted credentials from disk
    if user_id:
        creds_dir = os.path.join(USER_CREDS_DIR, user_id)
        shutil.rmtree(creds_dir)   # <-- Runs AFTER auto_push attempt
```

The control flow here is correct — cleanup happens in `finally` after `_auto_push_branch` runs. **However**, this means the user mounts (paths to credential files on disk) passed to `_auto_push_branch` are still valid directories during the push. This is fine in the nominal path.

The issue is that `task.status` is set from `_run_single_container`'s return value via:

```python
exit_reason = await self._run_single_container(task, ...)
```

But looking at `_run_single_container`, it sets `task.status` to `"completed"` or `"failed"` (not directly visible here — need to confirm), and if it's `"failed"`, the auto push is skipped entirely. This means code that fails inside the container but still has commits to push will never get auto-pushed.

---

### Bug 3 (HIGH): GitHub OAuth tokens stored as `github_token` are not refreshed before use in auto push

**File:** `agent/modules/claude_code/tools.py:1919-1921` and `agent/portal/routers/settings.py:609-617`

When a user authenticates via the GitHub OAuth flow, the portal stores:
- `github_token` — the OAuth access token
- `github_refresh_token` — only for fine-grained tokens with expiration enabled
- `github_token_expires_at` — only if the token has expiration

In `_prepare_user_credentials` (line 1919), the GitHub token is extracted:
```python
gh_token = github_creds.get("github_token", "")
if gh_token:
    mounts["_github_token"] = gh_token
```

**There is no proactive refresh of the GitHub OAuth token** before it is passed to Docker — unlike Claude credentials which have `_maybe_refresh_credentials`. For fine-grained GitHub tokens (which do expire, typically after a user-configured period), if the token has expired, the push will fail with a 401 from GitHub.

Standard GitHub OAuth tokens (classic) don't expire, so this only affects users who configured fine-grained tokens. The `git_platform` module's `_refresh_bitbucket_token` shows the pattern that should exist for GitHub — check expiry and refresh proactively.

---

### Bug 4 (MEDIUM): The OAuth `GITHUB_TOKEN` credential helper in the git container does not handle token expiry or retry

**File:** `agent/modules/claude_code/tools.py:2421-2423`

The HTTPS credential helper is configured inline as a shell function:
```sh
git config --global credential.helper "!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f"
```

If `GITHUB_TOKEN` is an expired fine-grained token, `git push` will get a 401/403 from GitHub. The error surfaced in the task log will be a vague authentication failure. There is no retry or refresh path in this helper — it just fails.

---

### Bug 5 (MEDIUM): `_auto_push_branch` uses `task.workspace` as the container's working directory, but workspace path correctness depends on Bug 1 being fixed

**File:** `agent/modules/claude_code/tools.py:2439`

```python
"-w", task.workspace,
```

`task.workspace` stores the absolute container-internal path (e.g. `/tmp/claude_tasks/<task_id>`). For continuation tasks, the workspace is the **parent's** path (correct), but the volume mount at line 2438 will be wrong until Bug 1 is fixed. After Bug 1 is fixed, both the volume mount and `-w` will be consistent.

---

### Bug 6 (LOW): The `_auto_push_branch` check for `UP_TO_DATE` uses `git rev-parse @{u}` which fails for new branches with no upstream

**File:** `agent/modules/claude_code/tools.py:2274`

```sh
REMOTE=$(git rev-parse @{u} 2>/dev/null || echo 'none');
```

If the branch has never been pushed (which is the normal case for auto_push), `@{u}` has no upstream tracking branch. The fallback `|| echo 'none'` means `REMOTE='none'` and `LOCAL != REMOTE`, so the check correctly proceeds to push. This is not a bug per se, but the `git fetch origin` at the start of the check (line 2272) can fail silently for HTTPS repos when credentials are not yet configured in that container. The `2>/dev/null` swallows the error and continues.

---

## Summary of Root Causes

| # | Severity | Issue |
|---|----------|-------|
| 1 | CRITICAL | `_run_git_in_workspace` uses `task.id` for workspace path instead of `os.path.basename(task.workspace)`, causing git operations to mount wrong/nonexistent directory for continuation tasks |
| 2 | HIGH | Auto push skipped when task status is `"failed"`, even if the Claude agent committed work before failing |
| 3 | HIGH | No proactive GitHub OAuth token refresh before push — expired fine-grained tokens cause silent auth failures |
| 4 | MEDIUM | No retry or token refresh in the git credential helper for expired HTTPS tokens |
| 5 | MEDIUM | Workspace path bug (Bug 1) cascades into wrong `-w` working directory for git container |
| 6 | LOW | `git fetch origin` in status check can fail silently, producing misleading check output |

---

## Files to Modify

### Primary fix target
- **`agent/modules/claude_code/tools.py`** — All bugs are in this file

### Specific locations
1. `_run_git_in_workspace` (line 2431-2432): Fix workspace path derivation
2. `_execute_task` (line 1562): Consider adding `"failed"` to statuses that trigger auto push, or at least log why push was skipped
3. `_prepare_user_credentials` (line 1918-1921): Add GitHub token expiry check and refresh before returning mounts
4. `_run_git_in_workspace` entrypoint script (line 2421): Consider adding better error output for auth failures

---

## Implementation Steps

### Step 1: Fix Bug 1 — Workspace path in `_run_git_in_workspace`

Replace lines 2431-2432:
```python
# OLD (wrong)
host_workspace = os.path.join(TASK_VOLUME, task.id)
container_workspace = os.path.join(TASK_BASE_DIR, task.id)

# NEW (correct — same pattern as _build_docker_cmd)
workspace_dir_name = os.path.basename(task.workspace)
host_workspace = os.path.join(TASK_VOLUME, workspace_dir_name)
container_workspace = task.workspace
```

Also update the volume mount argument at line 2438:
```python
# OLD
"-v", f"{host_workspace}:{container_workspace}",

# NEW
"-v", f"{host_workspace}:{container_workspace}",
# (same syntax, but now with correct values)
```

### Step 2: Add GitHub OAuth token proactive refresh

Add a new helper function analogous to `_maybe_refresh_credentials`:

```python
async def _maybe_refresh_github_token(user_id: str, github_creds: dict) -> dict:
    """Proactively refresh GitHub OAuth token if it has an expiry and is close to expiring.

    Returns updated github_creds dict. On failure, returns original.
    Only applies to fine-grained tokens that have expiry set.
    """
    expires_at_iso = github_creds.get("github_token_expires_at")
    refresh_token = github_creds.get("github_refresh_token")

    if not expires_at_iso or not refresh_token:
        # Classic tokens don't expire; nothing to do
        return github_creds

    from datetime import datetime, timezone
    try:
        expires_at = datetime.fromisoformat(expires_at_iso)
        now = datetime.now(timezone.utc)
        remaining = (expires_at - now).total_seconds()

        if remaining > 1800:  # more than 30 minutes left
            return github_creds

        logger.info("proactive_github_token_refresh", user_id=user_id, remaining_seconds=remaining)

        # Use the GitHubOAuthProvider to refresh
        from portal.git_oauth import GitHubOAuthProvider
        from shared.config import get_settings
        settings = get_settings()
        provider = GitHubOAuthProvider(
            client_id=settings.github_oauth_client_id,
            client_secret=settings.github_oauth_client_secret,
        )
        new_tokens = await provider.refresh_access_token(refresh_token)
        if not new_tokens:
            return github_creds

        updated = dict(github_creds)
        updated["github_token"] = new_tokens.access_token
        if new_tokens.refresh_token:
            updated["github_refresh_token"] = new_tokens.refresh_token
        if new_tokens.expires_at:
            expires_dt = datetime.fromtimestamp(new_tokens.expires_at / 1000, tz=timezone.utc)
            updated["github_token_expires_at"] = expires_dt.isoformat()

        # Persist refreshed token to DB
        from shared.credential_store import CredentialStore
        from shared.database import get_session_factory
        if settings.credential_encryption_key:
            store = CredentialStore(settings.credential_encryption_key)
            factory = get_session_factory()
            async with factory() as session:
                await store.set_many(session, user_id, "github", {
                    k: v for k, v in updated.items()
                    if k in ("github_token", "github_refresh_token", "github_token_expires_at")
                })

        logger.info("proactive_github_token_refresh_success", user_id=user_id)
        return updated
    except Exception as e:
        logger.warning("proactive_github_token_refresh_error", user_id=user_id, error=str(e))
        return github_creds
```

Call this in `_prepare_user_credentials` before extracting the token:
```python
# In _prepare_user_credentials, after getting github_creds:
github_creds_dict = dict(github_creds)
if user_id:
    github_creds_dict = await _maybe_refresh_github_token(user_id, github_creds_dict)

gh_token = github_creds_dict.get("github_token", "")
```

### Step 3: Improve auth failure diagnostics in git container

In `_run_git_in_workspace` entrypoint, add explicit credential verification before running the git command:

```sh
# After credential helper setup, log whether a token is set
if [ -n "$GITHUB_TOKEN" ]; then
    echo "[git-container] GITHUB_TOKEN is set (length: ${#GITHUB_TOKEN})"
else
    echo "[git-container] WARNING: No GITHUB_TOKEN set. Push may fail for HTTPS repos."
fi
```

This is diagnostic only and doesn't affect execution, but makes failure logs actionable.

### Step 4: Log auto push skip reason when task status prevents push

In `_execute_task`, after the auto push condition:
```python
if task.auto_push and task.repo_url and task.status in ("completed", "awaiting_input"):
    await self._auto_push_branch(task, user_mounts)
elif task.auto_push and task.repo_url:
    logger.info(
        "auto_push_skipped_bad_status",
        task_id=task.id,
        status=task.status,
    )
```

---

## Testing Plan

1. **Regression test for Bug 1**: Create a task with `auto_push=True` and a repo. Then call `continue_task` on it. Verify `_auto_push_branch` mounts the correct workspace directory by checking container logs.

2. **OAuth token flow test**: Configure a fine-grained GitHub token with expiry in the credential store. Set `github_token_expires_at` to a time within 30 minutes. Verify `_maybe_refresh_github_token` is called and the refresh succeeds.

3. **End-to-end test**: Create a task with `repo_url` and `auto_push=True`, using OAuth-configured credentials (not SSH). Verify the branch is pushed to GitHub after the container exits.

4. **Classic token test**: Verify classic GitHub OAuth tokens (no expiry) still work without triggering a refresh attempt.

---

## What is NOT the Root Cause

- The credential helper syntax in the entrypoint is correct (`echo username=x-access-token; echo password=$GITHUB_TOKEN`)
- The OAuth flow itself stores the token under the correct key (`github_token`)
- The `_prepare_user_credentials` function correctly reads and passes the token
- The `_entrypoint_script` correctly configures the credential helper for the main container (this is for Claude's git operations during the task, which may work fine)
- The `finally` cleanup block ordering is correct — credentials are cleaned up after auto push completes
