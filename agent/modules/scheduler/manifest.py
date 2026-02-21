"""Scheduler module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="scheduler",
    description=(
        "Background job scheduler for monitoring long-running tasks and running "
        "recurring jobs. Supports simple notifications, workflow chaining "
        "(resume_conversation), cron schedules, and webhook triggers."
    ),
    tools=[
        # ------------------------------------------------------------------
        # add_job
        # ------------------------------------------------------------------
        ToolDefinition(
            name="scheduler.add_job",
            description=(
                "Schedule a background monitoring job. When the condition is met, "
                "either sends a notification OR re-enters the agent loop so you can "
                "continue with follow-up actions (like deploying after a build). "
                "\n\nJob types:\n"
                "- poll_module: poll a module tool until a field reaches a target value\n"
                "- delay: fire after a fixed number of seconds\n"
                "- poll_url: fire when an HTTP endpoint returns the expected status/body\n"
                "- cron: fire on a recurring cron schedule (stays active after each run)\n"
                "- webhook: fire when an external system POSTs to the returned webhook_url\n"
                "\nUse on_complete='resume_conversation' for multi-step workflows "
                "(e.g. build then deploy). Use on_complete='notify' (default) for "
                "simple monitoring.\n"
                "\nMessage placeholders: {result}, {result.field}, {result.nested.field}, "
                "{job_id}, {workflow_id}."
            ),
            parameters=[
                ToolParameter(
                    name="job_type",
                    type="string",
                    description=(
                        "Type of monitoring job: 'poll_module' to poll a module tool, "
                        "'delay' for a simple timer, 'poll_url' for HTTP health checks, "
                        "'cron' for recurring scheduled jobs, 'webhook' for external triggers."
                    ),
                    enum=["poll_module", "delay", "poll_url", "cron", "webhook"],
                ),
                ToolParameter(
                    name="check_config",
                    type="object",
                    description=(
                        "Configuration for the check.\n\n"
                        "poll_module: {\"module\": \"claude_code\", \"tool\": \"claude_code.task_status\", "
                        "\"args\": {\"task_id\": \"abc\"}, \"success_field\": \"status\", "
                        "\"success_values\": [\"completed\", \"failed\"], "
                        "\"success_operator\": \"in\" (default), "
                        "\"result_summary_fields\": [\"task_id\", \"status\"]}. "
                        "success_field supports dot-paths (e.g. \"phase.status\"). "
                        "success_operator: \"in\", \"eq\", \"neq\", \"gt\", \"gte\", \"lt\", \"lte\", \"contains\".\n\n"
                        "delay: {\"delay_seconds\": 300}.\n\n"
                        "poll_url: {\"url\": \"http://example.com/health\", \"method\": \"GET\", "
                        "\"expected_status\": 200, \"response_field\": \"status\", "
                        "\"response_value\": \"ok\", \"response_operator\": \"eq\"}.\n\n"
                        "cron: {\"cron_expr\": \"0 8 * * *\", \"timezone\": \"Australia/Sydney\"}.\n\n"
                        "webhook: {\"secret\": \"optional_hmac_secret\"}."
                    ),
                ),
                ToolParameter(
                    name="on_success_message",
                    type="string",
                    description=(
                        "Message to send when the condition is met. Supports placeholders: "
                        "{result} (compact result summary), {result.field} (specific field), "
                        "{result.nested.field} (dot-path into nested dict), "
                        "{job_id} (this job's UUID), {workflow_id} (workflow UUID). "
                        "For resume_conversation mode this becomes the context message "
                        "the agent sees to decide next steps."
                    ),
                ),
                ToolParameter(
                    name="on_failure_message",
                    type="string",
                    description="Message to send if the job times out or expires (max_attempts or expires_at exceeded).",
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
                        "Create one with scheduler.create_workflow first, or re-use "
                        "an existing workflow_id. Jobs sharing a workflow_id are shown "
                        "together and can be cancelled as a group. On failure, sibling "
                        "jobs in the workflow are auto-cancelled."
                    ),
                    required=False,
                ),
                ToolParameter(
                    name="name",
                    type="string",
                    description="Human-readable label for the job (e.g. 'Monitor phase 2 build'). Shown in list_jobs.",
                    required=False,
                ),
                ToolParameter(
                    name="description",
                    type="string",
                    description="Optional longer description of what this job is monitoring.",
                    required=False,
                ),
                ToolParameter(
                    name="interval_seconds",
                    type="integer",
                    description="How often to check the condition in seconds (default: 30). Not used for cron jobs.",
                    required=False,
                ),
                ToolParameter(
                    name="max_attempts",
                    type="integer",
                    description="Maximum number of checks before marking failed (default: 120 = ~1 hour at 30s). Not applicable to cron jobs.",
                    required=False,
                ),
                ToolParameter(
                    name="max_runs",
                    type="integer",
                    description="For cron jobs: maximum number of times to fire before auto-completing. Omit for indefinite.",
                    required=False,
                ),
                ToolParameter(
                    name="expires_at",
                    type="string",
                    description=(
                        "ISO 8601 datetime after which the job is treated as failed if not yet complete "
                        "(e.g. '2026-02-21T18:00:00Z'). Alternative to max_attempts for wall-clock timeouts."
                    ),
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
        # ------------------------------------------------------------------
        # list_jobs
        # ------------------------------------------------------------------
        ToolDefinition(
            name="scheduler.list_jobs",
            description=(
                "List scheduled jobs for the current user, optionally filtered by status "
                "and/or workflow_id. Returns name, last_result, runs_completed, and other "
                "observability fields."
            ),
            parameters=[
                ToolParameter(
                    name="status_filter",
                    type="string",
                    description="Filter by job status.",
                    required=False,
                    enum=["active", "completed", "failed", "cancelled"],
                ),
                ToolParameter(
                    name="workflow_id",
                    type="string",
                    description="Filter to only jobs belonging to this workflow.",
                    required=False,
                ),
                ToolParameter(
                    name="user_id",
                    type="string",
                    description="The user ID (injected by orchestrator).",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        # ------------------------------------------------------------------
        # cancel_job
        # ------------------------------------------------------------------
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
            required_permission="user",
        ),
        # ------------------------------------------------------------------
        # cancel_workflow
        # ------------------------------------------------------------------
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
        # ------------------------------------------------------------------
        # create_workflow
        # ------------------------------------------------------------------
        ToolDefinition(
            name="scheduler.create_workflow",
            description=(
                "Create a named workflow to group related scheduler jobs. "
                "Returns a workflow_id to use in subsequent add_job calls. "
                "Use get_workflow_status to check overall progress."
            ),
            parameters=[
                ToolParameter(
                    name="name",
                    type="string",
                    description="Human-readable workflow name (e.g. 'Build and deploy my-api').",
                ),
                ToolParameter(
                    name="description",
                    type="string",
                    description="Optional description of what this workflow does.",
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
        # ------------------------------------------------------------------
        # get_workflow_status
        # ------------------------------------------------------------------
        ToolDefinition(
            name="scheduler.get_workflow_status",
            description=(
                "Get the overall status of a workflow and summaries of all its jobs. "
                "Overall status is derived from job statuses: active if any job is active, "
                "failed if any failed and none active, completed if all completed."
            ),
            parameters=[
                ToolParameter(
                    name="workflow_id",
                    type="string",
                    description="UUID of the workflow to inspect.",
                ),
                ToolParameter(
                    name="user_id",
                    type="string",
                    description="The user ID (injected by orchestrator).",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        # ------------------------------------------------------------------
        # list_workflows
        # ------------------------------------------------------------------
        ToolDefinition(
            name="scheduler.list_workflows",
            description="List named workflows for the current user.",
            parameters=[
                ToolParameter(
                    name="status_filter",
                    type="string",
                    description="Filter by workflow status.",
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
            required_permission="user",
        ),
    ],
)
