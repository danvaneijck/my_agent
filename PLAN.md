# Fix: Tasks Card Showing Stale "Awaiting Input" Tasks as Active

## Problem

The Tasks summary card on `HomePage.tsx` shows tasks with `awaiting_input` status as active, even when their task chain has moved on (i.e., the user already approved the plan and a continuation task was created). This happens because:

1. **`list_tasks` returns all tasks flat** — every task in a chain appears as a separate entry (`tools.py:472-485`). When a plan task finishes with `awaiting_input` and the user continues it, the original task keeps its `awaiting_input` status permanently. The new continuation task is a separate entry.

2. **The "Active Task" highlight picks stale tasks** — `HomePage.tsx:368-372` finds the first task with `running` or `awaiting_input` status, which could be an old plan task whose chain already has a newer `running` or `completed` continuation.

3. **Stats are inflated** — All chain siblings count separately, so a single logical task that went through plan → approve → execute shows as 3 separate entries.

## Root Cause

When `continue_task` creates a new child task (`tools.py:297-394`), the parent task's status is never updated. The parent stays `awaiting_input` forever. The only link between parent and child is `parent_task_id`, which points to the chain root.

## Solution: Filter to Latest Task Per Chain in `list_tasks`

The fix should be applied at the **backend** (`list_tasks` in `tools.py`) so the dashboard (and any other consumer) automatically gets the correct view. We add a `latest_per_chain` parameter that, when true, returns only the most recent task from each chain.

### Files to Modify

#### 1. `agent/modules/claude_code/tools.py` — `list_tasks` method (lines 472-485)

**Change:** Add a `latest_per_chain: bool = False` parameter. When `True`, group tasks by their chain root (using `parent_task_id or task.id`) and return only the latest task (by `created_at`) from each group.

```python
async def list_tasks(
    self, status_filter: str | None = None,
    latest_per_chain: bool = False,
    user_id: str | None = None,
) -> dict:
    """List tasks for the given user, optionally filtered by status."""
    if user_id:
        tasks = [t for t in self.tasks.values() if t.user_id == user_id]
    else:
        tasks = list(self.tasks.values())
    if status_filter:
        tasks = [t for t in tasks if t.status == status_filter]

    if latest_per_chain:
        # Group by chain root, keep only the most recent task per chain
        chains: dict[str, Task] = {}
        for t in tasks:
            chain_key = t.parent_task_id or t.id
            existing = chains.get(chain_key)
            if existing is None or t.created_at > existing.created_at:
                chains[chain_key] = t
        tasks = list(chains.values())

    return {
        "tasks": [t.to_dict() for t in tasks],
        "total": len(tasks),
    }
```

#### 2. `agent/modules/claude_code/manifest.py` — `list_tasks` tool definition

**Change:** Add `latest_per_chain` parameter to the manifest so the orchestrator knows about it.

Add this parameter to the `list_tasks` tool definition:
```python
ToolParameter(
    name="latest_per_chain",
    type="boolean",
    description="When true, return only the latest task from each task chain instead of all chain members.",
    required=False,
),
```

#### 3. `agent/modules/claude_code/main.py` — No changes needed

The execute handler already uses `**args` to forward all arguments to `list_tasks` (line 96: `result = await tools.list_tasks(**args)`). Adding the new parameter to `tools.py` and `manifest.py` is sufficient — `main.py` will pass it through automatically.

#### 4. `agent/portal/routers/tasks.py` — `list_tasks` endpoint (lines 69-85)

**Change:** Add `latest_per_chain` query parameter (default `True` for the portal, since the dashboard always wants the latest view).

```python
@router.get("")
async def list_tasks(
    status: str | None = Query(None, alias="status"),
    latest_per_chain: bool = Query(True),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List all Claude Code tasks, optionally filtered by status."""
    args: dict = {}
    if status:
        args["status_filter"] = status
    if latest_per_chain:
        args["latest_per_chain"] = True
    result = await call_tool(
        module="claude_code",
        tool_name="claude_code.list_tasks",
        arguments=args,
        user_id=str(user.user_id),
        timeout=15.0,
    )
    return result.get("result", {})
```

Note: defaulting to `True` for the portal endpoint means the dashboard and task list pages automatically get deduplicated results. The underlying module tool defaults to `False` for backward compatibility with the orchestrator/bot callers.

#### 5. `agent/portal/frontend/src/pages/HomePage.tsx` — No changes needed

The frontend code is already correct in its logic — it finds the first `running` or `awaiting_input` task for the "Active Task" highlight, and shows stats/list from the tasks array. Once the backend returns only the latest task per chain, this logic naturally shows the correct state:

- If a chain's latest task is `running`, it shows as running
- If a chain's latest task is `awaiting_input` (no continuation yet), it shows as awaiting input
- If a chain's latest task is `completed`, it shows as completed (the old `awaiting_input` parent is hidden)

No frontend changes are required.

### Why Backend Over Frontend

Filtering at the backend is preferred because:

1. **Single source of truth** — All consumers (dashboard, task list page, API clients) get consistent data
2. **Less data over the wire** — Don't send redundant chain siblings to the frontend
3. **Simpler frontend** — No need to implement chain deduplication logic in JavaScript
4. **The chain endpoint still exists** — `GET /api/tasks/{task_id}/chain` still returns all chain members when you need the full history (e.g., TaskChainViewer component)

### Testing Approach

1. Create a task in `plan` mode → it finishes with `awaiting_input`
2. Continue the task (approve plan) → new child task is created
3. Call `GET /api/tasks` → verify only the latest child task appears, not the stale `awaiting_input` parent
4. Call `GET /api/tasks?latest_per_chain=false` → verify all tasks still appear (backward compat)
5. Verify the "Active Task" highlight on the dashboard shows the correct current task
6. Verify the TaskChainViewer still works (it uses `/api/tasks/{id}/chain`, not `list_tasks`)

### Edge Cases

- **Standalone tasks (no chain)**: These have `parent_task_id = None`, so their chain key is their own `id`. They appear as their own group with one member — no behavior change.
- **Multiple active chains**: Each chain is independent. If chain A has a running task and chain B has a completed task, both latest tasks appear.
- **Status filter + latest_per_chain**: Status filter is applied first, then chain deduplication. This means if you filter by `status=awaiting_input` with `latest_per_chain=true`, you only see `awaiting_input` tasks that are genuinely the latest in their chain (i.e., no continuation has been created yet).
