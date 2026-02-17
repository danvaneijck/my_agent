# Task Chain Terminal Working Directory Fix

## Problem

When using the terminal feature with task chains, the terminal would open in an empty directory instead of the actual workspace. This occurred because:

1. In task chains, the workspace directory is named after the **first task** in the chain (e.g., `/tmp/claude_tasks/{first_task_id}`)
2. The terminal code was constructing the working directory path using the **current task ID** (e.g., `/tmp/claude_tasks/{current_task_id}`)
3. This mismatch caused the terminal to try to access a non-existent directory

## Root Cause

The `claude_code` module reuses workspace directories for task chains:
- Task A creates workspace: `/tmp/claude_tasks/abc123/`
- Task B (continues from A) uses same workspace: `/tmp/claude_tasks/abc123/`
- But Task B's ID is `def456`

The terminal service was using: `/tmp/claude_tasks/def456/` ❌
Should have been using: `/tmp/claude_tasks/abc123/` ✅

## Solution

### 1. Added workspace mount to portal service
**File**: `agent/docker-compose.yml`

Added the same volume mount that `claude-code` service uses:
```yaml
volumes:
  - /var/run/docker.sock:/var/run/docker.sock
  - ./data/claude_tasks:/tmp/claude_tasks  # Added this line
```

This gives the portal service direct access to workspace directories at the same path structure as task containers.

### 2. Use actual workspace path instead of constructing from task_id
**File**: `agent/portal/routers/tasks.py` (line 475)

Changed from:
```python
working_dir=f"/tmp/claude_tasks/{task_id}",  # ❌ Wrong for task chains
```

To:
```python
working_dir=workspace,  # ✅ Uses actual workspace path from get_task_container
```

The `workspace` variable comes from `get_task_container` and contains the correct path even in task chains.

### 3. Mount entire /tmp/claude_tasks directory in terminal containers
**File**: `agent/portal/services/terminal_service.py` (lines 414-420)

Changed from:
```python
working_dir=f"/tmp/claude_tasks/{task_id}",  # ❌ Constructed path
volumes={
    workspace_path: {
        "bind": f"/tmp/claude_tasks/{task_id}",  # ❌ Single workspace mount
        "mode": "rw",
    }
}
```

To:
```python
working_dir=workspace_path,  # ✅ Actual workspace path
volumes={
    "/tmp/claude_tasks": {
        "bind": "/tmp/claude_tasks",  # ✅ Mount entire directory
        "mode": "rw",
    }
}
```

This matches how `claude-code` task containers are configured - they mount the entire `/tmp/claude_tasks` directory and can access any workspace within it.

## How It Works Now

1. **get_task_container** returns the workspace path: `/tmp/claude_tasks/abc123/`
2. **Portal service** has access to this path via the volume mount
3. **Terminal container** is created with:
   - Mount: `/tmp/claude_tasks:/tmp/claude_tasks` (entire directory)
   - Working dir: `/tmp/claude_tasks/abc123/` (actual workspace)
4. **Result**: Terminal opens in the correct workspace directory, even in task chains

## Testing

To verify the fix works:

1. Create a task (Task A)
2. Create a continuation task (Task B) that references Task A
3. Open terminal for Task B
4. Run `ls` and `pwd` - should show the workspace files and correct path
5. Files from Task A should be visible in Task B's terminal

## Deployment Note

For this fix to work in production, the portal service must be restarted after the docker-compose.yml change to mount the workspace volume.

```bash
cd agent
docker compose restart portal
```
