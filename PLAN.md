# Investigation Plan: Auto Push Failing When Git Creds Configured via OAuth Flow

## Problem Statement

When a user configures GitHub credentials via the OAuth flow (portal settings → GitHub OAuth), `auto_push=True` in Claude tasks fails to push to the remote repository, even though manually asking Claude to push in a `continue_task` call works fine.

## Confirmed Working / Not the Problem

Before listing bugs, establishing what definitely works helps narrow down the failure:

- **Manual push inside task container works**: When a user does `continue_task` and instructs Claude to push, Claude runs `git push` from inside its Docker container where `GITHUB_TOKEN` is set as an environment variable and the credential helper is configured. This works.
- **OAuth token is stored correctly**: The GitHub OAuth callback stores `github_token` in the credential store, `_prepare_user_credentials` reads it and sets `user_mounts["_github_token"]`, and `_build_docker_cmd` passes it as `GITHUB_TOKEN` env var to the task container.
- **Credential helper syntax is correct**: The entrypoint configures `git config --global credential.helper "!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f"` before cloning — this is the correct pattern.
- **Repo URLs are always HTTPS**: Both `portal/routers/projects.py:314` and `project_planner/tools.py:926` always construct `https://github.com/owner/repo` — so SSH key absence is not the problem.

---

## Root Cause Analysis

### Primary Bug: `auto_push` git instructions are appended to the prompt, Claude tries to push, push fails, container exits non-zero → task marked `"failed"` → `_auto_push_branch` fallback is never called

**The failure flow:**

1. `run_task` is called with `auto_push=True` and `repo_url`
2. `_execute_task` appends to the prompt (lines 1483-1489):
   ```
   IMPORTANT — Git workflow:
   - Commit your changes with descriptive commit messages as you work.
   - When you are done, push your branch: git push -u origin HEAD
   - Do NOT leave uncommitted changes.
   ```
3. Claude follows these instructions and runs `git push -u origin HEAD` from inside the container
4. **The push fails** (authentication error — see Bug 2 below)
5. Claude sees the push failure, reports it, and the container exits non-zero
6. `_run_single_container` sets `task.status = "failed"` (line 1803)
7. Back in `_execute_task` (line 1562): the auto push check is `task.status in ("completed", "awaiting_input")` — since status is `"failed"`, **`_auto_push_branch` is never called**
8. The user sees the task as failed with a git push error

**Why manual `continue_task` push works**: When the user manually continues the task and instructs Claude to push, the task is a new run which might succeed for a different reason, OR Claude is being instructed without the failing auto-push path. The key difference is that in a successful manual push, Claude doesn't fail at the push step.

---

### Bug 2 (HIGH): Git credential helper is configured AFTER the repo is cloned — but the real issue is the `GITHUB_TOKEN` variable expansion in the credential helper shell function

**File:** `agent/modules/claude_code/tools.py:2082-2085`

The entrypoint sets up the credential helper as:
```sh
git config --global credential.helper "!f() { echo username=x-access-token; echo password=$GITHUB_TOKEN; }; f"
```

This writes the literal string `$GITHUB_TOKEN` into the git config. When git later calls the helper, it executes the function in a **new shell**, and `$GITHUB_TOKEN` must still be in the environment of that new shell for expansion to work.

The git credential helper is invoked as a subprocess by git. The credential helper receives the environment of the git process, which inherits from the shell session. Since `GITHUB_TOKEN` is set as a Docker environment variable, it IS available to subprocesses — **this should work**.

However, there is a subtle issue: `su -p claude -c /tmp/git_run.sh` uses `-p` to preserve the environment. But `exec su` replaces the shell process. Depending on the `su` implementation in the Docker image (which may be from `util-linux` or `busybox`), `-p` behavior can vary. Some `su` implementations reset environment variables like `HOME` and filter others. **If `GITHUB_TOKEN` is not preserved through `su -p`**, the credential helper expands `$GITHUB_TOKEN` to empty string, and git push authenticates with an empty password → 401 from GitHub.

**This is the likely root cause for OAuth specifically**: when using SSH key auth, git uses the SSH key directly (not the credential helper), so the `su` environment preservation issue doesn't matter. When using OAuth token via `GITHUB_TOKEN`, the entire authentication chain depends on `$GITHUB_TOKEN` surviving the `su -p` invocation.

To verify: check if `su -p` in the Docker worker image preserves arbitrary environment variables, or only a subset.

---

### Bug 3 (HIGH): `_run_git_in_workspace` uses `task.id` for workspace path instead of `os.path.basename(task.workspace)`

**File:** `agent/modules/claude_code/tools.py:2431-2432`

```python
# WRONG
host_workspace = os.path.join(TASK_VOLUME, task.id)
container_workspace = os.path.join(TASK_BASE_DIR, task.id)
```

Compare with the correct implementation in `_build_docker_cmd` (lines 1943-1944):
```python
# CORRECT
workspace_dir_name = os.path.basename(task.workspace)
host_workspace = os.path.join(TASK_VOLUME, workspace_dir_name)
container_workspace = task.workspace
```

For `continue_task`, the new task has a different `task.id` but shares the parent's workspace directory (named after the parent's `task.id`). So `_run_git_in_workspace` mounts the wrong (nonexistent) directory. This affects the `_auto_push_branch` fallback, `git_status`, `git_push`, and `git_diff` tools when called on a continuation task.

**Why this doesn't explain the user's observation**: The user says manually asking Claude to push in a `continue_task` works — that's Claude pushing from inside the task container (which uses `_build_docker_cmd` with the correct path). The bug here would only affect `_auto_push_branch` called after a continuation task, or the standalone `git_push` tool called externally.

---

### Bug 4 (MEDIUM): `_auto_push_branch` is skipped when `task.status == "failed"`, even if the failure was only in the git push step

**File:** `agent/modules/claude_code/tools.py:1562`

```python
if task.auto_push and task.repo_url and task.status in ("completed", "awaiting_input"):
    await self._auto_push_branch(task, user_mounts)
```

If the Claude agent finishes all coding work but fails at the `git push` step, the container exits non-zero, `task.status = "failed"`, and the auto push fallback is never attempted — even though the workspace has committed changes ready to push. Adding `"failed"` to the status check (with a guard to only push if there are commits to push) would allow the fallback to recover from this scenario.

---

### Bug 5 (LOW): `_auto_push_branch` silently swallows `git fetch` errors due to `set -e` + `2>/dev/null`

**File:** `agent/modules/claude_code/tools.py:2272`

```sh
git fetch origin 2>/dev/null;
```

The inner shell script runs with `set -e`. If `git fetch origin` fails (e.g., network error, auth failure), stderr is discarded and the script exits immediately — before printing `UP_TO_DATE` or `NEEDS_PUSH`. `check_out` will be empty, which doesn't match `UP_TO_DATE`, so the code proceeds to commit+push. This means a fetch failure causes a spurious commit+push attempt, but the push itself will also fail. The error is captured in `push_result["error"]`. Not a show-stopper but adds noise.

---

## Summary Table

| # | Severity | Location | Issue |
|---|----------|----------|-------|
| 1 | CRITICAL | `_execute_task` + container entrypoint | Claude is instructed to push, push fails (likely `GITHUB_TOKEN` not surviving `su -p`), container exits non-zero, task marked failed, `_auto_push_branch` never runs |
| 2 | HIGH | `_entrypoint_script` line 2082-2085 | `GITHUB_TOKEN` may not survive `su -p claude` in the worker image's `su` implementation |
| 3 | HIGH | `_run_git_in_workspace` line 2431-2432 | Wrong workspace path for continuation tasks |
| 4 | MEDIUM | `_execute_task` line 1562 | `_auto_push_branch` skipped when task is `"failed"` |
| 5 | LOW | `_auto_push_branch` line 2272 | `git fetch` failure with `set -e` silently exits check script |

---

## Files to Modify

- **`agent/modules/claude_code/tools.py`** — All fixes are in this file

---

## Implementation Steps

### Step 1: Fix the `su` environment preservation issue (Bug 2)

**Option A — Use `env` to explicitly pass `GITHUB_TOKEN` to the inner script:**

Instead of relying on `su -p` to preserve `GITHUB_TOKEN`, explicitly pass it:

```sh
# Replace:
exec su -p claude -c /tmp/git_run.sh

# With (in _run_git_in_workspace entrypoint):
exec su claude -c "GITHUB_TOKEN=$GITHUB_TOKEN /tmp/git_run.sh"
```

Or more robustly, write the token into the script file directly (avoiding shell injection by using a file):

```sh
# In _run_git_in_workspace entrypoint, before writing git_run.sh:
# Write GITHUB_TOKEN into a file readable only by claude
echo "$GITHUB_TOKEN" > /tmp/.github_token
chmod 600 /tmp/.github_token
chown claude:claude /tmp/.github_token

# In git_run.sh:
GITHUB_TOKEN=$(cat /tmp/.github_token 2>/dev/null || true)
```

**Option B — Set up the credential store via a helper file instead of env var:**

Write the token to `.git-credentials` in the home directory (netrc format) instead of using a shell function helper. This avoids env var issues entirely:

```sh
if [ -n "$GITHUB_TOKEN" ]; then
    echo "https://x-access-token:${GITHUB_TOKEN}@github.com" > "$CLAUDE_HOME/.git-credentials"
    chmod 600 "$CLAUDE_HOME/.git-credentials"
    git config --global credential.helper store
fi
```

**Option B is safer** because it doesn't depend on env var propagation through `su`, and the credential file is already in the home directory which `su` switches to.

The same fix applies to `_entrypoint_script` (the main task container) for consistency, though in the main container the issue may not manifest because `su -p` behavior might differ, or because `set -e` is not used.

### Step 2: Fix `_auto_push_branch` to also run when task is "failed" (Bug 4)

```python
# In _execute_task, replace:
if task.auto_push and task.repo_url and task.status in ("completed", "awaiting_input"):
    await self._auto_push_branch(task, user_mounts)

# With:
if task.auto_push and task.repo_url and task.status in ("completed", "awaiting_input", "failed"):
    await self._auto_push_branch(task, user_mounts)
```

`_auto_push_branch` already has a `try/except` wrapper, and it checks `UP_TO_DATE` before doing anything. If the task failed before any commits, there's nothing to push and the fallback exits cleanly. If the task failed only at the push step, the fallback will attempt to push.

### Step 3: Fix workspace path in `_run_git_in_workspace` (Bug 3)

```python
# In _run_git_in_workspace, replace lines 2431-2432:
host_workspace = os.path.join(TASK_VOLUME, task.id)
container_workspace = os.path.join(TASK_BASE_DIR, task.id)

# With:
workspace_dir_name = os.path.basename(task.workspace)
host_workspace = os.path.join(TASK_VOLUME, workspace_dir_name)
container_workspace = task.workspace
```

Also update the volume mount (line 2438) — no change in syntax needed, just the values become correct via the above variable changes.

### Step 4: Fix `git fetch` with `set -e` (Bug 5)

In the `_auto_push_branch` check command, either:
- Remove `set -e` from the inner check script (by not using `eval "$GIT_CMD"` with `set -e`)
- Or handle the fetch separately:

```python
check_cmd = (
    "git fetch origin 2>/dev/null || true; "  # Add || true to prevent set -e exit
    "LOCAL=$(git rev-parse HEAD); "
    "REMOTE=$(git rev-parse @{u} 2>/dev/null || echo 'none'); "
    "DIRTY=$(git status --porcelain | head -1); "
    "if [ -z \"$DIRTY\" ] && [ \"$LOCAL\" = \"$REMOTE\" ]; then "
    "echo 'UP_TO_DATE'; else echo 'NEEDS_PUSH'; fi"
)
```

---

## Verification / Testing Plan

1. **Reproduce the failure**: Create a task with `auto_push=True`, a GitHub HTTPS repo URL, and OAuth-only credentials (no SSH key). Observe the task log for `git push` errors inside the container.

2. **Test `su` env var preservation**: Inside the worker Docker image, run:
   ```sh
   docker run --rm -e GITHUB_TOKEN=test_value <worker_image> sh -c \
     'echo "GITHUB_TOKEN=$GITHUB_TOKEN" && su -p claude -c "echo inner: GITHUB_TOKEN=\$GITHUB_TOKEN"'
   ```
   If the inner print shows empty `GITHUB_TOKEN`, the env var is lost through `su -p`.

3. **Apply Step 1 fix**: After switching to `.git-credentials` store approach, repeat the task creation. Verify the task log shows successful `git push` from inside the container, and `_auto_push_branch` reports `already pushed by agent`.

4. **Test Step 2 fix**: Create a task that fails at the push step (e.g., by temporarily using a bad token). Verify `_auto_push_branch` is now attempted and either succeeds (if a correct token is available from user_mounts) or fails with a clear error in `task.result["auto_push"]`.

5. **Test continuation task auto push**: Create a task, then call `continue_task` with `auto_push=True`. Verify `_run_git_in_workspace` now mounts the correct workspace directory (the parent's workspace path, not the continuation task's ID).
