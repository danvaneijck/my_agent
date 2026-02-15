# Project Planner Module

Project planning, tracking, and autonomous execution. Manages the full lifecycle from design sessions to implemented features with Git-native tracking.

## Architecture

```
User ─── Design Session ───► create_project (design doc + phases + tasks)
                                      │
                    ┌─────────────────┼──────────────────┐
                    ▼                 ▼                   ▼
               Project            Phases              Tasks
            (planning→active)  (planned→in_progress)  (todo→doing→in_review→done)
                    │                                    │
                    └── repo_owner/repo_name ────────────┤
                                                         │
                    ┌────────────────────────────────────┘
                    ▼
         Autonomous Execution Flow:
         1. get_next_task(phase_id)
         2. update_task(status=doing)
         3. git_platform.create_issue(...)
         4. claude_code.run_task(prompt, repo_url, branch, auto_push=true)
         5. scheduler.add_job(poll task_status, on_complete=resume_conversation)
         6. [on resume] git_platform.create_pull_request(...)
         7. update_task(status=in_review, pr_number=N)
         8. Loop to step 1
```

## Data Model

### Projects
- Owned by a user, unique name per user
- Contains design document (markdown from planning session)
- Links to a GitHub repo (owner + name + default branch)
- `auto_merge` flag controls whether PRs are merged automatically after CI
- Status: `planning` → `active` → `paused` → `completed` → `archived`

### Phases
- Ordered milestones within a project
- Status: `planned` → `in_progress` → `completed`

### Tasks
- Individual implementable units within a phase
- Status: `todo` → `doing` → `in_review` → `done` | `failed`
- Tracks: branch_name, pr_number, issue_number, claude_task_id, error_message
- Branch auto-generated: `feature/{short_id}/{slugified-title}`

## Tools

| Tool | Permission | Description |
|------|-----------|-------------|
| `create_project` | user | Create project with optional phases and tasks |
| `update_project` | user | Update project fields |
| `get_project` | user | Get project with phases and task counts |
| `list_projects` | user | List projects with summary stats |
| `delete_project` | admin | Delete project cascade |
| `add_phase` | user | Add phase to project |
| `update_phase` | user | Update phase fields/status |
| `add_task` | user | Add task to phase |
| `bulk_add_tasks` | user | Add multiple tasks at once |
| `update_task` | user | Update task fields/status/git info |
| `get_task` | user | Get full task detail |
| `get_phase_tasks` | user | All tasks in a phase |
| `get_next_task` | user | Next todo task in a phase |
| `get_execution_plan` | user | Batch plan for all todo tasks across phases |
| `bulk_update_tasks` | user | Update multiple tasks at once |
| `get_project_status` | user | Project summary with counts |

## Planning Session Workflow

1. User has a design conversation with the agent
2. User says "save this as a project" or "create the project plan"
3. Agent calls `create_project` with:
   - Design document summarizing the conversation
   - Phases broken down from the design
   - Tasks within each phase with descriptions and acceptance criteria
4. Project starts in `planning` status
5. User reviews in portal or chat, adjusts as needed
6. User says "implement phase 1" to begin autonomous execution

## Autonomous Execution

The LLM orchestrates using existing modules — the project planner only manages state.

### Sequential Flow (per phase)
1. `get_next_task(phase_id)` → returns next `todo` task
2. `update_task(status="doing")` → marks it in progress BEFORE starting work
3. `claude_code.run_task(prompt, repo_url, branch, auto_push=true)` → starts coding
4. `scheduler.add_job(poll task_status, on_complete="resume_conversation")` → monitors
5. On resume: `update_task(status="done")` → marks completion
6. For subsequent tasks in the same phase: prefer `claude_code.continue_task` on the
   previous workspace (preserves file context and conversation history) over a fresh
   `run_task`. Only start fresh when previous work has been pushed and context is exhausted.
7. Repeat from step 1 until no more `todo` tasks

### Workspace Continuity

- **Plan → Execute**: Always use `continue_task(mode="execute", auto_push=true)` on the
  planning task's workspace. Never create a new `run_task` for implementation.
- **Same phase, multiple tasks**: Use `continue_task` to keep working in the same workspace.
  The prompt can instruct the agent to switch branches for the new task.
- **New phase after push**: Safe to use fresh `run_task` since previous code is in the remote.
- **`auto_push=true`**: Always set this so changes are pushed after each task completes.

### Batch Execution

For simpler projects, or when the user requests implementing multiple phases at once, use batch mode to run everything in a single `claude_code` task:

1. `get_execution_plan(project_id)` — gathers all todo tasks across all phases, returns a structured plan with the design document and a pre-built prompt
2. `bulk_update_tasks(task_ids=todo_task_ids, status="doing")` — marks all tasks in-progress
3. `claude_code.run_task(prompt=plan.prompt, repo_url, branch=plan.branch, source_branch=plan.source_branch, auto_push=true)` — single container handles everything
4. `scheduler.add_job(poll task_status, on_complete="resume_conversation")` — monitor
5. On completion: `bulk_update_tasks(task_ids, status="done", claude_task_id=...)` — mark all done
6. Optionally create a single PR from the project branch into the default branch

Use `phase_ids` parameter on `get_execution_plan` to limit to specific phases if needed.

### Error Handling
- Task failure: mark as `failed` with error_message, notify user, skip to next
- Timeout: mark as `failed`, user can retry via `claude_code.continue_task`
- Merge conflicts: notify user for manual resolution
- Mid-execution plan change: cancel workflow via `scheduler.cancel_workflow`

### PR Merge (configurable)
- `auto_merge=false` (default): PRs stay `in_review` until manually merged
- `auto_merge=true`: agent polls CI status, merges after passing

## Portal — New Project Flow

The Projects portal page includes a "New Project" button that opens a multi-step creation modal. This is the primary way to create projects from the web UI.

### Modal Steps

1. **Details** — project name (required) and description (used as the project goal for Claude)
2. **Repository** — choose one of:
   - **Existing repo** — searchable dropdown fetched from `GET /api/repos` (`git_platform.list_repos`)
   - **Create new repo** — name + private toggle, calls `POST /api/repos` (`git_platform.create_repo`)
   - **No repo** — skip repo linkage entirely
3. **Options** — execution mode (plan first / execute immediately) and auto-push toggle

### Submit Flow

```
[Create repo]  POST /api/repos  →  git_platform.create_repo
       │                              (only if "Create new" selected)
       ▼
[Create project]  POST /api/projects  →  project_planner.create_project
       │                                   (links repo_owner/repo_name if set)
       ▼
[Kickoff]  POST /api/projects/{id}/kickoff  →  builds prompt + claude_code.run_task
       │                                         + project_planner.update_project(status="active")
       ▼
Navigate to /projects/{id}
```

### Kickoff Endpoint (`POST /api/projects/{id}/kickoff`)

Accepts:
- `mode` — `"plan"` (default) or `"execute"`
- `auto_push` — push branch to remote on completion (default `true`)
- `timeout` — task timeout in seconds (default `1800`)
- `description` — optional project goal passed to the prompt

Behaviour:
- **Plan mode**: builds a prompt asking Claude to analyze the repo, create a design document, and break the project into phases and tasks. The claude_code task runs in `mode: "plan"` and ends in `awaiting_input` status with a PLAN.md.
- **Execute mode**: calls `get_execution_plan` to gather existing todo tasks. If tasks exist, uses the batch prompt. If no tasks exist, falls back to plan mode.
- Creates a working branch named `project/{slugified-name}` branched from the project's default branch.
- Updates the project status to `active` after launching the task.

### Related Endpoints

| Endpoint | Module | Description |
|----------|--------|-------------|
| `POST /api/repos` | git_platform | Create a new GitHub/Bitbucket repo |
| `POST /api/projects` | project_planner | Create project record |
| `POST /api/projects/{id}/kickoff` | project_planner + claude_code | Launch Claude task for the project |

## Portal Pages

- `/projects` — project list with status badges, progress bars, and "New Project" button
- `/projects/:id` — project detail with phases and overall progress
- `/projects/:id/phases/:phaseId` — kanban board (todo/doing/in_review/done columns)
- `/projects/:id/tasks/:taskId` — task detail with git links and error info

## Context Builder Integration

Active projects are automatically injected into the agent's system prompt:
```
Active projects:
- "My App" (active), 3/8 tasks done, 2 in progress, repo: user/my-app
```

## Infrastructure

- **Database**: PostgreSQL (3 tables: projects, project_phases, project_tasks)
- **Dependencies**: FastAPI, SQLAlchemy, asyncpg, structlog
- **Docker**: `project-planner` service on `agent-net`
- **No external APIs**: pure state management, delegates execution to other modules
