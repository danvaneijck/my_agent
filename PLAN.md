# Fix: Project Automated Workflow Reliability

## Problem Statement

The automated workflow for the "deployments ui" project failed during Phase 3 execution. Two root causes were identified from reviewing the task execution logs.

---

## Root Cause Analysis

### Root Cause 1 — Git Branch Naming Conflict

**What happened:**
- Phase 2 executed on branch `project/deployments-ui` (a flat ref at the `project/` prefix level)
- Phase 3 tried to create branch `project/deployments-ui/phase/0/phase-3-polish-and-validation`
- Git rejected the push: `cannot lock ref '...phase/0/...': 'refs/heads/project/deployments-ui' exists; cannot create '...'`
- Phase 3 worked around this by deleting the Phase 2 branch remotely before pushing its own

**Why it happened:**
Git does not allow a ref path to be both a leaf ref and a directory node simultaneously. If `project/deployments-ui` exists as a branch (leaf), then no branch can exist under `project/deployments-ui/...` (would need `project/deployments-ui` to be a directory node).

The `create_project` function correctly uses the `/integration` suffix for the project-level branch (`project/{slug}/integration`) so phase branches (`project/{slug}/phase/{n}/...`) don't conflict. However, if a project is set up without `repo_owner`/`repo_name` (so `project_branch=None`), or if phases are executed with a manually specified flat branch name, the naming convention breaks.

**The specific failure mode:** Phase 2's `branch_name` in the DB was `project/deployments-ui` while Phase 3's was the hierarchical `project/deployments-ui/phase/0/phase-3-polish-and-validation`. When these co-exist in git, the latter is rejected.

**Missing safeguard:** `execute_next_phase` does not validate that the target `phase_branch` can actually be created in git before launching the claude_code task.

---

### Root Cause 2 — Fresh Conversation Context Loss During Workflow Chaining

**What happened:**
- When Phase 2 completed, the scheduler posted the `on_success_message` to trigger Phase 3
- Phase 3 started in a fresh conversation without knowledge of completed phases
- The agent had to reconstruct context about the project from scratch

**Why it happened:**
The `start_project_workflow` function creates a scheduler job that posts an `on_success_message` when each phase's claude_code task completes. This message is delivered to a **new conversation** (by design — `on_complete='resume_conversation'`). The receiving agent must then manually call three separate tools:

1. `project_planner.complete_phase(phase_id, claude_task_id)` — mark phase done, create PR
2. `project_planner.execute_next_phase(project_id)` — start next phase
3. `scheduler.add_job(...)` — create a new monitoring job for the new phase

Step 3 is the fragile part. An agent starting fresh must reconstruct the correct `check_config`, `on_success_message` format, and workflow parameters without any prior conversation context. This requires the agent to "know" the scheduler job creation convention, which is not reliably inferred from the message alone.

---

### Root Cause 3 — Phase Prompts Lack Completed Phase Context

**What happened:**
Phase 3 received a prompt saying "Phase 2 is complete. Now implement Phase 3..." but the prompt did not include:
- What Phase 2 actually implemented (which files were changed)
- The branch names of completed phases (what the source branch looks like)
- Git workflow instructions (what branch to work on, what to PR against)

**Why it matters:**
Without this context, the executing agent may:
- Not know where to find prior work (wrong source branch assumption)
- Create PRs targeting the wrong base branch
- Duplicate work that was already done

---

## Proposed Fixes

### Fix 1 — Add `advance_project_workflow` Tool (High Priority)

**Goal:** Replace the brittle 3-step manual process in `on_success_message` with a single atomic tool call.

**New method:** `ProjectPlannerTools.advance_project_workflow(phase_id, claude_task_id, project_id, workflow_id, platform, platform_channel_id, user_id)`

**Behavior:**
1. Calls `complete_phase(phase_id, claude_task_id)` — marks phase done, creates PR
2. Calls `execute_next_phase(project_id)` — starts next phase
3. If next phase was started, automatically creates a new scheduler job to monitor it
4. If no next phase, marks project as completed

**New `on_success_message` format** (simple single tool call):
```
[Project Workflow] Phase '{phase_name}' claude_code task has finished.

Call:
  project_planner.advance_project_workflow(
    phase_id='{phase_id}',
    claude_task_id='{claude_task_id}',
    project_id='{project_id}',
    workflow_id='{workflow_id}',
    platform='{platform}',
    platform_channel_id='{platform_channel_id}'
  )
```

This reduces agent responsibility from constructing a new scheduler job to making one well-defined tool call.

---

### Fix 2 — Branch Conflict Detection Before Phase Execution (High Priority)

**Goal:** Detect git ref conflicts before launching a claude_code task and fail fast with a clear error.

**Where:** `execute_next_phase` in `project_planner/tools.py`

**Detection logic (DB-level):** Before launching `claude_code.run_task`, check the target `phase_branch` against:
- The `project_branch` stored in the DB
- All other `phase.branch_name` values for phases in the same project

**Conflict conditions:**
- `phase_branch == project_branch` (exact duplicate)
- `phase_branch` starts with `{other_phase_branch}/` (target is a child of existing flat ref)
- `other_phase_branch` starts with `{phase_branch}/` (existing branch is a child of target)

**On conflict:** Raise a `ValueError` with a clear description:
```
Branch conflict: cannot create 'project/deployments-ui/phase/0/...' because
'project/deployments-ui' exists as a sibling branch in the same project.
To fix: update the branch_name for the conflicting phase in the DB, or
rename the conflicting remote branch before continuing.
```

This ensures the workflow fails loudly rather than silently proceeding and having the claude_code task worker fail partway through.

---

### Fix 3 — Enrich Phase Prompts With Completed Phase Context (Medium Priority)

**Goal:** Each phase's prompt includes a summary of what previous phases accomplished.

**Where:** `_build_batch_prompt` in `project_planner/tools.py`

**New parameter:** `completed_phases: list[dict] | None = None`

Each dict in `completed_phases` contains:
- `name` — phase name
- `branch_name` — git branch used
- `pr_number` — PR number (if created)
- `task_titles` — list of completed task titles

**Prompt addition** (inserted before `# Your Tasks`):

```markdown
# Project Progress

The following phases have already been completed and merged:

## Phase: {name} (branch: `{branch_name}`, PR #{pr_number})
Tasks completed:
- {task_title_1}
- {task_title_2}

---
```

**Where to collect this data:** In `execute_next_phase`, after loading `target_phase`, query for all phases with `status="completed"` in the same project and fetch their tasks. Pass this to `get_execution_plan` which passes to `_build_batch_prompt`.

---

### Fix 4 — Git Workflow Section in Phase Prompts (Medium Priority)

**Goal:** Each phase task receives explicit git instructions so it doesn't have to guess.

**Where:** End of `_build_batch_prompt` output.

**New section added to every phase prompt:**

```markdown
---

IMPORTANT — Git workflow:
- Commit your changes with descriptive commit messages as you work.
- When you are done, push your branch: git push -u origin HEAD
- Do NOT leave uncommitted changes.
- When creating a pull request, do NOT include PLAN.md in the PR diff.
  PLAN.md is a planning artifact only. Before opening the PR, remove it
  from the branch with:
  `git rm --cached PLAN.md && git commit -m 'chore: remove planning artifact'`
  (skip this step if PLAN.md was never committed on this branch).
```

This is the same git workflow footer that is already included in task prompts from `start_project_workflow`. Making it part of `_build_batch_prompt` ensures it appears for every phase regardless of how the task is launched.

---

### Fix 5 — Source Branch Info in Phase Prompts (Medium Priority)

**Goal:** Include the source branch and working branch in the phase prompt so the agent knows its git context.

**Where:** `_build_batch_prompt`, alongside the git workflow section.

**Addition** (at the start of the git workflow section):

```markdown
## Git Context

- **Your working branch:** `{branch_name}`
- **Based on:** `{source_branch}` (contains all work from prior phases)
- **PR will target:** `{pr_base}` (project integration branch)

Do NOT delete or force-push any branches other than your own working branch.
```

**How to pass these values:** `_build_batch_prompt` already receives phases; extend it to also accept `branch_name: str | None`, `source_branch: str | None`, and `pr_base: str | None` which are populated in `execute_next_phase` when building the prompt.

---

## Files to Modify

| File | Change | Priority |
|---|---|---|
| `agent/modules/project_planner/tools.py` | Add `advance_project_workflow` method | High |
| `agent/modules/project_planner/tools.py` | Update `start_project_workflow` `on_success_message` | High |
| `agent/modules/project_planner/tools.py` | Add branch conflict detection in `execute_next_phase` | High |
| `agent/modules/project_planner/tools.py` | Enrich `_build_batch_prompt` with completed phases + git context | Medium |
| `agent/modules/project_planner/tools.py` | Pass completed phases + branch info to `_build_batch_prompt` from `execute_next_phase` | Medium |
| `agent/modules/project_planner/manifest.py` | Add `advance_project_workflow` tool definition | High |
| `agent/modules/project_planner/main.py` | Add `advance_project_workflow` to `_ALLOWED_TOOLS` dispatch | High |

No database migrations required. No new modules. No Docker Compose changes.

---

## Step-by-Step Implementation

### Step 1 — Add `advance_project_workflow` to `tools.py`

Add after the `complete_phase` method:

```python
async def advance_project_workflow(
    self,
    phase_id: str,
    claude_task_id: str,
    project_id: str,
    workflow_id: str,
    platform: str,
    platform_channel_id: str,
    auto_push: bool = True,
    timeout: int = 1800,
    user_id: str | None = None,
) -> dict:
    """
    Atomic phase transition for scheduler-driven workflows.

    1. Completes the current phase (creates PR, updates task statuses).
    2. Executes the next phase (launches claude_code task).
    3. Creates a new scheduler job to monitor the next phase.

    Designed to be called from the scheduler on_success_message in a fresh
    conversation — all parameters are self-contained.
    """
    if not user_id:
        raise ValueError("user_id is required")

    # Step 1: Complete the current phase
    complete_result = await self.complete_phase(
        phase_id=phase_id,
        claude_task_id=claude_task_id,
        user_id=user_id,
    )

    if not complete_result.get("success"):
        return {
            "success": False,
            "stage": "complete_phase",
            "message": complete_result.get("message"),
        }

    # Step 2: Execute the next phase
    next_result = await self.execute_next_phase(
        project_id=project_id,
        auto_push=auto_push,
        timeout=timeout,
        user_id=user_id,
    )

    # No more phases — workflow complete
    if "claude_task_id" not in next_result:
        return {
            "success": True,
            "stage": "workflow_complete",
            "phase_completed": complete_result,
            "message": next_result.get("message", "All phases complete."),
        }

    new_claude_task_id = next_result["claude_task_id"]
    new_phase_id = next_result["phase_id"]
    new_phase_name = next_result["phase_name"]

    # Step 3: Fetch project name for the scheduler message
    async with self.session_factory() as session:
        result = await session.execute(
            select(Project).where(Project.id == uuid.UUID(project_id))
        )
        project = result.scalar_one_or_none()
        project_name = project.name if project else project_id

    # Step 4: Build the on_success_message for the new phase
    on_success_message = _build_advance_message(
        project_id=project_id,
        project_name=project_name,
        phase_id=new_phase_id,
        phase_name=new_phase_name,
        claude_task_id=new_claude_task_id,
        workflow_id=workflow_id,
        platform=platform,
        platform_channel_id=platform_channel_id,
    )

    # Step 5: Create a new scheduler job for the new phase
    async with httpx.AsyncClient(timeout=30.0, headers=get_service_auth_headers()) as client:
        resp = await client.post(
            f"{settings.module_services['scheduler']}/execute",
            json={
                "tool_name": "scheduler.add_job",
                "arguments": {
                    "job_type": "poll_module",
                    "check_config": {
                        "module": "claude_code",
                        "tool": "claude_code.task_status",
                        "args": {"task_id": new_claude_task_id},
                        "success_field": "status",
                        "success_values": ["completed", "failed", "timed_out", "cancelled"],
                    },
                    "interval_seconds": 30,
                    "max_attempts": 240,
                    "on_success_message": on_success_message,
                    "on_complete": "resume_conversation",
                    "workflow_id": workflow_id,
                    "platform": platform,
                    "platform_channel_id": platform_channel_id,
                },
                "user_id": user_id,
            }
        )
        if resp.status_code != 200 or not resp.json().get("success"):
            raise ValueError(f"Failed to create scheduler job for next phase: {resp.text}")

    return {
        "success": True,
        "stage": "next_phase_started",
        "phase_completed": complete_result,
        "next_phase": next_result,
        "message": (
            f"Phase '{complete_result.get('phase_name')}' completed. "
            f"Started next phase '{new_phase_name}'. Scheduler job created."
        ),
    }
```

Also add the `_build_advance_message` helper as a module-level function:

```python
def _build_advance_message(
    project_id: str,
    project_name: str,
    phase_id: str,
    phase_name: str,
    claude_task_id: str,
    workflow_id: str,
    platform: str,
    platform_channel_id: str,
) -> str:
    """Build the on_success_message for the scheduler to post when a phase task completes."""
    return (
        f"[Project Workflow] Project '{project_name}' phase '{phase_name}' "
        f"(claude_code task `{claude_task_id}`) has finished.\n\n"
        f"Call `project_planner.advance_project_workflow` with these exact parameters:\n"
        f"  phase_id: '{phase_id}'\n"
        f"  claude_task_id: '{claude_task_id}'\n"
        f"  project_id: '{project_id}'\n"
        f"  workflow_id: '{workflow_id}'\n"
        f"  platform: '{platform}'\n"
        f"  platform_channel_id: '{platform_channel_id}'"
    )
```

### Step 2 — Update `start_project_workflow` to use `_build_advance_message`

Replace the inline `on_success_message` string in `start_project_workflow` with:

```python
on_success_message = _build_advance_message(
    project_id=project_id,
    project_name=project.name,
    phase_id=phase_id,
    phase_name=phase_name,
    claude_task_id=claude_task_id,
    workflow_id=workflow_id,
    platform=platform,
    platform_channel_id=platform_channel_id,
)
```

### Step 3 — Add Branch Conflict Detection in `execute_next_phase`

Insert before the `use_continue_task` determination block (after `phase_branch` and `source_branch` are computed):

```python
# Validate branch doesn't conflict with other branches in this project
if phase_branch:
    all_branches = [project.project_branch] + [p.branch_name for p in phases if p.branch_name]
    for existing in all_branches:
        if existing == phase_branch:
            continue  # same phase, skip
        if existing and (
            phase_branch.startswith(existing + "/") or existing.startswith(phase_branch + "/")
        ):
            raise ValueError(
                f"Branch naming conflict: '{phase_branch}' conflicts with existing branch "
                f"'{existing}' in this project. Git does not allow a ref to be both a leaf "
                f"and a directory node. Fix: rename the conflicting phase branch in the DB "
                f"or delete the conflicting remote ref before continuing."
            )
```

### Step 4 — Enhance `_build_batch_prompt` With Completed Phase Context

Update the signature:

```python
@staticmethod
def _build_batch_prompt(
    project_name: str,
    design_document: str | None,
    phases: list[dict],
    completed_phases: list[dict] | None = None,  # NEW
    branch_name: str | None = None,              # NEW
    source_branch: str | None = None,            # NEW
    pr_base: str | None = None,                  # NEW
) -> str:
```

After the `<project-plan>` section and before `# Your Tasks`, insert:

```python
if completed_phases:
    lines.append("# Project Progress")
    lines.append("")
    lines.append("The following phases have already been completed:")
    lines.append("")
    for cp in completed_phases:
        pr_info = f" (PR #{cp['pr_number']})" if cp.get("pr_number") else ""
        lines.append(f"## Completed: {cp['name']} — branch `{cp.get('branch_name', 'unknown')}`{pr_info}")
        for title in cp.get("task_titles", []):
            lines.append(f"- {title}")
        lines.append("")
    lines.append("---")
    lines.append("")
```

Before the final `return`, add the git context section:

```python
lines.append("---")
lines.append("")
lines.append("## Git Context")
lines.append("")
if branch_name:
    lines.append(f"- **Your working branch:** `{branch_name}`")
if source_branch:
    lines.append(f"- **Based on:** `{source_branch}` (contains all prior phase work)")
if pr_base:
    lines.append(f"- **PR will target:** `{pr_base}`")
lines.append("")
lines.append("---")
lines.append("")
lines.append("IMPORTANT — Git workflow:")
lines.append("- Commit your changes with descriptive commit messages as you work.")
lines.append("- When you are done, push your branch: `git push -u origin HEAD`")
lines.append("- Do NOT leave uncommitted changes.")
lines.append(
    "- When creating a pull request, do NOT include PLAN.md in the PR diff. "
    "PLAN.md is a planning artifact only. Before opening the PR, remove it "
    "from the branch with: `git rm --cached PLAN.md && git commit -m 'chore: remove planning artifact'` "
    "(skip this step if PLAN.md was never committed on this branch)."
)
```

### Step 5 — Pass Completed Phases to `_build_batch_prompt` via `get_execution_plan`

In `get_execution_plan`, after the project and phases are loaded, query completed phases:

```python
# Collect completed phase context
completed_phases_data = []
for p in all_phases:
    if p.status == "completed":
        tasks_result = await session.execute(
            select(ProjectTask).where(ProjectTask.phase_id == p.id)
        )
        phase_tasks = list(tasks_result.scalars().all())
        pr_numbers = {t.pr_number for t in phase_tasks if t.pr_number}
        completed_phases_data.append({
            "name": p.name,
            "branch_name": p.branch_name,
            "pr_number": next(iter(pr_numbers), None),
            "task_titles": [t.title for t in phase_tasks],
        })
```

Pass these to `_build_batch_prompt` along with `branch_name`, `source_branch`, and `pr_base`.

Update `get_execution_plan` return value to include these fields so `execute_next_phase` can pass them through.

### Step 6 — Add `advance_project_workflow` to `manifest.py`

```python
ToolDefinition(
    name="project_planner.advance_project_workflow",
    description=(
        "Atomic phase transition for automated project workflows. "
        "Completes the current phase (creates PR, updates tasks), executes the next phase, "
        "and creates a new scheduler job to monitor it. "
        "Call this from the scheduler on_success_message when a phase's claude_code task finishes."
    ),
    parameters=[
        ToolParameter(name="phase_id", type="string", description="ID of the just-completed phase", required=True),
        ToolParameter(name="claude_task_id", type="string", description="Claude Code task ID for the completed phase", required=True),
        ToolParameter(name="project_id", type="string", description="Project UUID", required=True),
        ToolParameter(name="workflow_id", type="string", description="Workflow UUID linking all scheduler jobs", required=True),
        ToolParameter(name="platform", type="string", description="Bot platform (discord|telegram|slack)", required=True),
        ToolParameter(name="platform_channel_id", type="string", description="Channel to post scheduler notifications", required=True),
        ToolParameter(name="auto_push", type="boolean", description="Auto-push branch after completion", required=False),
        ToolParameter(name="timeout", type="integer", description="Timeout in seconds for the next phase task", required=False),
    ],
    required_permission="admin",
),
```

### Step 7 — Add dispatch in `main.py`

In the `_ALLOWED_TOOLS` set and the `execute` endpoint dispatch:

```python
"advance_project_workflow": tools.advance_project_workflow,
```

---

## Acceptance Criteria

| Scenario | Expected Behaviour |
|---|---|
| Phase N completes, scheduler fires | Agent calls `advance_project_workflow` with a single tool call; next phase starts automatically |
| Branch conflict detected | `execute_next_phase` raises `ValueError` with clear description before any docker task is started |
| Phase 3 prompt | Includes "Project Progress" section listing phases 1 and 2 with their branches and PR numbers |
| Phase 3 prompt | Includes "Git Context" with working branch, source branch, PR target |
| `advance_project_workflow` called when all phases done | Returns `{"stage": "workflow_complete"}` without error |
| `advance_project_workflow` called after a failed phase | Marks phase tasks as failed, does NOT start next phase |

---

## Out of Scope

- Remote git ref validation (checking GitHub API for conflicting refs) — DB-level conflict detection is sufficient for the common case
- UI for monitoring workflow progress — the existing `get_project_status` tool and portal handle this
- Parallel phase execution — phases remain sequential
- Auto-retry on failed phases — still requires manual intervention
