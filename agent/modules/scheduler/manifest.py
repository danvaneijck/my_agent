"""Scheduler module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="scheduler",
    description=(
        "Background job scheduler for monitoring long-running tasks. Supports "
        "simple notifications and workflow chaining (resume_conversation) to "
        "continue multi-step workflows like build-then-deploy."
    ),
    tools=[
        ToolDefinition(
            name="scheduler.add_job",
            description=(
                "Schedule a background monitoring job. When the condition is met, "
                "either sends a notification OR re-enters the agent loop so you can "
                "continue with follow-up actions (like deploying after a build). "
                "Use on_complete='resume_conversation' for multi-step workflows "
                "(e.g. build then deploy) — the conversation resumes automatically "
                "and you can call deployer.deploy() with the completed workspace. "
                "Use on_complete='notify' (default) for simple monitoring where "
                "just a message to the user is sufficient."
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
                        "placeholder to include the actual result. For "
                        "resume_conversation mode this becomes the context message "
                        "the agent sees to decide next steps."
                    ),
                ),
                ToolParameter(
                    name="on_failure_message",
                    type="string",
                    description="Message to send if the job times out (max attempts exceeded).",
                    required=False,
                ),
                ToolParameter(
                    name="on_complete",
                    type="string",
                    description=(
                        "What to do when the condition is met. 'notify' sends a "
                        "message to the user. 'resume_conversation' re-enters the "
                        "agent loop so you can continue with follow-up tool calls "
                        "(e.g. deploy after build completes). Default: 'notify'."
                    ),
                    required=False,
                    enum=["notify", "resume_conversation"],
                ),
                ToolParameter(
                    name="workflow_id",
                    type="string",
                    description=(
                        "Optional UUID to group related jobs into a workflow. "
                        "All jobs sharing a workflow_id are shown together in the "
                        "portal and can be cancelled as a group."
                    ),
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
        ToolDefinition(
            name="scheduler.cancel_workflow",
            description="Cancel all active jobs in a workflow by workflow_id.",
            parameters=[
                ToolParameter(
                    name="workflow_id",
                    type="string",
                    description="UUID of the workflow to cancel.",
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
