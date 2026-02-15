# New Project Flow — Implementation Plan

## Feature Overview

Add a "New Project" button to the Projects portal page that opens a multi-step creation form with:
1. **Git repo selection** — dropdown to pick an existing repo OR create a new one
2. **Plan & auto-push options** — toggle whether the project starts with a planning phase or jumps straight to execution, and whether to auto-push branches
3. **Kick-off** — on submit, creates the project record AND fires a `claude_code.run_task` to plan/scaffold the project

The flow ties together three existing modules: **project_planner**, **git_platform**, and **claude_code**.

---

## Current State Analysis

### What exists
- `POST /api/projects` portal endpoint → calls `project_planner.create_project` (fully working)
- `GET /api/repos` portal endpoint → calls `git_platform.list_repos` (fully working, supports search)
- `POST /api/tasks` portal endpoint → calls `claude_code.run_task` (fully working)
- `project_planner.get_execution_plan` → builds a batch prompt from phases/tasks
- `ProjectsPage.tsx` — lists projects but has **no** "New Project" button or creation UI
- `useRepos` hook — fetches repos from `/api/repos`
- `useProjects` hook — fetches projects from `/api/projects`

### What's missing
- **No `create_repo` tool** in `git_platform` — GitHub provider doesn't implement repo creation
- **No UI** for creating projects from the portal
- **No backend endpoint** to orchestrate the combined flow (create project + kick off claude task)
- **No "New Repo" form** in the frontend

---

## Architecture Decision

**Two-phase approach**: Rather than a single monolithic endpoint, we split the flow into composable steps that the frontend orchestrates:

1. **Frontend** renders a modal/drawer with the form
2. **Frontend** calls `POST /api/repos` (new endpoint) if user wants to create a repo
3. **Frontend** calls `POST /api/projects` (existing) to create the project record
4. **Frontend** calls `POST /api/projects/{project_id}/kickoff` (new endpoint) to fire the claude task

This keeps each backend endpoint focused and reusable. The frontend orchestrates the sequence with loading/error states between steps.

---

## Files to Modify / Create

### Backend (Portal API)

| File | Action | Description |
|------|--------|-------------|
| `agent/modules/git_platform/providers/base.py` | Modify | Add abstract `create_repo` method |
| `agent/modules/git_platform/providers/github.py` | Modify | Implement `create_repo` via GitHub API `POST /user/repos` |
| `agent/modules/git_platform/providers/bitbucket.py` | Modify | Implement `create_repo` via Bitbucket API |
| `agent/modules/git_platform/manifest.py` | Modify | Add `git_platform.create_repo` tool definition |
| `agent/modules/git_platform/tools.py` | Modify | Add `create_repo` method to `GitPlatformTools` |
| `agent/modules/git_platform/main.py` | Modify | Add routing for `create_repo` in `/execute` |
| `agent/portal/routers/repos.py` | Modify | Add `POST /api/repos` endpoint for creating repos |
| `agent/portal/routers/projects.py` | Modify | Add `POST /api/projects/{project_id}/kickoff` endpoint |

### Frontend

| File | Action | Description |
|------|--------|-------------|
| `agent/portal/frontend/src/pages/ProjectsPage.tsx` | Modify | Add "New Project" button + mount the modal |
| `agent/portal/frontend/src/components/NewProjectModal.tsx` | Create | Multi-step creation form modal |
| `agent/portal/frontend/src/hooks/useProjects.ts` | Modify | Add `createProject` and `kickoffProject` functions |
| `agent/portal/frontend/src/hooks/useRepos.ts` | Modify | Add `createRepo` function |
| `agent/portal/frontend/src/types/index.ts` | Modify | Add `CreateProjectPayload`, `CreateRepoPayload`, `KickoffResult` types |

---

## Detailed Implementation Steps

### Step 1: Add `create_repo` to git_platform module

**1a. `agent/modules/git_platform/providers/base.py`**
Add abstract method:
```python
@abstractmethod
async def create_repo(
    self, name: str, description: str | None = None,
    private: bool = True, auto_init: bool = True,
) -> dict:
    """Create a new repository."""
```

**1b. `agent/modules/git_platform/providers/github.py`**
Implement using `POST /user/repos`:
```python
async def create_repo(self, name, description=None, private=True, auto_init=True):
    body = {"name": name, "private": private, "auto_init": auto_init}
    if description:
        body["description"] = description
    resp = await self._client.post("/user/repos", json=body)
    # parse response → return {owner, repo, full_name, clone_url, default_branch, ...}
```

**1c. `agent/modules/git_platform/providers/bitbucket.py`**
Implement using `POST /2.0/repositories/{workspace}/{repo_slug}`:
```python
async def create_repo(self, name, description=None, private=True, auto_init=True):
    slug = name.lower().replace(" ", "-")
    body = {"scm": "git", "is_private": private, "name": name}
    if description:
        body["description"] = description
    resp = await self._client.post(f"/2.0/repositories/{self._username}/{slug}", json=body)
    # parse response → same shape as github
```

**1d. `agent/modules/git_platform/manifest.py`**
Add tool definition:
```python
ToolDefinition(
    name="git_platform.create_repo",
    description="Create a new git repository.",
    parameters=[
        ToolParameter(name="name", type="string", description="Repository name", required=True),
        ToolParameter(name="description", type="string", description="Repository description", required=False),
        ToolParameter(name="private", type="boolean", description="Whether the repo is private", required=False),
        ToolParameter(name="auto_init", type="boolean", description="Initialize with README", required=False),
    ],
    required_permission="user",
)
```

**1e. `agent/modules/git_platform/tools.py`**
Add method delegation:
```python
async def create_repo(self, name: str, **kwargs) -> dict:
    return await self.provider.create_repo(name, **kwargs)
```

**1f. `agent/modules/git_platform/main.py`**
Add `create_repo` to the tool dispatch in `/execute`.

### Step 2: Add portal backend endpoints

**2a. `agent/portal/routers/repos.py` — `POST /api/repos`**

New endpoint to create a repository:
```python
class CreateRepoBody(BaseModel):
    name: str
    description: str | None = None
    private: bool = True

@router.post("")
async def create_repo(body: CreateRepoBody, user: PortalUser = Depends(require_auth)):
    result, err = await _safe_call(
        "git_platform", "git_platform.create_repo",
        {"name": body.name, "description": body.description, "private": body.private},
        str(user.user_id)
    )
    if err:
        return err
    return result
```

**2b. `agent/portal/routers/projects.py` — `POST /api/projects/{project_id}/kickoff`**

New endpoint that takes a project, generates an execution plan, and fires a claude_code task:

```python
class KickoffRequest(BaseModel):
    mode: str = "plan"  # "plan" or "execute"
    auto_push: bool = True
    timeout: int = 1800
    description: str | None = None  # optional free-form project description/goal for the prompt

@router.post("/{project_id}/kickoff")
async def kickoff_project(
    project_id: str,
    body: KickoffRequest,
    user: PortalUser = Depends(require_auth),
):
    # 1. Get the project to extract repo info
    project = await call_tool(
        module="project_planner",
        tool_name="project_planner.get_project",
        arguments={"project_id": project_id},
        user_id=str(user.user_id),
    )
    project_data = project.get("result", {})

    # 2. Build prompt — for "plan" mode, ask Claude to create a design doc + phases + tasks
    #    For "execute" mode, use get_execution_plan if tasks exist, else generate from description
    repo_owner = project_data.get("repo_owner")
    repo_name = project_data.get("repo_name")
    repo_url = f"https://github.com/{repo_owner}/{repo_name}" if repo_owner and repo_name else None
    branch = project_data.get("default_branch", "main")

    if body.mode == "plan":
        # Ask Claude to analyze the repo and create a project plan
        prompt = _build_planning_prompt(project_data, body.description)
    else:
        # Try to get execution plan from existing tasks
        exec_plan = await call_tool(
            module="project_planner",
            tool_name="project_planner.get_execution_plan",
            arguments={"project_id": project_id},
            user_id=str(user.user_id),
        )
        plan_data = exec_plan.get("result", {})
        if plan_data.get("prompt"):
            prompt = plan_data["prompt"]
            branch = plan_data.get("branch", branch)
        else:
            prompt = _build_planning_prompt(project_data, body.description)
            body.mode = "plan"  # Fall back to planning

    # 3. Fire claude_code task
    task_args = {
        "prompt": prompt,
        "mode": body.mode,
        "auto_push": body.auto_push,
        "timeout": body.timeout,
    }
    if repo_url:
        task_args["repo_url"] = repo_url
        task_args["branch"] = f"project/{_slugify(project_data.get('name', 'new'))}"
        task_args["source_branch"] = branch

    task_result = await call_tool(
        module="claude_code",
        tool_name="claude_code.run_task",
        arguments=task_args,
        user_id=str(user.user_id),
        timeout=30.0,
    )
    claude_task = task_result.get("result", {})

    # 4. Update project status to "active" and store claude_task_id
    await call_tool(
        module="project_planner",
        tool_name="project_planner.update_project",
        arguments={"project_id": project_id, "status": "active"},
        user_id=str(user.user_id),
    )

    return {
        "project_id": project_id,
        "claude_task_id": claude_task.get("task_id"),
        "mode": body.mode,
        "workspace": claude_task.get("workspace"),
    }
```

Helper function to build the planning prompt:
```python
def _build_planning_prompt(project_data: dict, description: str | None) -> str:
    name = project_data.get("name", "Untitled")
    desc = description or project_data.get("description") or ""
    design_doc = project_data.get("design_document") or ""

    lines = [
        f'You are planning a software project called "{name}".',
        "",
    ]
    if desc:
        lines.append(f"## Project Goal\n\n{desc}\n")
    if design_doc:
        lines.append(f"## Design Document\n\n{design_doc}\n")

    lines.extend([
        "## Your Task",
        "",
        "1. Analyze the repository (if it exists) to understand the current codebase.",
        "2. Create a detailed design document covering architecture, key decisions, and implementation approach.",
        "3. Break the project into phases, each with concrete, implementable tasks.",
        "4. Each task should have a clear title, description, and acceptance criteria.",
        "5. Write the plan to PLAN.md in the workspace.",
        "",
        "Focus on creating an actionable, well-structured plan that can be executed incrementally.",
    ])
    return "\n".join(lines)
```

### Step 3: Add TypeScript types

**`agent/portal/frontend/src/types/index.ts`**

Add:
```typescript
export interface CreateProjectPayload {
  name: string;
  description?: string;
  repo_owner?: string;
  repo_name?: string;
  default_branch?: string;
  auto_merge?: boolean;
}

export interface CreateRepoPayload {
  name: string;
  description?: string;
  private?: boolean;
}

export interface CreateRepoResult {
  owner: string;
  repo: string;
  full_name: string;
  clone_url: string;
  default_branch: string;
}

export interface KickoffResult {
  project_id: string;
  claude_task_id: string;
  mode: string;
  workspace: string;
}
```

### Step 4: Update hooks

**`agent/portal/frontend/src/hooks/useRepos.ts`**

Add `createRepo` function:
```typescript
export async function createRepo(payload: CreateRepoPayload): Promise<CreateRepoResult> {
  return api<CreateRepoResult>("/api/repos", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
```

**`agent/portal/frontend/src/hooks/useProjects.ts`**

Add utility functions:
```typescript
export async function createProject(payload: CreateProjectPayload): Promise<{ project_id: string }> {
  return api<{ project_id: string }>("/api/projects", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function kickoffProject(
  projectId: string,
  options: { mode: string; auto_push: boolean; description?: string }
): Promise<KickoffResult> {
  return api<KickoffResult>(`/api/projects/${projectId}/kickoff`, {
    method: "POST",
    body: JSON.stringify(options),
  });
}
```

### Step 5: Create `NewProjectModal.tsx`

A modal with the following sections:

**Form Fields:**
1. **Project Name** — text input (required)
2. **Description** — textarea (optional, used as the project goal for Claude)
3. **Repository** — radio group:
   - **Select existing repo** → searchable dropdown populated from `GET /api/repos`
   - **Create new repo** → shows name + private toggle inputs
   - **No repo** → skip repo linkage
4. **Execution Mode** — radio group:
   - **Plan first** (default) — fires `claude_code.run_task` in `mode: "plan"`, Claude creates PLAN.md
   - **Execute immediately** — fires in `mode: "execute"`, skips planning
5. **Auto-push** — checkbox toggle (default: on)

**Submit Flow:**
1. If "Create new repo" selected → call `createRepo()`, get `{owner, repo}`
2. Call `createProject()` with name, description, repo_owner, repo_name
3. Call `kickoffProject(projectId, {mode, auto_push, description})`
4. On success → navigate to `/projects/${projectId}` or `/tasks/${claudeTaskId}`
5. Show loading spinner during each step, error toast on failure

**UI Design:**
- Full-screen modal overlay with centered card (matching existing `bg-surface-light border border-border rounded-xl` patterns)
- Step indicator at top showing progress (1. Details → 2. Repository → 3. Options)
- Previous/Next navigation between steps
- Submit button on final step
- Close/cancel button

### Step 6: Update `ProjectsPage.tsx`

Add "New Project" button in the header:
```tsx
<button
  onClick={() => setShowNewProjectModal(true)}
  className="bg-accent hover:bg-accent/80 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
>
  <Plus size={16} />
  New Project
</button>
```

Mount the modal:
```tsx
{showNewProjectModal && (
  <NewProjectModal
    onClose={() => setShowNewProjectModal(false)}
    onCreated={(projectId) => {
      setShowNewProjectModal(false);
      refetch();
      navigate(`/projects/${projectId}`);
    }}
  />
)}
```

Also update the empty state to include the new project button:
```tsx
<button onClick={() => setShowNewProjectModal(true)} className="...">
  Create your first project
</button>
```

---

## Data Flow Diagram

```
User clicks "New Project"
        │
        ▼
  NewProjectModal renders
  ├── Step 1: Name + Description
  ├── Step 2: Repo selection
  │   ├── "Existing" → GET /api/repos → searchable dropdown
  │   ├── "New"      → name + private inputs
  │   └── "None"     → skip
  └── Step 3: Mode + Auto-push
        │
        ▼ (Submit)
  [If creating repo]
  POST /api/repos
  → git_platform.create_repo
  → returns {owner, repo}
        │
        ▼
  POST /api/projects
  → project_planner.create_project
  → returns {project_id}
        │
        ▼
  POST /api/projects/{id}/kickoff
  → project_planner.get_project (fetch details)
  → builds prompt
  → claude_code.run_task
  → project_planner.update_project (status → "active")
  → returns {project_id, claude_task_id}
        │
        ▼
  Navigate to /projects/{id}
```

---

## Edge Cases & Error Handling

1. **Repo creation fails** (name taken, permissions) — show error, let user retry or pick existing
2. **Project name taken** — `project_planner.create_project` returns error (unique constraint), show inline error
3. **Claude Code not available** — check `/api/tasks/health` before showing kickoff options; if unavailable, create project without kickoff and show info message
4. **No git credentials** — detect from repos endpoint error, show "configure credentials in Settings" link
5. **Kickoff fails after project created** — project still exists in "planning" status, user can retry kickoff from project detail page
6. **User cancels mid-flow** — if repo was created but project wasn't, that's fine (orphan repo is acceptable)

---

## Testing Checklist

- [ ] `git_platform.create_repo` works for GitHub (POST /user/repos)
- [ ] `POST /api/repos` portal endpoint creates repo and returns metadata
- [ ] `POST /api/projects/{id}/kickoff` creates claude task and updates project status
- [ ] Modal form validates required fields (name)
- [ ] Repo dropdown loads and filters correctly
- [ ] "Create new repo" flow creates repo then uses it for the project
- [ ] "No repo" flow creates project without repo linkage
- [ ] Plan mode generates appropriate planning prompt
- [ ] Execute mode uses `get_execution_plan` when tasks exist
- [ ] Navigation works after successful creation
- [ ] Error states display correctly for each step
- [ ] Loading states show during API calls
- [ ] Modal closes on cancel/escape

---

## Implementation Order

1. **git_platform `create_repo`** — backend module changes (base, github, bitbucket, manifest, tools, main)
2. **Portal `POST /api/repos`** — new endpoint in repos router
3. **Portal `POST /api/projects/{id}/kickoff`** — new endpoint in projects router
4. **TypeScript types** — add new interfaces
5. **Hook updates** — `createRepo`, `createProject`, `kickoffProject`
6. **`NewProjectModal.tsx`** — create the form component
7. **`ProjectsPage.tsx`** — add button + modal integration
