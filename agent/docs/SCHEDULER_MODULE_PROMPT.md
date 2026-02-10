# Scheduler Module — Implementation Prompt

Feed this entire prompt to Claude to implement the scheduler module.

---

## Context

You are working on an AI agent system. The codebase lives at `/home/user/my_agent/agent/`. Read `CLAUDE.md` at the project root for full architecture docs before starting.

The system is a microservices architecture: a core orchestrator (FastAPI) routes messages from communication bots (Discord/Telegram/Slack) to tool modules. Modules are independent FastAPI services discovered via `GET /manifest` and called via `POST /execute`.

**The problem**: Long-running tasks (specifically `claude_code.run_task`) complete asynchronously. The orchestrator returns immediately, and the user must manually prompt "check my task" to see results. There is no mechanism for the system to proactively notify the user when something finishes.

**The solution**: A `scheduler` module that polls for job completion and sends proactive notifications back to the user's channel via Redis pub/sub.

## Design Decisions (already made — do not change)

1. **Persistence**: Jobs are stored in PostgreSQL so they survive container restarts.
2. **Callback depth**: Limited. The scheduler NEVER auto-executes follow-up tools. It always messages the user to confirm next steps (e.g., "Your task finished. Reply to deploy it.").
3. **Notification transport**: Redis pub/sub. The scheduler publishes to `notifications:{platform}` channels. Bots subscribe and send the message to the appropriate platform channel.
4. **No agent loop re-entry**: Callbacks are plain text messages, not re-processed through the LLM. This keeps costs and complexity down.

## What to Implement

There are 4 pieces of work, in this order:

### Piece 1: Shared Schema + DB Model

#### 1a. Notification schema — `agent/shared/shared/schemas/notifications.py` (new file)

```python
"""Notification schemas for proactive messages via Redis pub/sub."""

from __future__ import annotations
from pydantic import BaseModel


class Notification(BaseModel):
    """A proactive message to send to a user on a specific platform channel."""
    platform: str                          # "discord" | "telegram" | "slack"
    platform_channel_id: str               # where to send the message
    platform_thread_id: str | None = None  # optional thread
    content: str                           # the message text
    user_id: str | None = None             # internal user UUID (for logging)
    job_id: str | None = None              # scheduler job ID that triggered this
```

#### 1b. DB model — `agent/shared/shared/models/scheduled_job.py` (new file)

Create a `ScheduledJob` SQLAlchemy model with this schema:

```
scheduled_jobs
  id                  UUID PK (default uuid4)
  user_id             UUID FK → users.id
  conversation_id     UUID FK → conversations.id (nullable)

  # Where to send the notification
  platform            str          — "discord" | "telegram" | "slack"
  platform_channel_id str
  platform_thread_id  str | null

  # What to check
  job_type            str          — "poll_module" | "delay" | "poll_url"
  check_config        JSON         — see below for structure per job_type

  # Schedule
  interval_seconds    int          — how often to poll (default 30)
  max_attempts        int          — max polls before marking failed (default 120 = 1 hour at 30s)
  attempts            int          — current attempt count (default 0)

  # What to say when done
  on_success_message  Text         — message template sent on success
  on_failure_message  Text | null  — message sent if max_attempts exceeded

  # Lifecycle
  status              str          — "active" | "completed" | "failed" | "cancelled"
  next_run_at         DateTime(tz) — when to next check
  created_at          DateTime(tz)
  completed_at        DateTime(tz) | null
```

**Important**: Use `mapped_column(DateTime(timezone=True))` for all datetime fields (asyncpg requirement). Use `default=lambda: datetime.now(timezone.utc)` for created_at. Use `mapped_column(JSON)` for check_config (SQLAlchemy's `JSON` type maps to PostgreSQL `jsonb`).

**check_config structure by job_type**:

For `poll_module` (the primary use case — checking claude_code task completion):
```json
{
  "module": "claude_code",
  "tool": "claude_code.task_status",
  "args": {"task_id": "abc123"},
  "success_field": "status",
  "success_values": ["completed", "failed"]
}
```

For `delay` (simple timer — notify after N seconds):
```json
{
  "delay_seconds": 300
}
```

For `poll_url` (HTTP health check):
```json
{
  "url": "http://example.com/health",
  "method": "GET",
  "expected_status": 200
}
```

#### 1c. Register the model

Add to `agent/shared/shared/models/__init__.py`:
```python
from shared.models.scheduled_job import ScheduledJob
```
And add `"ScheduledJob"` to `__all__`.

#### 1d. Alembic migration

Generate with: `alembic revision --autogenerate -m "add scheduled_jobs table"`

The migration should be generated from within the core container (`make shell`) where alembic is configured.

---

### Piece 2: Scheduler Module

Create `agent/modules/scheduler/` with the standard module structure.

#### 2a. `agent/modules/scheduler/__init__.py` — empty

#### 2b. `agent/modules/scheduler/manifest.py`

Define 3 tools:

**`scheduler.add_job`** (permission: `admin`)
- `job_type` (string, required, enum: ["poll_module", "delay", "poll_url"])
- `check_config` (object, required) — JSON config for the check (structure depends on job_type)
- `on_success_message` (string, required) — what to tell the user when the condition is met
- `on_failure_message` (string, required=False) — what to tell the user if it times out
- `interval_seconds` (integer, required=False) — polling interval, default 30
- `max_attempts` (integer, required=False) — max checks, default 120
- `user_id` (string, required=False) — injected by orchestrator

Description should explain that the job will monitor a condition and proactively message the user when it completes. Emphasize that this is for fire-and-forget monitoring — the user does not need to check back manually.

**`scheduler.list_jobs`** (permission: `admin`)
- `status_filter` (string, required=False, enum: ["active", "completed", "failed", "cancelled"])
- `user_id` (string, required=False)

**`scheduler.cancel_job`** (permission: `admin`)
- `job_id` (string, required) — UUID of the job to cancel
- `user_id` (string, required=False)

#### 2c. `agent/modules/scheduler/tools.py`

```python
class SchedulerTools:
    def __init__(self, session_factory, settings):
        self.session_factory = session_factory
        self.settings = settings
```

**`add_job` method**:
- Receives `job_type`, `check_config`, `on_success_message`, plus optional params
- IMPORTANT: Also receives `platform`, `platform_channel_id`, `platform_thread_id` from the ToolCall. These must be injected by the orchestrator (see Piece 4 below for the context injection approach). For now, accept them as optional parameters with sensible handling if missing.
- Creates a `ScheduledJob` row in the DB with status="active" and `next_run_at = now + interval_seconds`
- Returns `{"job_id": str(job.id), "status": "active", "message": "Job scheduled. I'll notify you when the condition is met."}`

**`list_jobs` method**:
- Queries ScheduledJob filtered by user_id and optional status_filter
- Returns list of job summaries (id, job_type, status, attempts, created_at, next_run_at)

**`cancel_job` method**:
- Finds job by ID, verifies it belongs to the user, sets status="cancelled"
- Returns confirmation

#### 2d. `agent/modules/scheduler/worker.py`

This is the background polling loop. It runs as an asyncio task started on FastAPI startup.

```python
async def scheduler_loop(session_factory, settings, redis_url: str):
    """Background loop that processes active scheduled jobs."""
```

**Loop logic** (runs every 10 seconds):
1. Query all `ScheduledJob` rows where `status = 'active'` AND `next_run_at <= now`
2. For each due job, call `_evaluate_job(job, session, settings, redis)`
3. Commit changes after each job evaluation

**`_evaluate_job` logic**:
1. Increment `job.attempts`
2. Based on `job.job_type`:

   **poll_module**:
   - Extract module URL from `settings.module_services[check_config["module"]]`
   - POST to `{module_url}/execute` with a `ToolCall(tool_name=check_config["tool"], arguments=check_config["args"])`
   - Parse the `ToolResult` response
   - Check if `result[check_config["success_field"]]` is in `check_config["success_values"]`
   - If matched: job is done (see notification step below)
   - If the result shows the task failed (e.g. status="failed"), also mark done but use a failure-aware message

   **delay**:
   - If `attempts * interval_seconds >= check_config["delay_seconds"]`: job is done

   **poll_url**:
   - HTTP GET/POST to the URL
   - Check response status code matches `expected_status`

3. **If condition met**:
   - Set `job.status = "completed"`, `job.completed_at = now`
   - Build the notification message. For `poll_module`, interpolate the actual result into `on_success_message` if it contains `{result}` placeholder. Also, if the polled task failed, use `on_failure_message` or append the error.
   - Publish a `Notification` to Redis channel `notifications:{job.platform}` (JSON-serialized)

4. **If max_attempts exceeded**:
   - Set `job.status = "failed"`, `job.completed_at = now`
   - Publish notification with `on_failure_message` or a default "Job timed out" message

5. **Otherwise** (condition not met, attempts remaining):
   - Set `job.next_run_at = now + interval_seconds`

**Redis publishing**:
```python
import redis.asyncio as aioredis

redis = aioredis.from_url(redis_url)
await redis.publish(f"notifications:{job.platform}", notification.model_dump_json())
```

**Error handling**: Wrap each job evaluation in try/except. If a check fails (network error, module down), log the error, increment attempts, and set next_run_at. Do NOT mark the job as failed for transient errors — only when max_attempts is exceeded.

#### 2e. `agent/modules/scheduler/main.py`

Standard FastAPI app with `/manifest`, `/execute`, `/health`.

On startup:
1. Initialize `SchedulerTools` with session_factory and settings
2. Start the background worker: `asyncio.create_task(scheduler_loop(session_factory, settings, settings.redis_url))`

On shutdown:
1. Cancel the background task

The `/execute` endpoint routes to the 3 tools (add_job, list_jobs, cancel_job).

#### 2f. `agent/modules/scheduler/Dockerfile`

Same pattern as knowledge module. Needs: `sqlalchemy`, `asyncpg`, `httpx`, `redis[hiredis]` (for async Redis pub/sub).

#### 2g. `agent/modules/scheduler/requirements.txt`

```
fastapi>=0.109
uvicorn[standard]>=0.27
structlog>=24.1
httpx>=0.26
pydantic>=2.5
pydantic-settings>=2.1
sqlalchemy>=2.0
asyncpg>=0.29
redis[hiredis]>=5.0
```

---

### Piece 3: Bot Changes (Redis Subscriber)

Each bot needs a background task that subscribes to `notifications:{platform}` on Redis and sends messages to the specified channel.

#### Discord bot — `agent/comms/discord_bot/bot.py`

Add a method to `AgentDiscordBot`:

```python
async def _notification_listener(self):
    """Subscribe to Redis notifications and send proactive messages."""
    import redis.asyncio as aioredis
    r = aioredis.from_url(self.settings.redis_url)
    pubsub = r.pubsub()
    await pubsub.subscribe("notifications:discord")

    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            from shared.schemas.notifications import Notification
            notification = Notification.model_validate_json(message["data"])
            channel = self.get_channel(int(notification.platform_channel_id))
            if channel is None:
                channel = await self.fetch_channel(int(notification.platform_channel_id))
            if channel:
                await channel.send(notification.content)
        except Exception as e:
            logger.error("notification_send_failed", error=str(e))
```

Start this in `on_ready`:
```python
async def on_ready(self):
    logger.info("discord_bot_ready", user=str(self.user))
    asyncio.create_task(self._notification_listener())
```

**Do the same for Telegram and Slack bots**, adjusting:
- Telegram: subscribe to `notifications:telegram`, use `bot.send_message(chat_id=notification.platform_channel_id, text=notification.content)`
- Slack: subscribe to `notifications:slack`, use `client.chat_postMessage(channel=notification.platform_channel_id, text=notification.content)`

Add `redis[hiredis]>=5.0` to each bot's `requirements.txt` if not already present.

---

### Piece 4: Orchestrator Changes

The orchestrator needs to pass conversation context (platform, channel_id, thread_id) to the scheduler so it knows where to send notifications.

#### 4a. Inject conversation context into tool calls

In `agent/core/orchestrator/agent_loop.py`, when the agent loop executes a tool call for the scheduler module, it needs to inject the conversation's platform routing info into the tool arguments.

Find where tool calls are executed (the section that POSTs to module `/execute` endpoints). When the tool belongs to the `scheduler` module, add these fields to `call.arguments`:
- `platform` — from the `IncomingMessage` or resolved conversation
- `platform_channel_id` — from the conversation
- `platform_thread_id` — from the conversation (may be null)

This is analogous to how `user_id` is already injected into `ToolCall`. The scheduler tools accept these as parameters.

The cleanest approach: in the tool execution section, detect if the tool name starts with `scheduler.` and inject the context:
```python
if call.tool_name.startswith("scheduler."):
    call.arguments["platform"] = conversation.platform
    call.arguments["platform_channel_id"] = conversation.platform_channel_id
    call.arguments["platform_thread_id"] = conversation.platform_thread_id
```

#### 4b. Register the module

In `agent/shared/shared/config.py`, add to `module_services`:
```python
"scheduler": "http://scheduler:8000",
```

#### 4c. Docker Compose

In `agent/docker-compose.yml`, add:
```yaml
  scheduler:
    build:
      context: .
      dockerfile: modules/scheduler/Dockerfile
    env_file: .env
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_started
    networks:
      - agent-net
    restart: unless-stopped
```

---

### Piece 5: LLM Integration — Teach the Agent to Use It

The orchestrator's agent loop needs to know WHEN to schedule a job. This happens naturally through the LLM's tool selection, but the system prompt should hint at the pattern.

In the default persona's system prompt (or in the context builder), add guidance like:

> When you submit a long-running task (like claude_code.run_task), use scheduler.add_job to monitor it so the user is notified when it completes. Do not ask the user to check back manually.

This ensures the LLM automatically pairs `claude_code.run_task` with `scheduler.add_job` in the same agent loop iteration.

---

## Concrete Example: The Full Flow

1. User says: "Build me a React dashboard"
2. LLM calls `claude_code.run_task(prompt="Build a React dashboard...")` → gets `{task_id: "a1b2c3", workspace: "/tmp/claude_tasks/a1b2c3"}`
3. LLM calls `scheduler.add_job`:
   ```json
   {
     "job_type": "poll_module",
     "check_config": {
       "module": "claude_code",
       "tool": "claude_code.task_status",
       "args": {"task_id": "a1b2c3"},
       "success_field": "status",
       "success_values": ["completed", "failed"]
     },
     "interval_seconds": 30,
     "max_attempts": 120,
     "on_success_message": "Your Claude Code task has finished! The project is ready at `/tmp/claude_tasks/a1b2c3`. Would you like me to deploy it?",
     "on_failure_message": "Your Claude Code task timed out after 60 minutes. Use `claude_code.task_status` with task_id `a1b2c3` to check what happened."
   }
   ```
   (Orchestrator injects `platform`, `platform_channel_id`, `platform_thread_id`, `user_id`)
4. LLM replies to user: "I've started building your React dashboard. I'll let you know when it's done."
5. Scheduler polls `claude_code.task_status` every 30 seconds
6. After ~5 minutes, task completes → scheduler publishes `Notification` to Redis `notifications:discord`
7. Discord bot receives notification → sends message to the channel: "Your Claude Code task has finished! The project is ready at `/tmp/claude_tasks/a1b2c3`. Would you like me to deploy it?"
8. User replies: "Yes, deploy it" → normal flow resumes through orchestrator

---

## Implementation Order

1. Create `agent/shared/shared/schemas/notifications.py`
2. Create `agent/shared/shared/models/scheduled_job.py`
3. Update `agent/shared/shared/models/__init__.py`
4. Generate and apply Alembic migration
5. Create the full `agent/modules/scheduler/` directory with all files
6. Update `agent/shared/shared/config.py` — add scheduler to `module_services`
7. Update `agent/docker-compose.yml` — add scheduler service
8. Update `agent/core/orchestrator/agent_loop.py` — inject conversation context for scheduler tool calls
9. Update each bot (`discord_bot/bot.py`, `telegram_bot/bot.py`, `slack_bot/bot.py`) — add Redis notification subscriber
10. Add `redis[hiredis]>=5.0` to each bot's `requirements.txt`
11. Build and test: `make build-module M=scheduler && make up && make refresh-tools`

## Files to Read First

Before writing any code, read these files to match existing patterns exactly:
- `CLAUDE.md` (project root) — full architecture reference
- `agent/modules/knowledge/main.py` — reference module main.py pattern
- `agent/modules/knowledge/manifest.py` — reference manifest pattern
- `agent/modules/knowledge/tools.py` — reference tools pattern with DB access
- `agent/modules/claude_code/tools.py` — understand the task_status response format (this is what you'll be polling)
- `agent/shared/shared/models/conversation.py` — reference model pattern
- `agent/shared/shared/schemas/tools.py` — ToolCall, ToolResult schemas
- `agent/shared/shared/config.py` — settings and module_services
- `agent/core/orchestrator/agent_loop.py` — where to inject conversation context
- `agent/core/main.py` — understand startup pattern (for the background loop reference)
- `agent/comms/discord_bot/bot.py` — where to add notification listener
- `agent/docker-compose.yml` — service definition patterns

## Important Constraints

- Python 3.12, async throughout
- Use `DateTime(timezone=True)` on all datetime model columns (asyncpg requirement)
- Use `session.commit()` not `session.flush()` for cross-container DB visibility
- Do NOT create `__init__.py` in the alembic directory
- Tool names MUST follow `module_name.tool_name` pattern
- Docker service name uses hyphens, Python module uses underscores
- Add `redis[hiredis]>=5.0` to any service that uses Redis pub/sub (bots + scheduler)
- The scheduler should gracefully handle modules being temporarily unreachable (retry on next interval, don't fail the job)
- Keep the worker loop lightweight — query only due jobs, process them sequentially, sleep 10s between cycles
