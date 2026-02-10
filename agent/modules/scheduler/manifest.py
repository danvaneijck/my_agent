"""Scheduler module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="scheduler",
    description=(
        "Background job scheduler for monitoring long-running tasks and sending "
        "proactive notifications. Use this to monitor async operations (like "
        "claude_code.run_task) so the user is notified when they complete."
    ),
    tools=[
        ToolDefinition(
            name="scheduler.add_job",
            description=(
                "Schedule a background monitoring job that will proactively notify "
                "the user when a condition is met. Use this after submitting a "
                "long-running task (like claude_code.run_task) to monitor its "
                "completion. The user does NOT need to check back manually — they "
                "will receive a message in their channel when the job finishes. "
                "Supports polling module tool results, simple delays, and HTTP "
                "health checks."
            ),
            parameters=[
                ToolParameter(
                    name="job_type",
                    type="string",
                    description=(
                        "Type of monitoring job: 'poll_module' to poll a module tool, "
                        "'delay' for a simple timer, 'poll_url' for HTTP health checks"
                    ),
                    enum=["poll_module", "delay", "poll_url"],
                ),
                ToolParameter(
                    name="check_config",
                    type="object",
                    description=(
                        "Configuration for the check. For poll_module: "
                        '{\"module\": \"claude_code\", \"tool\": \"claude_code.task_status\", '
                        '\"args\": {\"task_id\": \"abc123\"}, \"success_field\": \"status\", '
                        '\"success_values\": [\"completed\", \"failed\"]}. '
                        "For delay: {\"delay_seconds\": 300}. "
                        "For poll_url: {\"url\": \"http://example.com/health\", "
                        '\"method\": \"GET\", \"expected_status\": 200}.'
                    ),
                ),
                ToolParameter(
                    name="on_success_message",
                    type="string",
                    description=(
                        "Message to send when the condition is met. Use {result} "
                        "placeholder to include the actual result."
                    ),
                ),
                ToolParameter(
                    name="on_failure_message",
                    type="string",
                    description="Message to send if the job times out (max attempts exceeded).",
                    required=False,
                ),
                ToolParameter(
                    name="interval_seconds",
                    type="integer",
                    description="How often to check the condition in seconds (default: 30).",
                    required=False,
                ),
                ToolParameter(
                    name="max_attempts",
                    type="integer",
                    description="Maximum number of checks before marking failed (default: 120 = ~1 hour at 30s).",
                    required=False,
                ),
                ToolParameter(
                    name="user_id",
                    type="string",
                    description="The user ID (injected by orchestrator).",
                    required=False,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="scheduler.list_jobs",
            description="List scheduled jobs for the current user, optionally filtered by status.",
            parameters=[
                ToolParameter(
                    name="status_filter",
                    type="string",
                    description="Filter by job status.",
                    required=False,
                    enum=["active", "completed", "failed", "cancelled"],
                ),
                ToolParameter(
                    name="user_id",
                    type="string",
                    description="The user ID (injected by orchestrator).",
                    required=False,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="scheduler.cancel_job",
            description="Cancel an active scheduled job by its ID.",
            parameters=[
                ToolParameter(
                    name="job_id",
                    type="string",
                    description="UUID of the job to cancel.",
                ),
                ToolParameter(
                    name="user_id",
                    type="string",
                    description="The user ID (injected by orchestrator).",
                    required=False,
                ),
            ],
            required_permission="admin",
        ),
    ],
)
