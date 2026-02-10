"""Claude Code module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="claude_code",
    description="Execute coding tasks using Claude Code CLI in disposable Docker containers.",
    tools=[
        ToolDefinition(
            name="claude_code.run_task",
            description=(
                "Submit a coding task for Claude Code to execute in an isolated Docker container. "
                "Returns a task_id and workspace path immediately — use claude_code.task_status to poll for results. "
                "Claude Code can write code, run commands, create files, and interact with git repos. "
                "The workspace path (e.g. /tmp/claude_tasks/<task_id>) can be passed directly to "
                "deployer.deploy as the project_path to deploy the generated project."
            ),
            parameters=[
                ToolParameter(
                    name="prompt",
                    type="string",
                    description="Detailed description of the coding task to perform.",
                    required=True,
                ),
                ToolParameter(
                    name="repo_url",
                    type="string",
                    description="Git repository URL to clone before starting (e.g. https://github.com/user/repo).",
                    required=False,
                ),
                ToolParameter(
                    name="branch",
                    type="string",
                    description="Git branch to checkout or create.",
                    required=False,
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="Max execution time in seconds (default 600).",
                    required=False,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="claude_code.task_status",
            description=(
                "Check the status of a previously submitted Claude Code task. Returns status "
                "(queued/running/completed/failed), workspace path, elapsed time, heartbeat, and result if finished. "
                "The workspace path can be passed to deployer.deploy as the project_path."
            ),
            parameters=[
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="The task ID returned by run_task.",
                    required=True,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="claude_code.task_logs",
            description=(
                "Read live log output from a running (or finished) Claude Code task. "
                "Returns the most recent lines by default. Use tail to control how many "
                "lines, or offset to paginate from a specific line number."
            ),
            parameters=[
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="The task ID returned by run_task.",
                    required=True,
                ),
                ToolParameter(
                    name="tail",
                    type="integer",
                    description="Number of lines to return (default 100). Returns the last N lines unless offset is set.",
                    required=False,
                ),
                ToolParameter(
                    name="offset",
                    type="integer",
                    description="Start reading from this line number (0-indexed). When set, returns `tail` lines starting from offset.",
                    required=False,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="claude_code.cancel_task",
            description=(
                "Cancel a running or queued Claude Code task. Kills the Docker container "
                "and marks the task as failed. Use this when a task is taking too long, "
                "is stuck, or is no longer needed."
            ),
            parameters=[
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="The task ID returned by run_task.",
                    required=True,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="claude_code.list_tasks",
            description="List all Claude Code tasks with their current statuses.",
            parameters=[
                ToolParameter(
                    name="status_filter",
                    type="string",
                    description="Filter by status.",
                    enum=["queued", "running", "completed", "failed"],
                    required=False,
                ),
            ],
            required_permission="admin",
        ),
    ],
)
