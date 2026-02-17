# claude_code

Coding tasks via Claude Code CLI running in Docker containers. Supports git operations, plan/execute modes, and workspace browsing.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `claude_code.run_task` | Submit a new coding task | admin |
| `claude_code.continue_task` | Resume task with follow-up prompt | admin |
| `claude_code.task_status` | Poll task status and result | admin |
| `claude_code.task_logs` | Read live/finished task logs | admin |
| `claude_code.cancel_task` | Kill a running task | admin |
| `claude_code.list_tasks` | List all tasks with statuses | admin |
| `claude_code.get_task_chain` | Get all tasks in a plan chain | admin |
| `claude_code.browse_workspace` | List files in task workspace | admin |
| `claude_code.read_workspace_file` | Read a file from workspace | admin |
| `claude_code.get_task_container` | Get container info for terminal access | admin |
| `claude_code.git_status` | Get git status of workspace | admin |
| `claude_code.git_push` | Push workspace branch to remote | admin |

## Tool Details

### `claude_code.run_task`
- **prompt** (string, required) — detailed coding task description
- **repo_url** (string, optional) — git repo to clone before starting
- **branch** (string, optional) — branch to checkout or create
- **source_branch** (string, optional) — base branch when creating a new branch
- **timeout** (integer, optional) — max seconds (default 1800)
- **mode** (string, optional) — `execute` (default) or `plan` (creates plan for review)
- Returns `{task_id, workspace_path}` immediately

### `claude_code.continue_task`
- **task_id** (string, required) — original task to continue
- **prompt** (string, required) — follow-up instructions
- **timeout** (integer, optional) — default 1800
- **mode** (string, optional) — set to `execute` to approve a plan
- Uses `--continue` flag for session context
- Returns new `task_id` for tracking

### `claude_code.task_status`
- **task_id** (string, required)
- Statuses: `queued`, `running`, `completed`, `failed`, `timed_out`, `awaiting_input`
- Returns `{status, workspace_path, elapsed_time, heartbeat, result}`

### `claude_code.task_logs`
- **task_id** (string, required)
- **tail** (integer, optional) — lines to return (default 100)
- **offset** (integer, optional) — start from line number for pagination

### `claude_code.cancel_task`
- **task_id** (string, required)
- Kills Docker container, marks as failed

### `claude_code.list_tasks`
- **status_filter** (string, optional) — `queued`/`running`/`completed`/`failed`/`timed_out`/`awaiting_input`

### `claude_code.get_task_chain`
- **task_id** (string, required) — any task in the chain
- Returns all tasks sorted chronologically (plan -> feedback -> implementation)

### `claude_code.browse_workspace`
- **task_id** (string, required)
- **path** (string, optional) — relative path within workspace
- Returns `{name, type, size, modified_time}` entries

### `claude_code.read_workspace_file`
- **task_id** (string, required)
- **path** (string, required) — relative file path

### `claude_code.git_status`
- **task_id** (string, required)
- Returns branch, tracking info, ahead/behind counts, staged/unstaged/untracked files, recent commits

### `claude_code.git_push`
- **task_id** (string, required)
- **remote** (string, optional) — default `origin`
- **branch** (string, optional) — defaults to current branch
- **force** (boolean, optional) — uses `--force-with-lease` (default false)

## Implementation Notes

- Workspaces live at `/tmp/claude_tasks/{task_id}/` and persist across continuations
- Plan mode creates `awaiting_input` status — use `continue_task` with `mode='execute'` to approve
- The workspace path is the contract with `deployer.deploy` — pass it directly as `project_path`
- Dockerfile installs Docker CLI for managing sibling containers via mounted Docker socket
- Task timeout defaults to 1800s (30 min) — avoid setting lower unless explicitly requested

## Interactive Terminal Access

The portal provides interactive terminal access to workspace containers via WebSocket. This allows developers to:
- Inspect workspace files directly with shell commands
- Run git operations (status, diff, log, push)
- Test code execution in the same environment Claude Code uses
- Debug issues by exploring the filesystem and running diagnostic commands
- Upload files via drag-and-drop interface

See [Portal Documentation](../portal.md#terminal) for terminal features and usage.

**Container Requirements:**
- Container must be in `running` status
- Container ID is retrieved via `get_task_container` tool
- Terminal creates Docker exec instances with `/bin/bash` and `tty=True`
- Working directory is set to the workspace path (`/tmp/claude_tasks/{task_id}/`)

## Workflow Integration

Typical build-then-deploy flow:
1. `claude_code.run_task` → get `task_id` and `workspace_path`
2. `scheduler.add_job` with `poll_module: claude_code.task_status`, `on_complete="resume_conversation"`
3. Scheduler polls until task completes
4. Agent loop resumes, calls `deployer.deploy(project_path=workspace_path)`

## Key Files

- `agent/modules/claude_code/manifest.py`
- `agent/modules/claude_code/tools.py`
- `agent/modules/claude_code/main.py`
