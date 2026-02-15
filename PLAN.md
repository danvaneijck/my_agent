# Implementation Plan: Claude Code Task Management Improvements

## Task Overview
Improve the claude_code task management system by:
1. Enforcing a maximum of 10 workspaces per user
2. Adding a "delete all" button for cleaning up tasks

## Current Architecture Analysis

### Key Files
- `agent/modules/claude_code/tools.py` (lines 247-1730) - Core task management logic
- `agent/modules/claude_code/manifest.py` (lines 1-325) - Tool definitions
- `agent/modules/claude_code/main.py` (lines 1-123) - FastAPI service endpoint
- `agent/dashboard/main.py` (lines 1-748) - Admin dashboard API
- `agent/dashboard/static/index.html` - Dashboard UI (no claude_code tasks display currently)

### Current State
1. **Task Storage**: Tasks are stored in-memory in `ClaudeCodeTools.tasks` dict and persisted to disk as JSON metadata files
2. **Workspace Management**:
   - Each task gets a unique workspace directory under `/tmp/claude_tasks/<task_id>`
   - Tasks can be chained (sharing the same workspace via `parent_task_id`)
   - `delete_workspace()` method exists (line 596) but is NOT exposed as a public tool
3. **User Isolation**: Tasks include `user_id` field for ownership tracking
4. **List Tasks Tool**: `list_tasks()` method (line 567) supports filtering by user and status

### Missing Features
1. **No workspace limit per user** - users can create unlimited workspaces
2. **No bulk delete functionality** - can only delete one workspace at a time
3. **delete_workspace tool not exposed** in manifest.py - it exists but isn't callable via the agent
4. **No UI for claude_code tasks** in the dashboard

## Implementation Plan

### Step 1: Add Workspace Limit Enforcement

**File**: `agent/modules/claude_code/tools.py`

**Changes**:
1. Add a constant `MAX_WORKSPACES_PER_USER = 10` at the top of the file (around line 42)
2. Create a new helper method `_count_user_workspaces(user_id: str) -> int`:
   - Count unique workspaces owned by the user
   - Consider task chains (multiple tasks sharing same workspace count as 1)
   - Use the chain root logic (line 583-589) to count unique workspace chains

3. Modify `run_task()` method (line 327):
   - Before creating a new workspace, check workspace count for the user
   - If count >= MAX_WORKSPACES_PER_USER, raise a clear error:
     ```python
     "Workspace limit reached. You have 10 active workspaces. Please delete old workspaces using claude_code.delete_workspace or claude_code.delete_all_workspaces before creating new ones."
     ```
   - Note: `continue_task()` reuses existing workspace, so no check needed there

### Step 2: Add Bulk Delete Functionality

**File**: `agent/modules/claude_code/tools.py`

**Changes**:
1. Create new method `delete_all_workspaces(user_id: str | None = None) -> dict`:
   - Get all tasks for the user
   - Group by workspace (using chain root logic to avoid duplicates)
   - Cancel any running/queued tasks first
   - Delete each unique workspace directory
   - Remove all associated tasks from memory
   - Return summary with count of deleted workspaces and tasks

2. Implementation approach:
   ```python
   async def delete_all_workspaces(self, user_id: str | None = None) -> dict:
       """Delete all workspaces and tasks for a user."""
       if not user_id:
           raise ValueError("user_id is required for safety")

       # Get all user tasks
       user_tasks = [t for t in self.tasks.values() if t.user_id == user_id]

       # Group by workspace
       workspaces = {}
       for task in user_tasks:
           chain_root = task.parent_task_id or task.id
           if chain_root not in workspaces:
               workspaces[chain_root] = {
                   'workspace': task.workspace,
                   'task_ids': []
               }
           workspaces[chain_root]['task_ids'].append(task.id)

       # Delete each workspace
       deleted_workspaces = 0
       deleted_tasks = 0
       for chain_root, info in workspaces.items():
           # Cancel running tasks
           for tid in info['task_ids']:
               t = self.tasks.get(tid)
               if t and t.status in ("queued", "running"):
                   # Cancel logic from delete_workspace

           # Delete workspace directory
           if os.path.isdir(info['workspace']):
               shutil.rmtree(info['workspace'], ignore_errors=True)
               deleted_workspaces += 1

           # Remove from memory
           for tid in info['task_ids']:
               self.tasks.pop(tid, None)
               deleted_tasks += 1

       return {
           "deleted_workspaces": deleted_workspaces,
           "deleted_tasks": deleted_tasks,
           "message": f"Deleted {deleted_workspaces} workspace(s) and {deleted_tasks} task(s)"
       }
   ```

### Step 3: Expose Tools in Manifest

**File**: `agent/modules/claude_code/manifest.py`

**Changes**:
1. Add `delete_workspace` tool definition (currently missing from manifest):
   ```python
   ToolDefinition(
       name="claude_code.delete_workspace",
       description=(
           "Delete a task's workspace directory and remove all tasks in the chain. "
           "This permanently removes all files in the workspace. "
           "Use this to clean up completed or failed tasks."
       ),
       parameters=[
           ToolParameter(
               name="task_id",
               type="string",
               description="The task ID whose workspace to delete.",
               required=True,
           ),
       ],
       required_permission="admin",
   )
   ```

2. Add `delete_all_workspaces` tool definition:
   ```python
   ToolDefinition(
       name="claude_code.delete_all_workspaces",
       description=(
           "Delete ALL workspaces and tasks for the current user. "
           "This is a bulk cleanup operation that permanently removes all files "
           "from all your claude_code workspaces. Use with caution."
       ),
       parameters=[],  # user_id is injected automatically
       required_permission="admin",
   )
   ```

### Step 4: Wire Up Endpoints

**File**: `agent/modules/claude_code/main.py`

**Changes**:
1. Add handler in `execute()` function (around line 99):
   ```python
   elif tool_name == "delete_all_workspaces":
       result = await tools.delete_all_workspaces(**args)
   ```

2. Ensure `delete_workspace` is already wired (check line 99) - if missing, add it

### Step 5: Update Dashboard API (Optional - for future UI)

**File**: `agent/dashboard/main.py`

**Changes** (optional, for future enhancement):
1. Add new endpoint to fetch claude_code tasks from the module:
   ```python
   @app.get("/api/claude-tasks")
   async def claude_tasks_list():
       """Fetch claude_code tasks from the module service."""
       import httpx
       try:
           async with httpx.AsyncClient(timeout=10.0) as client:
               # Call claude_code module's list_tasks endpoint
               resp = await client.post(
                   f"{settings.module_services['claude_code']}/execute",
                   json={
                       "tool_name": "claude_code.list_tasks",
                       "arguments": {},
                       "user_id": None  # Or from auth context
                   }
               )
               if resp.status_code == 200:
                   data = resp.json()
                   return data.get("result", {}).get("tasks", [])
               return []
       except Exception as e:
           logger.error("claude_tasks_fetch_failed", error=str(e))
           return []
   ```

2. Add delete endpoints for UI buttons (future enhancement)

### Step 6: Testing Plan

**Manual Tests**:
1. **Workspace Limit Test**:
   - Create 10 claude_code tasks as a user
   - Verify 11th task fails with clear error message
   - Delete one workspace
   - Verify can now create a new task

2. **Delete All Test**:
   - Create multiple tasks with different workspaces
   - Call `delete_all_workspaces`
   - Verify all workspaces deleted
   - Verify task count shows 0

3. **Chain Handling Test**:
   - Create a task chain (original + 2 continuations)
   - Verify counted as 1 workspace toward limit
   - Delete workspace via chain member
   - Verify all chain tasks removed

4. **User Isolation Test**:
   - Create tasks as user A
   - Attempt to delete user A's workspace as user B
   - Verify permission denied

## Edge Cases & Considerations

1. **Running Tasks**: Both delete operations must cancel running tasks before deletion
2. **Workspace Sharing**: Task chains share workspaces - must count correctly
3. **Disk Space**: Old workspaces can accumulate - delete_all helps with cleanup
4. **Safety**: delete_all requires user_id to prevent accidental global deletion
5. **Persistence**: Deleted tasks removed from both memory and disk metadata files
6. **Concurrent Access**: Use existing locking patterns if needed (check _execute_task for patterns)

## Files to Modify

1. ✅ `agent/modules/claude_code/tools.py` - Add limit check, bulk delete method
2. ✅ `agent/modules/claude_code/manifest.py` - Add tool definitions
3. ✅ `agent/modules/claude_code/main.py` - Wire up new endpoint
4. ⚠️ `agent/dashboard/main.py` - Optional UI support (future enhancement)

## Rollout Steps

1. Implement code changes in order (Steps 1-4)
2. Test manually with multiple users
3. Deploy to development environment
4. Monitor for workspace limit errors
5. Gather feedback on limit (adjust if needed)
6. Optional: Build dashboard UI for task management

## Success Criteria

✅ Users cannot create more than 10 workspaces
✅ Clear error message when limit reached
✅ `delete_workspace` tool is callable via agent
✅ `delete_all_workspaces` tool works and requires user_id
✅ Task chains counted correctly (1 workspace = 1 count)
✅ Running tasks cancelled before deletion
✅ User isolation enforced (can't delete other users' workspaces)

## Timeline Estimate

- Step 1 (Limit): ~30 min
- Step 2 (Bulk Delete): ~45 min
- Step 3 (Manifest): ~15 min
- Step 4 (Endpoints): ~10 min
- Testing: ~30 min
- **Total**: ~2 hours

## Notes

- The existing `delete_workspace` method is well-implemented but not exposed as a tool
- Task persistence uses JSON files in each workspace directory
- The system already has good user isolation via `user_id` field
- Consider making MAX_WORKSPACES_PER_USER configurable via environment variable in future
