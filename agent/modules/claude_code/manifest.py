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
                "Returns a task_id immediately — use claude_code.task_status to poll for results. "
                "Claude Code can write code, run commands, create files, and interact with git repos."
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
                "(queued/running/completed/failed), elapsed time, heartbeat, and result if finished."
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
