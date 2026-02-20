# Plan: Fix "Apply Plan" State & Prevent Duplicate Application

## Problem Statement

When a user applies a plan to a project, the backend operation can take 30-60+ seconds (Claude API call + sequential phase/task creation). During this time:

1. The frontend awaits the HTTP response; if the browser times out or the user navigates away, the in-progress state is lost.
2. After a timeout, the user sees the "Apply Plan" button again (since phases may or may not have been partially created), and clicking it again creates **duplicate phases**.
3. There is no persistent "applying" indicator that survives page navigation.

## Root Cause Analysis

### Backend (`agent/portal/routers/projects.py` lines 397–594)

The `POST /api/projects/{project_id}/apply-plan` endpoint is fully synchronous:
- It calls Claude Sonnet (can take 20-40s for large plans).
- It then loops over each phase calling `project_planner.add_phase` + `project_planner.bulk_add_tasks` sequentially.
- No idempotency guard: nothing prevents calling it twice for the same project.
- No intermediate state written to DB before the long-running part.

### Frontend

- `PlanningTaskPanel.tsx` — "Apply Plan" button is enabled whenever task status is `awaiting_input` or `completed`, with no check for whether phases already exist or applying is in-flight.
- `ProjectDetailPage.tsx` — The `PlanningTaskPanel` is shown when `project.phases.length === 0`. Once phases start being created this should hide the panel, but if the operation is aborted mid-way, partial phases exist and the panel is hidden but the user is left in an ambiguous state.
- The "Re-apply Plan" button in `ProjectDetailPage.tsx` (`handleReapplyPlan`) also has no idempotency guard.
- All applying state is local React state (`submitting`, `reapplying`) — lost on navigation.

### Database (`agent/shared/shared/models/project.py`)

The `projects` table has no column to persist an "applying" state. The existing `status` values are `planning | active | paused | completed | archived`. There is no `applying_plan` status or flag.

## Solution Overview

1. **Add a persistent `plan_apply_status` field to the `projects` table** (e.g., `idle | applying | applied | failed`) so the UI can read this on page load.
2. **Write state transitions at the start and end of the apply-plan endpoint** so the status is durable across navigation.
3. **Guard the apply-plan endpoint against concurrent/duplicate invocations** using the persisted status.
4. **Update the frontend** to read this status, show a persistent "applying" indicator when returning to the page, and disable the Apply Plan button when applying is already in-flight or done.

---

## Detailed Step-by-Step Plan

### Step 1: Add `plan_apply_status` to the `projects` table

**File:** `agent/shared/shared/models/project.py`

Add a new column:

```python
# Plan application state: "idle" | "applying" | "applied" | "failed"
plan_apply_status: Mapped[str] = mapped_column(String, default="idle")
plan_apply_error: Mapped[str | None] = mapped_column(Text, default=None)
```

- `idle` — default; no apply has been started.
- `applying` — the apply is in progress (backend is working).
- `applied` — phases were successfully created from the plan.
- `failed` — the apply attempt failed; error stored in `plan_apply_error`.

**Why this field and not overloading `project.status`?** The project lifecycle status (`planning`, `active`, etc.) is a separate concern from plan-apply progress. Adding a dedicated field avoids confusion and doesn't break existing status-based logic.

### Step 2: Create Alembic migration

**New file:** `agent/alembic/versions/016_add_plan_apply_status_to_projects.py`

```python
"""Add plan_apply_status and plan_apply_error to projects table.

Revision ID: 016
Revises: 015
Create Date: 2026-02-20
"""

from typing import Union
import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("plan_apply_status", sa.String(), nullable=False, server_default="idle"),
    )
    op.add_column(
        "projects",
        sa.Column("plan_apply_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "plan_apply_error")
    op.drop_column("projects", "plan_apply_status")
```

### Step 3: Update `project_planner` module tools to expose `plan_apply_status`

**File:** `agent/modules/project_planner/tools.py`

The `get_project` tool already returns project data. Ensure `plan_apply_status` and `plan_apply_error` are included in the returned dict (they will be automatically included since the model is now updated, but verify the serialization).

Also add an `update_project` path for `plan_apply_status` and `plan_apply_error` — these are portal-level DB writes, so they will be done directly via SQLAlchemy in the portal (not via the module tool), to keep the apply-plan logic self-contained in the portal router.

### Step 4: Update the apply-plan backend endpoint

**File:** `agent/portal/routers/projects.py`

Make the following changes to the `apply_plan` function (lines 397–594):

#### 4a. Idempotency guard at the top

After fetching the project, immediately check:

```python
current_apply_status = project_data.get("plan_apply_status", "idle")
if current_apply_status == "applying":
    raise HTTPException(status_code=409, detail="Plan application is already in progress. Please wait.")
if current_apply_status == "applied" and not body.force:
    raise HTTPException(status_code=409, detail="Plan has already been applied. Use force=true to re-apply.")
```

Add `force: bool = False` to `ApplyPlanRequest` for the re-apply use case.

#### 4b. Persist `applying` state before long-running work

Immediately after the guard check, before calling the Claude API, write `plan_apply_status = "applying"` directly to the DB via SQLAlchemy:

```python
async with session_factory() as session:
    await session.execute(
        update(Project)
        .where(Project.id == uuid.UUID(project_id))
        .values(plan_apply_status="applying", plan_apply_error=None, updated_at=datetime.now(timezone.utc))
    )
    await session.commit()
```

This ensures that if the browser disconnects, anyone who re-loads the page will see `applying`.

#### 4c. On success, write `applied`

After all phases and tasks are created:

```python
async with session_factory() as session:
    await session.execute(
        update(Project)
        .where(Project.id == uuid.UUID(project_id))
        .values(plan_apply_status="applied", updated_at=datetime.now(timezone.utc))
    )
    await session.commit()
```

#### 4d. On failure, write `failed` with error message

Wrap the entire try block and write `plan_apply_status = "failed"` + `plan_apply_error` in the except handler:

```python
except Exception as e:
    async with session_factory() as session:
        await session.execute(
            update(Project)
            .where(Project.id == uuid.UUID(project_id))
            .values(
                plan_apply_status="failed",
                plan_apply_error=str(e),
                updated_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()
    raise
```

#### 4e. Update `ApplyPlanRequest`

```python
class ApplyPlanRequest(BaseModel):
    plan_content: str | None = None
    custom_prompt: str | None = None
    force: bool = False  # Allow re-applying when already applied
```

#### 4f. Clear-phases endpoint should also reset `plan_apply_status`

In the `clear-phases` endpoint (which is called before re-apply), reset `plan_apply_status` to `idle`:

```python
async with session_factory() as session:
    await session.execute(
        update(Project)
        .where(Project.id == uuid.UUID(project_id))
        .values(plan_apply_status="idle", plan_apply_error=None, updated_at=datetime.now(timezone.utc))
    )
    await session.commit()
```

### Step 5: Expose `plan_apply_status` in the project detail API response

**File:** `agent/portal/routers/projects.py`

The project detail endpoint fetches project data via `project_planner.get_project`. The module tool needs to include the new fields. Check `agent/modules/project_planner/tools.py` `get_project` method and ensure `plan_apply_status` and `plan_apply_error` are returned.

Since the portal also directly queries the DB in some places, add a fallback: if the module response doesn't include `plan_apply_status`, query the DB directly:

```python
# In GET /api/projects/{project_id}
# After fetching project_data from project_planner.get_project:
# Add plan_apply_status from direct DB lookup if not present
if "plan_apply_status" not in project_data:
    async with session_factory() as session:
        row = await session.get(Project, uuid.UUID(project_id))
        if row:
            project_data["plan_apply_status"] = row.plan_apply_status
            project_data["plan_apply_error"] = row.plan_apply_error
```

Alternatively (cleaner): update the module tools to include these fields, and update the project detail portal endpoint to directly include them from DB. Given the portal already imports and uses SQLAlchemy models directly, prefer a direct DB read for the new fields in the portal's GET endpoint.

### Step 6: Update the project_planner module `get_project` tool

**File:** `agent/modules/project_planner/tools.py`

In the `get_project` method, include `plan_apply_status` and `plan_apply_error` in the returned dictionary:

```python
return {
    ...existing fields...,
    "plan_apply_status": project.plan_apply_status,
    "plan_apply_error": project.plan_apply_error,
}
```

This makes the status accessible to the agent/LLM as well as the portal frontend.

### Step 7: Update the TypeScript types

**File:** `agent/portal/frontend/src/types.ts` (or wherever `Project` type is defined)

Add the new fields to the `Project` interface:

```typescript
interface Project {
  // ... existing fields ...
  plan_apply_status: "idle" | "applying" | "applied" | "failed";
  plan_apply_error: string | null;
}
```

### Step 8: Update `PlanningTaskPanel.tsx`

**File:** `agent/portal/frontend/src/components/projects/PlanningTaskPanel.tsx`

Changes:
1. Accept `planApplyStatus` and `planApplyError` as props (passed from the parent page).
2. When `planApplyStatus === "applying"`, show a persistent "Applying plan..." spinner instead of the "Apply Plan" button — this state survives page navigation.
3. When `planApplyStatus === "applied"`, do not show the "Apply Plan" button at all (plan is already applied). The parent hides the panel when `phases.length > 0`, but this adds a safety net.
4. When `planApplyStatus === "failed"`, show an error banner with the error message and allow retry (re-sets to `idle` before re-applying).
5. Disable the "Apply Plan" button while `planApplyStatus === "applying"` as a secondary guard.

Updated component signature:
```typescript
interface PlanningTaskPanelProps {
  planningTaskId: string;
  projectId: string;
  planApplyStatus: "idle" | "applying" | "applied" | "failed";
  planApplyError: string | null;
  onPlanApplied: () => void;
}
```

New UI states to add:
- **Applying indicator** (shown when `planApplyStatus === "applying"`): A full-panel spinner with "Applying plan to project... This may take a minute. You can navigate away and return — your plan will still be applying." This replaces the apply button section.
- **Applied state** (when `planApplyStatus === "applied"` but `phases.length === 0` somehow): "Plan applied. Refreshing..."
- **Failed state** (when `planApplyStatus === "failed"`): Red error box showing `planApplyError`, with a "Retry" button that calls `POST /clear-phases` (to reset status to `idle`) then `POST /apply-plan` again.

### Step 9: Update `ProjectDetailPage.tsx`

**File:** `agent/portal/frontend/src/pages/ProjectDetailPage.tsx`

Changes:
1. Pass `plan_apply_status` and `plan_apply_error` to `PlanningTaskPanel`.
2. Change the condition for showing `PlanningTaskPanel`:
   - Current: `project.planning_task_id && project.phases.length === 0`
   - New: `project.planning_task_id && (project.phases.length === 0 || project.plan_apply_status === "applying" || project.plan_apply_status === "failed")`
   - This ensures the panel is shown (with applying/failed state) even if partial phases exist.
3. When `plan_apply_status === "applying"`, show a persistent banner in the phases section: "Plan is being applied... Please wait." and disable the "Re-apply Plan" button.
4. Poll more aggressively (every 3s instead of on-demand) when `plan_apply_status === "applying"` so the UI auto-updates when the apply finishes.
5. For the "Re-apply Plan" flow (`handleReapplyPlan`), pass `force: true` in the apply-plan request body (since clear-phases resets status to `idle`, this may not be needed, but is a safety net).

### Step 10: Update `useProjectDetail` hook for polling during apply

**File:** `agent/portal/frontend/src/hooks/useProjects.ts`

In the `useProjectDetail` hook, add auto-polling when `plan_apply_status === "applying"`:

```typescript
useEffect(() => {
  if (project?.plan_apply_status === "applying") {
    const interval = setInterval(() => refetch(), 3000);
    return () => clearInterval(interval);
  }
}, [project?.plan_apply_status, refetch]);
```

This way, after navigating back to the project, the page will automatically poll until the apply completes and then show the phases.

---

## Files to Modify

| File | Change |
|------|--------|
| `agent/shared/shared/models/project.py` | Add `plan_apply_status` + `plan_apply_error` columns |
| `agent/alembic/versions/016_add_plan_apply_status_to_projects.py` | New migration file |
| `agent/modules/project_planner/tools.py` | Include new fields in `get_project` return dict |
| `agent/portal/routers/projects.py` | Add idempotency guard, state transitions, `force` param, clear-phases reset |
| `agent/portal/frontend/src/types.ts` | Add new fields to `Project` type |
| `agent/portal/frontend/src/components/projects/PlanningTaskPanel.tsx` | Show persistent applying/failed state, disable button when applying |
| `agent/portal/frontend/src/pages/ProjectDetailPage.tsx` | Pass new props, adjust show condition, add polling, disable re-apply when applying |
| `agent/portal/frontend/src/hooks/useProjects.ts` | Auto-poll when `plan_apply_status === "applying"` |

---

## Migration & Rollout Notes

- The migration adds two nullable/defaulted columns to `projects` — safe to run with zero downtime.
- All existing projects will have `plan_apply_status = "idle"` after migration (server_default).
- No data backfill needed: existing projects with phases will still show phases normally; the new field only affects the apply flow going forward.
- Projects that were mid-apply when this deploys will have `plan_apply_status = "idle"` (safe — they can re-apply or the partial phases can be cleared).

---

## Edge Cases Handled

1. **User navigates away mid-apply**: DB has `applying`; on return, frontend polls and shows the applying indicator. When done, auto-polls to `applied` and shows phases.
2. **Browser crash mid-apply**: Same as above.
3. **Network timeout (HTTP 504)**: Backend continues writing to DB. Frontend retries `GET /api/projects/{id}` which returns `applying`. Auto-polling kicks in.
4. **Double-click "Apply Plan"**: Second request hits the 409 guard (`applying` state) and is rejected.
5. **Plan parse fails**: Backend writes `failed` + error message. Frontend shows error with retry option.
6. **Re-apply Plan**: `clear-phases` resets to `idle`, then apply proceeds normally. `force: true` provides an extra safety net.
7. **Partial phase creation**: If the apply crashes mid-loop, status stays `applying` (or goes to `failed` if caught). The user sees the applying state and can wait, or if it transitions to `failed`, can retry (which will clear and re-apply).
