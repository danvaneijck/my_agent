# scheduler

Background job scheduler for monitoring long-running tasks. Supports simple notifications and workflow chaining via `resume_conversation`.

## Tools

| Tool | Description | Permission |
|------|-------------|------------|
| `scheduler.add_job` | Schedule a background monitoring job | admin |
| `scheduler.list_jobs` | List jobs, optionally filtered by status | admin |
| `scheduler.cancel_job` | Cancel an active job by ID | admin |
| `scheduler.cancel_workflow` | Cancel all jobs in a workflow | admin |

## Tool Details

### `scheduler.add_job`
- **job_type** (string, required) — `poll_module`, `delay`, or `poll_url`
- **check_config** (object, required) — condition configuration:
  - `poll_module`: `{module, tool, args, success_field, success_values}`
  - `delay`: `{delay_seconds}`
  - `poll_url`: `{url, method, expected_status}`
- **on_success_message** (string, required) — message when condition met; supports `{result}` placeholder
- **on_failure_message** (string, optional) — message if job times out
- **on_complete** (string, optional) — `notify` (default) or `resume_conversation`
- **workflow_id** (string, optional) — UUID to group related jobs
- **interval_seconds** (integer, optional) — polling interval (default 30)
- **max_attempts** (integer, optional) — max checks before failing (default 120 = ~1 hour at 30s)

### `scheduler.list_jobs`
- **status_filter** (string, optional) — `active`, `completed`, `failed`, `cancelled`

### `scheduler.cancel_job`
- **job_id** (string, required)

### `scheduler.cancel_workflow`
- **workflow_id** (string, required) — cancels all active jobs with this workflow_id

## Completion Modes

### `on_complete="notify"` (default)
Sends a message to the user via Redis pub/sub on the `notifications:{platform}` channel. The bot picks it up and delivers to the original channel/thread.

### `on_complete="resume_conversation"`
Calls core `/continue` endpoint to re-enter the agent loop. The LLM sees the `on_success_message` (with `{result}` replaced) and can decide next steps — e.g. calling `deployer.deploy`. Falls back to plain notification if `/continue` fails.

## Implementation Notes

- The orchestrator injects `user_id`, `platform`, `platform_channel_id`, `platform_thread_id`, and `conversation_id` into job creation
- `workflow_id` is a plain UUID, not a foreign key — it groups jobs for display and bulk cancellation
- The scheduler worker runs as a background task in core, polling `ScheduledJob.next_run_at <= now`
- On success: marks job completed, sends notification or resumes conversation
- On max_attempts exceeded: marks failed, sends `on_failure_message`

## Database

- **Model:** `ScheduledJob` (`agent/shared/shared/models/scheduled_job.py`)
- **Fields:** `id`, `user_id`, `conversation_id`, `platform`, `platform_channel_id`, `platform_thread_id`, `job_type`, `check_config` (JSON), `interval_seconds`, `max_attempts`, `attempts`, `on_success_message`, `on_failure_message`, `status`, `next_run_at`, `created_at`, `completed_at`

## Key Files

- `agent/modules/scheduler/manifest.py`
- `agent/modules/scheduler/tools.py`
- `agent/modules/scheduler/main.py`
- `agent/core/orchestrator/agent_loop.py` (worker logic, context injection)
