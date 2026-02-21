# scheduler

Background job scheduler for monitoring long-running tasks and running recurring jobs. Supports simple notifications, workflow chaining via `resume_conversation`, cron schedules, and webhook triggers.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `scheduler.add_job` | Schedule a background monitoring job | admin |
| `scheduler.list_jobs` | List jobs, optionally filtered by status/workflow | user |
| `scheduler.cancel_job` | Cancel an active job by ID | user |
| `scheduler.cancel_workflow` | Cancel all jobs in a workflow | admin |
| `scheduler.create_workflow` | Create a named workflow for grouping jobs | admin |
| `scheduler.get_workflow_status` | Get overall workflow status + job summaries | user |
| `scheduler.list_workflows` | List named workflows | user |

## Job Types

| Type | Behaviour |
|------|-----------|
| `poll_module` | Calls a module tool repeatedly; fires when a field matches a condition |
| `delay` | Fires after a wall-clock delay (uses `created_at`, not attempt count) |
| `poll_url` | Fires when an HTTP endpoint returns the expected status code and/or JSON body field |
| `cron` | Fires on a recurring cron schedule; stays active between runs |
| `webhook` | Fires when an external system POSTs to the returned `webhook_url` |

## Completion Modes

### `on_complete="notify"` (default)
Sends a message to the user via Redis pub/sub on the `notifications:{platform}` channel. The bot picks it up and delivers to the original channel/thread.

### `on_complete="resume_conversation"`
Calls core `/continue` endpoint to re-enter the agent loop. The LLM sees the `on_success_message` (with placeholders replaced) and can decide next steps — e.g. calling `deployer.deploy`. Falls back to plain notification if `/continue` fails.

## Tool Details

### `scheduler.add_job`

**Required parameters:**
- **job_type** — `poll_module`, `delay`, `poll_url`, `cron`, or `webhook`
- **check_config** — condition configuration (see below)
- **on_success_message** — message when condition is met; supports `{result}`, `{result.field}`, `{result.nested.field}`, `{job_id}`, `{workflow_id}` placeholders

**Optional parameters:**
- **on_failure_message** — message if job times out or expires
- **on_complete** — `notify` (default) or `resume_conversation`
- **workflow_id** — UUID to group related jobs (creates a named workflow with `create_workflow`)
- **name** — human-readable label (shown in `list_jobs`)
- **description** — longer description of what this job monitors
- **interval_seconds** — polling interval in seconds (default 30; not used for cron)
- **max_attempts** — max checks before failing (default 120 = ~1 hour; not for cron)
- **max_runs** — for cron: max number of fires before auto-completing (omit for indefinite)
- **expires_at** — ISO 8601 datetime after which the job is treated as failed (alternative to max_attempts)

### `check_config` by job type

**poll_module:**
```json
{
  "module": "claude_code",
  "tool": "claude_code.task_status",
  "args": {"task_id": "abc123"},
  "success_field": "status",
  "success_values": ["completed", "failed"],
  "success_operator": "in",
  "result_summary_fields": ["task_id", "status", "error"]
}
```

- `success_field` supports dot-paths: `"phase.status"`, `"result.code"`
- `success_operator`: `in` (default), `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `contains`
- When `success_operator` is not `in`, use `success_value` (single target) instead of `success_values`
- `result_summary_fields` overrides the default set of keys shown in `{result}` summary

**delay:**
```json
{"delay_seconds": 300}
```
Uses wall-clock time from `created_at`, not `attempts × interval_seconds`.

**poll_url:**
```json
{
  "url": "http://my-app/health",
  "method": "GET",
  "expected_status": 200,
  "response_field": "status",
  "response_value": "ok",
  "response_operator": "eq"
}
```
`response_field` supports dot-paths. `response_operator` uses the same set as `success_operator`.

**cron:**
```json
{"cron_expr": "0 8 * * 1-5", "timezone": "Australia/Sydney"}
```
Standard 5-field cron expressions. `timezone` defaults to `UTC`.

**webhook:**
```json
{"secret": "optional_hmac_secret"}
```
Returns a `webhook_url` in the result. External systems POST to that URL to fire the job. If `secret` is set, callers must include `X-Webhook-Signature: sha256=<hex>` (HMAC-SHA256 of the raw request body).

### `scheduler.list_jobs`
- **status_filter** (optional) — `active`, `completed`, `failed`, `cancelled`
- **workflow_id** (optional) — filter to a specific workflow

Returns `name`, `last_result`, `runs_completed`, `expires_at`, and all standard fields.

### `scheduler.cancel_job`
- **job_id** (required)

### `scheduler.cancel_workflow`
- **workflow_id** (required) — cancels all active jobs with this `workflow_id`

When any job in a workflow fails (max_attempts or expires_at), sibling active jobs are **automatically cancelled**.

### `scheduler.create_workflow`
- **name** (required) — human-readable workflow name
- **description** (optional)

Returns `workflow_id` to use in subsequent `add_job` calls.

### `scheduler.get_workflow_status`
- **workflow_id** (required)

Returns overall derived status (`active`/`failed`/`completed`/`cancelled`), job count breakdown, and per-job summaries including `last_result`.

### `scheduler.list_workflows`
- **status_filter** (optional)

## Message Placeholders

| Placeholder | Replaces with |
|-------------|---------------|
| `{result}` | Compact summary of the full result dict |
| `{result.field}` | Value of `result["field"]` |
| `{result.nested.field}` | Dot-path traversal into nested dicts |
| `{job_id}` | This job's UUID |
| `{workflow_id}` | The workflow's UUID (if set) |

## Reliability

- **Exponential backoff**: transient errors (connection failures) back off with `min(interval × 2^consecutive_failures, 300s)`. The counter resets on successful poll.
- **Permanent errors**: HTTP 404/410 or error messages matching "not found", "does not exist", "unknown tool" fail the job immediately without retry.
- **Wall-clock expiry**: set `expires_at` for a hard deadline independent of polling interval.

## Webhook Endpoint

External systems can trigger webhook-type jobs via:

```
POST /webhook/{job_id}
Content-Type: application/json
X-Webhook-Signature: sha256=<hmac-sha256-hex>  # only if secret configured

{"event": "push", "ref": "refs/heads/main"}
```

This endpoint is intentionally **unauthenticated** (no service token required) since it's called by external CI/CD systems. The optional HMAC signature provides security when a `secret` is configured.

## Implementation Notes

- The orchestrator injects `user_id`, `platform`, `platform_channel_id`, `platform_thread_id`, and `conversation_id` into `add_job` and `create_workflow` calls
- `workflow_id` is a plain UUID on `ScheduledJob` (no FK); named workflow records live in `scheduled_workflows`
- The scheduler worker runs as a background asyncio task in the scheduler module container, polling `next_run_at <= now` every 10 seconds
- Cron jobs reschedule themselves after each fire; they only terminate when `max_runs` is reached or the job is cancelled
- For workflow continuations, the core creates a unique thread ID (`wf-{workflow_id}-{random}`) so each phase gets a fresh conversation context

## Database

- **Model:** `ScheduledJob` (`agent/shared/shared/models/scheduled_job.py`)
- **Model:** `ScheduledWorkflow` (`agent/shared/shared/models/scheduled_workflow.py`)
- **New columns (017 migration):** `name`, `description`, `consecutive_failures`, `runs_completed`, `max_runs`, `expires_at`, `last_result`

## Key Files

- `agent/modules/scheduler/manifest.py`
- `agent/modules/scheduler/tools.py`
- `agent/modules/scheduler/main.py`
- `agent/modules/scheduler/worker.py`
- `agent/shared/shared/models/scheduled_job.py`
- `agent/shared/shared/models/scheduled_workflow.py`
- `agent/alembic/versions/017_scheduler_improvements.py`
- `agent/tests/modules/test_scheduler_worker.py`
