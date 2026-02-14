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
2. `update_task(status="doing")` → marks it in progress
3. `git_platform.create_issue(title, body)` → creates GitHub issue
4. `update_task(issue_number=N)` → tracks issue
5. `claude_code.run_task(prompt, repo_url, branch, auto_push=true)` → starts coding
6. `scheduler.add_job(poll task_status, on_complete="resume_conversation")` → monitors
7. On resume: `git_platform.create_pull_request(head=branch, base=main)`
8. `update_task(status="in_review", pr_number=N)` → tracks PR
9. Repeat from step 1 until no more `todo` tasks

### Error Handling
- Task failure: mark as `failed` with error_message, notify user, skip to next
- Timeout: mark as `failed`, user can retry via `claude_code.continue_task`
- Merge conflicts: notify user for manual resolution
- Mid-execution plan change: cancel workflow via `scheduler.cancel_workflow`

### PR Merge (configurable)
- `auto_merge=false` (default): PRs stay `in_review` until manually merged
- `auto_merge=true`: agent polls CI status, merges after passing

## Portal Pages

- `/projects` — project list with status badges and progress bars
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
