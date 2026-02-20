# Investigation Plan: Auto Push Failing When Git Creds Configured via OAuth Flow

## Problem Statement

When a user configures GitHub credentials via the OAuth flow (portal settings → GitHub OAuth), `auto_push=True` in Claude tasks fails to push to the remote repository on **continuation runs** (after giving feedback via the portal). The **first run** (fresh branch) succeeds.

## Confirmed Symptom Pattern

- **First run (fresh task)** — auto push succeeds
- **Second run (continue_task after feedback)** — auto push fails

This narrows the root cause significantly.

---

## Root Cause: `_run_git_in_workspace` uses `task.id` instead of the workspace directory name

**File:** `agent/modules/claude_code/tools.py:2431-2432`

### What happens on the first run (succeeds)

1. `run_task` creates a task: `task.id = "abc123"`, `task.workspace = /tmp/claude_tasks/abc123`
2. Claude runs in container (via `_build_docker_cmd`): correctly mounts `TASK_VOLUME/abc123` → workspace
3. Claude pushes successfully from inside the container (`GITHUB_TOKEN` is in env, credential helper works)
4. Container exits 0 → `task.status = "completed"`
5. `_auto_push_branch(task, user_mounts)` is called → calls `_run_git_in_workspace`
6. In `_run_git_in_workspace`: `host_workspace = TASK_VOLUME/task.id = TASK_VOLUME/abc123` ✓ (correct — `task.id` equals the workspace dir name for a fresh task)
7. Git check sees `UP_TO_DATE` (Claude already pushed) → skips → success

### What happens on the second run (fails)

1. User gives feedback via portal → `continue_task` is called
2. A new task is created: `task.id = "xyz789"`, but `task.workspace = /tmp/claude_tasks/abc123` (reuses parent's workspace)
3. `effective_auto_push = True` (inherited from parent via `original.auto_push`)
4. Claude runs in container (via `_build_docker_cmd`): correctly uses `os.path.basename(task.workspace) = "abc123"` → mounts `TASK_VOLUME/abc123` → workspace ✓
5. Claude commits new changes and pushes from inside container — succeeds
6. Container exits 0 → `task.status = "completed"`
7. `_auto_push_branch(task, user_mounts)` is called → calls `_run_git_in_workspace`
8. **In `_run_git_in_workspace` (line 2431-2432):**
   ```python
   host_workspace = os.path.join(TASK_VOLUME, task.id)   # = TASK_VOLUME/xyz789 ← WRONG
   container_workspace = os.path.join(TASK_BASE_DIR, task.id)  # = /tmp/claude_tasks/xyz789 ← WRONG
   ```
   But `TASK_VOLUME/xyz789` does **not exist** — the workspace lives at `TASK_VOLUME/abc123`
9. Docker command: `-v TASK_VOLUME/xyz789:/tmp/claude_tasks/xyz789 -w /tmp/claude_tasks/abc123`
   - Volume mount points to nonexistent directory
   - Working directory (`-w`) points to a path that is NOT mounted
10. The git check script starts with `set -e`, runs `git fetch origin` in an unmounted directory — fails immediately
11. `check_out` is empty → not `UP_TO_DATE` → proceeds to push
12. Push command also fails (no `.git` in working directory)
13. `_auto_push_branch` catches the error, stores `{"success": False, "error": "..."}` in `task.result["auto_push"]`
14. Task is still `"completed"` but push failed — user sees auto push failure

### The fix location

Compare the broken code with the correct implementation already used in `_build_docker_cmd`:

```python
# _build_docker_cmd (CORRECT — lines 1943-1944):
workspace_dir_name = os.path.basename(task.workspace)
host_workspace = os.path.join(TASK_VOLUME, workspace_dir_name)
container_workspace = task.workspace

# _run_git_in_workspace (WRONG — lines 2431-2432):
host_workspace = os.path.join(TASK_VOLUME, task.id)
container_workspace = os.path.join(TASK_BASE_DIR, task.id)
```

The fix is to apply the same pattern as `_build_docker_cmd`.

---

## Secondary Issues (lower priority)

### Issue 2: Portal's `ContinueTaskRequest` has no `auto_push` field

**File:** `agent/portal/routers/tasks.py:65-68`

```python
class ContinueTaskRequest(BaseModel):
    prompt: str
    timeout: int | None = None
    mode: str | None = None  # None = inherit from parent
    # no auto_push field
```

`continue_task` in tools.py defaults `auto_push=None`, which triggers inheritance from the parent task. This is the intended behaviour for the project planner workflow, but means there's no way via the portal UI to explicitly disable auto push on a continuation. Not a bug that causes the failure, but worth noting.

### Issue 3: `git fetch` with `set -e` silently exits check script

**File:** `agent/modules/claude_code/tools.py:2272`

The `_run_git_in_workspace` inner script runs with `set -e`. The check command is:
```sh
git fetch origin 2>/dev/null; ...
```

If `git fetch` fails (nonexistent path, network error), `set -e` causes the inner script to exit before printing `UP_TO_DATE` or `NEEDS_PUSH`. `check_out` is empty, so the code proceeds to push. With the primary bug fixed, this becomes a minor noise issue rather than a blocking one. The fix is `|| true` on the fetch.

### Issue 4: `_auto_push_branch` is not called when `task.status == "failed"`

**File:** `agent/modules/claude_code/tools.py:1562`

If a task fails (Claude's container exits non-zero), the auto push fallback is never attempted even if the Claude agent committed work before failing. Adding `"failed"` to the allowed statuses would allow recovery.

---

## Files to Modify

- **`agent/modules/claude_code/tools.py`** — all changes are here

---

## Implementation Steps

### Step 1 (PRIMARY): Fix workspace path in `_run_git_in_workspace`

**Location:** `tools.py:2431-2432`

```python
# Replace:
host_workspace = os.path.join(TASK_VOLUME, task.id)
container_workspace = os.path.join(TASK_BASE_DIR, task.id)

# With:
workspace_dir_name = os.path.basename(task.workspace)
host_workspace = os.path.join(TASK_VOLUME, workspace_dir_name)
container_workspace = task.workspace
```

The volume mount argument at line 2438 stays the same syntactically:
```python
"-v", f"{host_workspace}:{container_workspace}",
```
— it just now uses the corrected values.

This also fixes the `git_status`, `git_push`, `git_diff`, and `git_log` tools for continuation tasks (they all go through `_run_git_in_workspace`).

### Step 2 (SECONDARY): Add `|| true` to `git fetch` in check command

**Location:** `tools.py` inside `_auto_push_branch`, the `check_cmd` string

```python
# Replace:
"git fetch origin 2>/dev/null; "

# With:
"git fetch origin 2>/dev/null || true; "
```

### Step 3 (SECONDARY): Allow `_auto_push_branch` to run on failed tasks

**Location:** `tools.py:1562`

```python
# Replace:
if task.auto_push and task.repo_url and task.status in ("completed", "awaiting_input"):

# With:
if task.auto_push and task.repo_url and task.status in ("completed", "awaiting_input", "failed"):
```

---

## Verification / Testing Plan

1. **Reproduce**: Create a task with `auto_push=True` and a repo URL. Let it complete (first run should push OK). Then give feedback via portal continue. Check `task.result["auto_push"]` on the continuation — currently shows `{"success": False, "error": ...}`.

2. **After Step 1 fix**: Repeat the same flow. The continuation task's `_auto_push_branch` should now mount the correct workspace (`abc123` directory, not `xyz789`). The check will find `UP_TO_DATE` (since Claude already pushed from inside the container) and skip. `task.result["auto_push"]` should show `{"success": True, "skipped": True, "reason": "already pushed by agent"}`.

3. **Confirm git tools work on continuation tasks**: Call `claude_code.git_status` with a continuation task's `task_id`. Currently fails with wrong workspace mount; after fix should return correct status.
