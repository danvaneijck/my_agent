# Implementation Plan: Persistent Workspace Access After Task Completion

## Problem Statement

**Current Issue:** Users can only access workspace files through the code terminal when a Claude Code task is actively running. Once a task completes, the Docker container is automatically removed, making files inaccessible via the terminal.

### Current Behavior
1. Task starts → Container created with `docker run --rm ...`
2. Task executes → Container running, terminal access works
3. Task completes → Container exits and is **immediately removed** (due to `--rm` flag)
4. Files inaccessible → Terminal shows "Container not found" error

### User Impact
- **Cannot inspect generated code** after task completion
- **Cannot run git operations** to review changes (diff, log, status)
- **Cannot test or debug** code that was written
- **Cannot run follow-up commands** (npm install, pytest, etc.)
- **Forced to use file browser only** which lacks command-line functionality

### Root Cause

**Location:** `agent/modules/claude_code/tools.py`

The container lifecycle in `_run_single_container()` (lines 1178-1401):

```python
async def _run_single_container(task, timeout, prompt, user_mounts):
    cmd = ["docker", "run", "--rm", ...]  # Line 1506: --rm auto-removes container
    # ... container runs ...
    finally:
        await self._remove_container(container_name)  # Line 1400: explicit removal
```

**Key Issue:** Both `--rm` flag AND explicit `_remove_container()` ensure the container is destroyed on exit, regardless of success/failure status.

## Proposed Solution: On-Demand Terminal Containers

Instead of keeping task execution containers running, create **lightweight persistent containers** specifically for terminal access after task completion.

### Design Principles

1. **Separation of Concerns**: Task containers (ephemeral) vs. Terminal containers (persistent)
2. **On-Demand Creation**: Only create when user requests terminal access
3. **Resource Efficiency**: Minimal footprint, automatic cleanup
4. **Seamless UX**: Transparent to users - terminal "just works"
5. **Workspace Preservation**: Both containers share same workspace volume

## Architecture

### Container Types

#### Task Execution Containers
- **Purpose:** Run Claude Code CLI for task execution
- **Lifecycle:** Created on `run_task` → Removed on completion
- **Name:** `claude-task-{task_id}-{continuation_count}`
- **Image:** Full Claude Code image with all tools
- **Duration:** Minutes to hours (until task completes)

#### Terminal Access Containers
- **Purpose:** Provide shell access to completed workspaces
- **Lifecycle:** Created on first terminal access → Removed after 24h idle
- **Name:** `claude-terminal-{task_id}`
- **Image:** Lightweight Alpine + bash + git
- **Duration:** Up to 24 hours (idle timeout)

### Lifecycle Flow

```
Task Created
    ↓
Task Container Running (claude-task-{id}-0)
    ↓ task completes
Task Container Removed (--rm)
    ↓ workspace files persist on host
User Opens Terminal
    ↓
Check: Does terminal container exist?
    ├─ Yes, running → Use it
    ├─ Yes, stopped → Remove and recreate
    └─ No → Create new terminal container
         ↓
Terminal Container Running (claude-terminal-{id})
    ↓ user works in terminal
24 hours of inactivity
    ↓
Cleanup Job Removes Container
```

## Implementation Plan

### Phase 1: Backend - Terminal Container Management

#### Task 1.1: Add Terminal Container Creation Tool

**Files:**
- `agent/modules/claude_code/manifest.py`
- `agent/modules/claude_code/tools.py`

**Changes:**

**manifest.py** - Add tool definition:
```python
ToolDefinition(
    name="claude_code.create_terminal_container",
    description="Create or get a persistent terminal container for workspace access",
    parameters=[
        ToolParameter(name="task_id", type="string", required=True),
    ],
    required_permission="admin",
)
```

**tools.py** - Add method to `ClaudeCodeTools`:
```python
async def create_terminal_container(
    self, task_id: str, user_id: str | None = None
) -> dict:
    """Create or get a persistent terminal container for workspace access.

    Container specifications:
    - Image: alpine:latest with bash and git
    - Command: tail -f /dev/null (keeps container running)
    - Name: claude-terminal-{task_id}
    - Volume: Same workspace mount as task container
    - Working dir: Task workspace path
    - Labels: user_id, task_id, type=terminal, created_at

    Returns:
        {
            "container_id": str,
            "container_name": str,
            "workspace": str,
            "status": "created" | "existing" | "restarted"
        }
    """
```

**Implementation Steps:**
1. Validate task exists and user has access (`_get_task()`)
2. Check if terminal container already exists:
   ```python
   container_name = f"claude-terminal-{task_id}"
   proc = await asyncio.create_subprocess_exec(
       "docker", "ps", "-a", "-q", "-f", f"name={container_name}",
       stdout=asyncio.subprocess.PIPE
   )
   ```
3. If exists and running → return existing info
4. If exists and stopped → remove then create new
5. If not exists → create new container
6. Return container metadata

**Container Creation Command:**
```python
cmd = [
    "docker", "run", "-d",  # Detached, NOT --rm
    "--name", f"claude-terminal-{task_id}",
    "-v", f"{TASK_VOLUME}:{TASK_BASE_DIR}",
    "-w", task.workspace,
    "-e", "TERM=xterm-256color",
    "--label", f"user_id={user_id}",
    "--label", f"task_id={task_id}",
    "--label", "type=terminal",
    "--label", f"created_at={int(time.time())}",
    "alpine:latest",
    "sh", "-c", "apk add --no-cache bash git && tail -f /dev/null"
]
```

**Acceptance Criteria:**
- [ ] Creates Alpine container with bash and git
- [ ] Mounts workspace volume correctly
- [ ] Sets working directory to task workspace
- [ ] Returns container ID and status
- [ ] Idempotent - returns existing if already created
- [ ] Validates user owns the task

---

#### Task 1.2: Add Container Lifecycle Management Tools

**File:** `agent/modules/claude_code/tools.py`

**Add methods:**

```python
async def stop_terminal_container(
    self, task_id: str, user_id: str | None = None
) -> dict:
    """Stop and remove a terminal container.

    Returns:
        {
            "task_id": str,
            "container_name": str,
            "removed": bool,
            "message": str
        }
    """
```

```python
async def list_terminal_containers(
    self, user_id: str | None = None
) -> dict:
    """List all terminal containers for a user.

    Returns:
        {
            "containers": [
                {
                    "task_id": str,
                    "container_id": str,
                    "container_name": str,
                    "workspace": str,
                    "status": str,
                    "created_at": int,
                    "idle_time_seconds": int
                }
            ],
            "total": int
        }
    """
```

**Acceptance Criteria:**
- [ ] `stop_terminal_container` removes container and cleans up
- [ ] `list_terminal_containers` filters by user_id
- [ ] Both handle non-existent containers gracefully
- [ ] Proper error messages for failures

---

#### Task 1.3: Add Manifest Entries

**File:** `agent/modules/claude_code/manifest.py`

Add to `MANIFEST.tools` list:

```python
ToolDefinition(
    name="claude_code.stop_terminal_container",
    description="Stop and remove a terminal container",
    parameters=[
        ToolParameter(name="task_id", type="string", required=True),
    ],
    required_permission="admin",
),
ToolDefinition(
    name="claude_code.list_terminal_containers",
    description="List all terminal containers for the current user",
    parameters=[],
    required_permission="admin",
),
```

---

#### Task 1.4: Add Automatic Cleanup

**File:** `agent/modules/claude_code/tools.py`

Add cleanup method:

```python
async def cleanup_idle_terminal_containers(self) -> dict:
    """Remove terminal containers idle for >24 hours.

    Cleanup criteria:
    - Container has label type=terminal
    - Created >24 hours ago OR last_activity >24 hours ago
    - Not currently attached to any terminal session

    Returns:
        {
            "removed": [container_names],
            "count": int,
            "errors": [error_messages]
        }
    """
```

**Implementation:**
1. List all containers with label `type=terminal`
2. For each container:
   - Inspect labels to get `created_at` timestamp
   - Check if container has been running >24 hours
   - Check if any active terminal sessions exist (via portal terminal_service)
   - If idle criteria met → remove container
3. Return summary of removed containers

**File:** `agent/modules/claude_code/main.py`

Add background cleanup loop:

```python
@app.on_event("startup")
async def startup():
    global tools
    tools = ClaudeCodeTools()
    # Start cleanup loop
    asyncio.create_task(cleanup_loop())

async def cleanup_loop():
    """Run terminal container cleanup every hour."""
    while True:
        try:
            await asyncio.sleep(3600)  # 1 hour
            result = await tools.cleanup_idle_terminal_containers()
            if result["count"] > 0:
                logger.info(
                    "terminal_cleanup_completed",
                    removed=result["count"],
                    containers=result["removed"]
                )
        except Exception as e:
            logger.error("cleanup_loop_error", error=str(e))
```

**Acceptance Criteria:**
- [ ] Cleanup runs every hour in background
- [ ] Removes containers idle >24 hours
- [ ] Logs removal actions
- [ ] Handles Docker API errors gracefully
- [ ] Does not remove containers with active sessions

---

### Phase 2: Portal Integration

#### Task 2.1: Update Terminal Service

**File:** `agent/portal/services/terminal_service.py`

**Add method:**

```python
async def ensure_terminal_container(
    self, task_id: str, user_id: str
) -> str:
    """Ensure a terminal container exists for the task.

    Workflow:
    1. Try to get task container (if task still running)
    2. If task container exists and running → return its ID
    3. Otherwise, call claude_code.create_terminal_container
    4. Return terminal container ID

    Args:
        task_id: Task ID
        user_id: User ID for ownership validation

    Returns:
        container_id: Docker container ID

    Raises:
        ValueError: If workspace not found or access denied
    """
    # First, try to get running task container
    try:
        from portal.services.module_client import call_tool

        result = await call_tool(
            module="claude_code",
            tool_name="claude_code.get_task_container",
            arguments={"task_id": task_id},
            user_id=user_id,
        )
        container_info = result.get("result", {})

        # If task container is running, use it
        if container_info.get("status") == "running":
            return container_info["container_id"]

    except Exception:
        # Task container not available, continue to terminal container
        pass

    # Create or get terminal container
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.create_terminal_container",
        arguments={"task_id": task_id},
        user_id=user_id,
    )

    terminal_info = result.get("result", {})
    if not terminal_info.get("container_id"):
        raise ValueError(
            "Failed to create terminal container. "
            "The workspace may have been deleted."
        )

    return terminal_info["container_id"]
```

**Update `get_container()` method:**

```python
def get_container(self, container_id: str) -> Container:
    """Get a Docker container by ID or name.

    Now handles both task and terminal containers.
    """
    try:
        container = self.docker_client.containers.get(container_id)
        # Refresh container status
        container.reload()

        if container.status != "running":
            raise ValueError(
                f"Container exists but is {container.status}. "
                f"It may need to be restarted."
            )

        return container
    except docker.errors.NotFound:
        raise ValueError(
            "Container not found. The workspace may have been deleted or "
            "the container may have been removed."
        )
    except docker.errors.APIError as e:
        raise ValueError(f"Docker API error: {e}")
```

**Acceptance Criteria:**
- [ ] `ensure_terminal_container` prefers task container if running
- [ ] Falls back to terminal container if task completed
- [ ] Creates terminal container on first access
- [ ] Returns valid container ID
- [ ] Handles all error cases with clear messages

---

#### Task 2.2: Update WebSocket Endpoint

**File:** `agent/portal/routers/tasks.py`

**Modify `terminal_ws` endpoint (around line 250):**

```python
@router.websocket("/{task_id}/terminal/ws")
async def terminal_ws(
    websocket: WebSocket,
    task_id: str,
    session_id: str = Query(...),
    token: str = Query(...),
):
    """WebSocket endpoint for interactive terminal access.

    Now supports both task and terminal containers automatically.
    """
    user = await verify_ws_auth(token)
    await websocket.accept()

    logger.info(
        "terminal_ws_connection_attempt",
        task_id=task_id,
        session_id=session_id,
        user_id=str(user.user_id)
    )

    try:
        terminal_service = get_terminal_service()

        # CHANGE: Ensure container exists (task or terminal)
        try:
            container_id = await terminal_service.ensure_terminal_container(
                task_id, str(user.user_id)
            )
        except Exception as e:
            logger.error(
                "terminal_container_ensure_failed",
                task_id=task_id,
                error=str(e)
            )
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
            return

        logger.info(
            "terminal_container_ready",
            task_id=task_id,
            container_id=container_id
        )

        # Rest of existing logic unchanged...
        session = await terminal_service.create_session(
            session_id=session_id,
            container_id=container_id,
            user_id=str(user.user_id),
            task_id=task_id,
        )
        # ... existing WebSocket handling ...
```

**Acceptance Criteria:**
- [ ] WebSocket connects successfully for running tasks
- [ ] WebSocket connects successfully for completed tasks
- [ ] Error messages are user-friendly
- [ ] Container creation logged for debugging

---

#### Task 2.3: Add Container Management REST Endpoints

**File:** `agent/portal/routers/tasks.py`

**Add new endpoints:**

```python
@router.post("/{task_id}/terminal/container")
async def create_terminal_container_endpoint(
    task_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Explicitly create a terminal container for a task.

    Useful for pre-warming container before opening terminal.
    """
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.create_terminal_container",
        arguments={"task_id": task_id},
        user_id=str(user.user_id),
    )
    return result.get("result", {})


@router.delete("/{task_id}/terminal/container")
async def stop_terminal_container_endpoint(
    task_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Stop and remove a terminal container."""
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.stop_terminal_container",
        arguments={"task_id": task_id},
        user_id=str(user.user_id),
    )
    return result.get("result", {})


@router.get("/terminal/containers")
async def list_terminal_containers_endpoint(
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List all terminal containers for the current user."""
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.list_terminal_containers",
        arguments={},
        user_id=str(user.user_id),
    )
    return result.get("result", {})
```

**Acceptance Criteria:**
- [ ] POST creates/gets container
- [ ] DELETE removes container
- [ ] GET lists user's containers
- [ ] All require authentication
- [ ] Return proper HTTP status codes

---

### Phase 3: Frontend Updates (Optional Enhancements)

#### Task 3.1: Add Terminal Status Indicator

**File:** `agent/portal/frontend/src/components/tasks/WorkspaceBrowser.tsx`

**Add state for container status:**

```tsx
const [containerStatus, setContainerStatus] = useState<{
  type: "task" | "terminal" | "none";
  status: "running" | "creating" | "error";
} | null>(null);

// Check on mount
useEffect(() => {
  // Container info fetched automatically by terminal
  // This is just for UI indication
}, [taskId]);
```

**Add UI indicator in header:**

```tsx
<div className="flex items-center gap-2">
  {containerStatus?.type === "terminal" && (
    <span className="text-xs text-yellow-400">
      Using persistent container
    </span>
  )}
  <button onClick={() => setShowTerminal(!showTerminal)}>
    Terminal
  </button>
</div>
```

**Acceptance Criteria:**
- [ ] Shows "Using persistent container" for terminal containers
- [ ] Shows nothing for task containers (default case)
- [ ] Updates when container type changes

---

#### Task 3.2: Improve Terminal Connection UX

**File:** `agent/portal/frontend/src/components/code/TerminalView.tsx`

**Update connection handling:**

```tsx
ws.onmessage = (event) => {
  const message = JSON.parse(event.data);

  if (message.type === "ready") {
    setStatus("connected");
    term.writeln("✓ Connected to workspace terminal");
    term.writeln("Tip: This terminal persists even after tasks complete");
    term.writeln("");
  }
  // ... rest of message handling
};

ws.onerror = (event) => {
  setStatus("error");
  const errorMsg =
    "Terminal container is starting. Please wait a moment and try reconnecting.";
  setErrorMessage(errorMsg);
};
```

**Acceptance Criteria:**
- [ ] Shows helpful message on connection
- [ ] Explains persistence behavior
- [ ] Clear error for container startup delays

---

### Phase 4: Documentation

#### Task 4.1: Update Module Documentation

**File:** `agent/docs/modules/claude_code.md`

**Add section after "Interactive Terminal Access":**

```markdown
### Terminal Container Persistence

Terminal access remains available even after tasks complete:

**Container Lifecycle:**
- **Task Running**: Terminal connects to task execution container
- **Task Completed**: Terminal auto-creates persistent container
- **Idle Timeout**: Containers removed after 24 hours of inactivity

**Terminal Containers:**
- Lightweight Alpine Linux with bash and git
- Same workspace volume as task container
- Automatic creation on first terminal access
- Removed during cleanup (every hour) if idle >24h

**New Tools:**
- `claude_code.create_terminal_container` - Create/get terminal container
- `claude_code.stop_terminal_container` - Remove terminal container
- `claude_code.list_terminal_containers` - List user's terminal containers

See [Portal Documentation](../portal.md#persistent-workspace-access) for user guide.
```

---

#### Task 4.2: Update Portal Documentation

**File:** `agent/docs/portal.md`

**Add section after "Terminal" section:**

```markdown
### Persistent Workspace Access

Workspaces remain accessible via terminal even after Claude Code tasks complete.

**How It Works:**

1. During task execution → terminal connects to task container
2. After task completes → task container is removed (saves resources)
3. User opens terminal → lightweight container auto-created
4. User can run commands, inspect files, perform git operations
5. Container persists for 24 hours of inactivity
6. Automatic cleanup removes idle containers

**Use Cases:**

- Review generated code with `cat`, `less`, etc.
- Run git operations: `git status`, `git diff`, `git log`
- Test code: `npm install`, `pytest`, `go run`
- Debug issues: inspect logs, check configurations
- Make quick edits with `vim` or `nano`

**Resource Management:**

- Terminal containers use minimal resources (~5MB Alpine Linux)
- Maximum 10 terminal containers per user
- Auto-cleanup every hour removes idle containers (>24h)
- Manual cleanup: DELETE `/api/tasks/{id}/terminal/container`

**Container Specifications:**

- **Image**: alpine:latest
- **Installed**: bash, git
- **Volume**: Same workspace as task
- **Working dir**: Task workspace path
- **Network**: Isolated (no internet access)
```

---

### Phase 5: Testing

#### Task 5.1: Unit Tests

**File:** `agent/modules/claude_code/test_terminal_containers.py` (new)

```python
import pytest
from modules.claude_code.tools import ClaudeCodeTools

@pytest.mark.asyncio
async def test_create_terminal_container_new():
    """Creating new terminal container succeeds."""

@pytest.mark.asyncio
async def test_create_terminal_container_existing():
    """Getting existing terminal container returns same ID."""

@pytest.mark.asyncio
async def test_stop_terminal_container():
    """Stopping terminal container removes it."""

@pytest.mark.asyncio
async def test_list_terminal_containers_filters_by_user():
    """List only shows user's own containers."""

@pytest.mark.asyncio
async def test_cleanup_idle_containers():
    """Cleanup removes containers idle >24 hours."""
```

---

#### Task 5.2: Integration Tests

**File:** `agent/portal/tests/test_terminal_persistence.py` (new)

```python
@pytest.mark.asyncio
async def test_terminal_access_after_task_completion():
    """Terminal works on completed tasks via persistent container."""

@pytest.mark.asyncio
async def test_terminal_container_auto_creation():
    """Opening terminal auto-creates container if needed."""

@pytest.mark.asyncio
async def test_terminal_container_reuse():
    """Second terminal connection reuses existing container."""
```

---

#### Task 5.3: Manual Testing Checklist

- [ ] Start task, let it complete, verify container removed
- [ ] Open terminal on completed task, verify new container created
- [ ] Run commands in terminal (ls, git status, etc.)
- [ ] Close and reopen terminal, verify same container reused
- [ ] Check container list shows terminal container
- [ ] Wait 24+ hours (or adjust timeout for testing), verify cleanup
- [ ] Check resource usage (should be minimal)
- [ ] Test with multiple concurrent terminal containers
- [ ] Test error cases (deleted workspace, invalid task_id)

---

## Files Modified/Created

### New Files
1. `agent/modules/claude_code/test_terminal_containers.py`
2. `agent/portal/tests/test_terminal_persistence.py`

### Modified Files
1. `agent/modules/claude_code/manifest.py` - Add 3 new tool definitions
2. `agent/modules/claude_code/tools.py` - Add 4 new methods
3. `agent/modules/claude_code/main.py` - Add cleanup background task
4. `agent/portal/services/terminal_service.py` - Add `ensure_terminal_container()`
5. `agent/portal/routers/tasks.py` - Update WebSocket + add 3 REST endpoints
6. `agent/portal/frontend/src/components/tasks/WorkspaceBrowser.tsx` - Add status indicator
7. `agent/portal/frontend/src/components/code/TerminalView.tsx` - Update messages
8. `agent/docs/modules/claude_code.md` - Document terminal containers
9. `agent/docs/portal.md` - Add persistence section

## Resource Considerations

### Container Resources
- **Task Container**: Short-lived, full Claude Code image (~500MB), high CPU during execution
- **Terminal Container**: Long-lived (max 24h), Alpine image (~5MB), idle CPU/memory

### Scaling Limits
- Max terminal containers per user: 10
- Max idle time: 24 hours
- System-wide limit: 100 containers (10 users × 10 containers)

### Expected Impact
- 100 containers × 5MB = ~500MB total disk space
- Minimal CPU/memory when idle
- Cleanup runs hourly to prevent accumulation

## Security Considerations

- Terminal containers run with same isolation as task containers
- User can only access their own workspaces (user_id validation)
- No privileged mode or network access
- Container labels enforce ownership tracking
- Portal auth required for all operations

## Success Criteria

### Functional
- ✅ Terminal works on completed tasks
- ✅ Files accessible and modifiable
- ✅ Git operations work correctly
- ✅ Automatic cleanup maintains system health

### Performance
- Container creation: <3 seconds
- Terminal connection: <1 second after container ready
- Resource overhead: <100MB per container

### User Experience
- Seamless transition (user doesn't notice container type)
- Clear error messages
- No manual intervention required

## Rollout Plan

1. **Week 1**: Implement backend (Phase 1)
   - Add terminal container tools to claude_code module
   - Add cleanup background task
   - Write unit tests

2. **Week 1-2**: Portal integration (Phase 2)
   - Update terminal service
   - Modify WebSocket endpoint
   - Add REST endpoints
   - Write integration tests

3. **Week 2**: Frontend polish (Phase 3)
   - Add status indicators
   - Improve messaging
   - User testing

4. **Week 2**: Documentation and deployment (Phase 4-5)
   - Update all docs
   - Final testing
   - Deploy to production

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Resource exhaustion | Per-user limit (10), idle timeout (24h), system cap (100) |
| Orphaned containers | Automatic cleanup loop + Docker labels |
| Breaking existing terminals | Graceful fallback (task container first) |
| Container startup delays | Clear loading messages, retry logic |

## Alternatives Considered

### Alternative 1: Remove `--rm`, keep task containers
**Rejected** - Wastes resources, full containers remain running indefinitely

### Alternative 2: File browser only
**Rejected** - Poor UX, no command-line tools, no git operations

### Alternative 3: Single shared terminal per user
**Rejected** - Complex workspace switching, session isolation issues

## Conclusion

This solution provides persistent workspace access through lightweight on-demand containers while maintaining resource efficiency. Users get seamless terminal access regardless of task status, with automatic lifecycle management preventing resource waste.

**Timeline**: 2 weeks
**Risk**: Low
**Impact**: High - dramatically improves developer experience
