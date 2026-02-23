# crew

Multi-agent crew sessions — coordinate 2-6 Claude Code agents working on a project in parallel with shared context and automated merge integration. Tasks are topologically sorted into parallelizable waves via dependency graph analysis.

## How It Works

```
User creates crew session (linked to a project with tasks)
        │
  crew module analyzes task dependencies
  builds dependency graph → computes waves (topological sort)
        │
  Wave 0: dispatch up to max_agents in parallel
  ┌─────────────────────────────────────────────┐
  │  Agent A (backend)    Agent B (frontend)     │
  │  branch: crew/a       branch: crew/b         │
  │  ┌─────────────────────────────────────────┐ │
  │  │  Shared Context Board (Redis + DB)      │ │
  │  │  "POST /api/users → {id, name, email}"  │ │
  │  └─────────────────────────────────────────┘ │
  └─────────────────────────────────────────────┘
        │ scheduler polls each agent
        ▼
  Agent A completes → merge crew/a → integration branch
  Agent B completes → merge crew/b → integration branch
        │ (conflict? → merge resolution via claude_code)
        ▼
  Wave 1: dispatch agents for dependent tasks
        │
        ▼
  All waves done → final PR → notify user
```

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `crew.create_session` | Create a crew session linked to a project | admin |
| `crew.start_session` | Begin wave dispatch | admin |
| `crew.get_session` | Full session detail with members + context | user |
| `crew.list_sessions` | List user's crew sessions | user |
| `crew.pause_session` | Pause dispatch (running agents finish) | admin |
| `crew.resume_session` | Resume from pause | admin |
| `crew.cancel_session` | Cancel all agents, mark session failed | admin |
| `crew.post_context` | Add entry to shared context board | admin |
| `crew.get_context_board` | Get all context entries | user |
| `crew.advance_session` | Called by scheduler on member completion | admin |

## Tool Details

### `crew.create_session`

Creates a new crew session linked to an existing project. Analyzes task dependencies via `depends_on` fields on `ProjectTask` and computes execution waves.

**Parameters:**
- **project_id** (required) — UUID of the project to run as a crew
- **name** (optional) — session name; defaults to `"Crew: {project.name}"`
- **max_agents** (optional) — max concurrent agents per wave (default 4, max 6)
- **role_assignments** (optional) — map of `task_id → role` (architect|backend|frontend|tester|reviewer)
- **auto_push** (optional) — auto-push branches after completion (default true)
- **timeout** (optional) — timeout per agent in seconds (default 1800)

### `crew.start_session`

Starts a configuring or paused session. Sets status to "running", creates a `workflow_id`, and dispatches wave 0.

**Parameters:**
- **session_id** (required) — crew session ID

### `crew.get_session`

Returns full session detail including all members, context board entries, and progress summary.

**Parameters:**
- **session_id** (required) — crew session ID

### `crew.list_sessions`

Lists crew sessions for the current user, ordered by most recently updated.

**Parameters:**
- **status_filter** (optional) — configuring|running|paused|completed|failed

### `crew.pause_session` / `crew.resume_session`

Pause stops new wave dispatch; currently working agents finish their tasks. Resume re-dispatches the current wave.

### `crew.cancel_session`

Cancels all working/merging members via `claude_code.cancel_task`, marks session as failed.

### `crew.post_context`

Posts an entry to the shared context board. All agents in subsequent waves see these entries in their prompts.

**Parameters:**
- **session_id** (required)
- **entry_type** (required) — decision|api_contract|interface|note|blocker
- **title** (required) — short title
- **content** (required) — full content

### `crew.advance_session`

Called by the scheduler via `on_complete="resume_conversation"` when a member's claude_code task finishes. Handles:
1. Check claude_code task status
2. If completed: merge member branch → integration branch
3. Update member and project task status
4. Post merge result or conflict to context board
5. If all members in wave are done: increment wave, dispatch next
6. If all waves done: create final PR, mark session completed

## Session Lifecycle

```
configuring → running → completed
                │  ↑
                ↓  │
              paused
                │
                ↓
              failed (cancel or all agents fail)
```

- **configuring**: session created, waves computed, awaiting start
- **running**: agents are being dispatched and monitored
- **paused**: no new dispatch; working agents finish naturally
- **completed**: all waves done, final PR created
- **failed**: cancelled or unrecoverable error

## Wave Computation

Tasks are topologically sorted into waves based on `depends_on` fields:

- **Wave 0**: tasks with no dependencies
- **Wave N**: tasks whose dependencies are all satisfied in waves < N
- Cycle detection: raises `ValueError` if circular dependencies exist
- Unknown dependency IDs are logged and ignored (graceful degradation)

Each wave dispatches up to `max_agents` tasks in parallel. When all members in a wave complete, the next wave is dispatched.

## Git Branch Strategy

Each crew member works on an isolated branch:
```
crew/{session_id[:8]}/wave-{N}/task-{i}
```

All branches merge into a shared integration branch:
```
crew/{project_id[:8]}/integration
```

The integration branch is created from the project's `source_branch` (default: `main`). On session completion, a PR is created from integration → source branch via `git_platform.create_pull_request`.

### Merge Handling

After a member completes, the coordinator spawns a short claude_code task to merge the member's branch into the integration branch. If there are merge conflicts, the claude_code agent resolves them. Merge results (success or conflict) are posted to the context board.

## Shared Context Board

The context board is a persistent feed of entries that all agents in subsequent waves see in their prompts. Entry types:

| Type | Purpose |
|------|---------|
| `decision` | Architectural or design decisions |
| `api_contract` | API endpoint specs, request/response schemas |
| `interface` | Interface or type definitions |
| `note` | General notes and information |
| `blocker` | Issues blocking progress |
| `merge_result` | Auto-posted after branch merges |

Users can also post entries via the portal UI or `crew.post_context` tool.

## Agent Roles

Optional role assignments influence the agent's system prompt:

| Role | Focus |
|------|-------|
| `architect` | System design, interfaces, API contracts |
| `backend` | Server-side logic, APIs, data models |
| `frontend` | UI components, state management, integration |
| `tester` | Unit/integration tests, edge cases, coverage |
| `reviewer` | Code review, bug finding, consistency |

Role prompts instruct agents to post relevant context (API contracts, interface definitions) to the shared board.

## Scheduler Integration

Each crew member gets its own scheduler job with a **unique per-member `workflow_id`** to avoid the sibling cancellation behavior (scheduler cancels all jobs sharing a workflow_id when one fails). The job polls `claude_code.task_status` every 30 seconds, up to 240 attempts (~2 hours).

```
scheduler.add_job:
  job_type: poll_module
  check_config:
    module: claude_code
    tool: claude_code.task_status
    args: {task_id: <member's claude_task_id>}
    success_field: status
    success_values: [completed, failed, timed_out, cancelled]
  on_complete: resume_conversation
  workflow_id: <unique per member>
  interval_seconds: 30
  max_attempts: 240
```

On completion, the scheduler's `resume_conversation` calls core `/continue`, which invokes `crew.advance_session` with the member details.

## Real-Time Events

The coordinator publishes events to Redis pub/sub on `crew:{session_id}:events`:

| Event | When |
|-------|------|
| `member_started` | Agent dispatched for a task |
| `member_merging` | Agent completed, merge in progress |
| `member_completed` | Member done (success or failure) |
| `wave_dispatched` | New wave of agents launched |
| `wave_completed` | All members in a wave finished |
| `session_paused` | Session paused |
| `session_resumed` | Session resumed |
| `session_cancelled` | Session cancelled |
| `session_completed` | All waves done |
| `context_posted` | New context board entry |

The portal subscribes to these via WebSocket at `/ws/crews/{session_id}`.

## Portal Integration

- **List page**: `/crews` — grid of crew sessions with status filter
- **Detail page**: `/crews/:sessionId` — agent timeline, context board, dependency graph, events feed
- **API routes**: `agent/portal/routers/crews.py` proxies to the crew module
- **WebSocket**: `/ws/crews/{session_id}` streams Redis pub/sub events to the frontend
- **Project integration**: "Run with Crew" button on project detail page via `POST /api/projects/{project_id}/start-crew`

## Database

- **Model:** `CrewSession` (`agent/shared/shared/models/crew_session.py`)
- **Model:** `CrewMember` (`agent/shared/shared/models/crew_member.py`)
- **Model:** `CrewContextEntry` (`agent/shared/shared/models/crew_context_entry.py`)
- **Migration:** `agent/alembic/versions/021_add_crew_tables_and_task_dependencies.py`
- **Related:** `ProjectTask.depends_on` (JSON column, list of task UUID strings)

## Key Files

- `agent/modules/crew/manifest.py` — tool definitions
- `agent/modules/crew/tools.py` — CrewTools class (tool implementations)
- `agent/modules/crew/coordinator.py` — wave dispatch, merge integration, member lifecycle
- `agent/modules/crew/waves.py` — topological sort, wave computation
- `agent/modules/crew/prompts.py` — role-based prompt builder with context injection
- `agent/modules/crew/main.py` — FastAPI app
- `agent/portal/routers/crews.py` — portal API routes
- `agent/portal/frontend/src/pages/CrewsPage.tsx` — list page
- `agent/portal/frontend/src/pages/CrewDetailPage.tsx` — detail dashboard
- `agent/portal/frontend/src/hooks/useCrews.ts` — data fetching + CRUD
- `agent/portal/frontend/src/hooks/useCrewSession.ts` — session detail with polling
- `agent/portal/frontend/src/hooks/useCrewEvents.ts` — WebSocket events hook
