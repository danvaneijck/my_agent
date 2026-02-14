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
                    description="Max execution time in seconds (default 1800). Do not set a lower value unless specifically requested.",
                    required=False,
                ),
                ToolParameter(
                    name="mode",
                    type="string",
                    description=(
                        "Task mode: 'execute' (default) runs the task immediately, "
                        "'plan' creates a plan for review before execution. "
                        "Plan-mode tasks finish with 'awaiting_input' status."
                    ),
                    enum=["execute", "plan"],
                    required=False,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="claude_code.continue_task",
            description=(
                "Run a follow-up prompt against an existing task's workspace to make edits "
                "to a previously generated project. Uses --continue to resume the Claude CLI "
                "session with full conversation context. Returns a new task_id for tracking. "
                "Set mode='execute' to approve a plan and begin implementation. "
                "Also use this to resume a timed_out task — the workspace files are preserved."
            ),
            parameters=[
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="The task ID of the original task whose workspace to edit.",
                    required=True,
                ),
                ToolParameter(
                    name="prompt",
                    type="string",
                    description="Description of the changes to make to the existing project.",
                    required=True,
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="Max execution time in seconds (default 1800). Do not set a lower value unless specifically requested.",
                    required=False,
                ),
                ToolParameter(
                    name="mode",
                    type="string",
                    description=(
                        "Override the mode for this continuation. Use 'execute' to approve "
                        "a plan and begin implementation. Omit to inherit from parent task."
                    ),
                    enum=["execute", "plan"],
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
                    enum=["queued", "running", "completed", "failed", "timed_out", "awaiting_input"],
                    required=False,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="claude_code.get_task_chain",
            description=(
                "Get all tasks in a planning chain (plan -> feedback -> implementation). "
                "Returns tasks sorted chronologically. Use any task ID in the chain."
            ),
            parameters=[
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="Any task ID in the chain.",
                    required=True,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="claude_code.browse_workspace",
            description=(
                "List files and directories in a task's workspace. "
                "Returns entries with name, type (file/directory), size, and modified time."
            ),
            parameters=[
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="The task ID whose workspace to browse.",
                    required=True,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="Relative path within the workspace (empty string for root).",
                    required=False,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="claude_code.read_workspace_file",
            description="Read the contents of a text file in a task's workspace.",
            parameters=[
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="The task ID whose workspace contains the file.",
                    required=True,
                ),
                ToolParameter(
                    name="path",
                    type="string",
                    description="Relative file path within the workspace.",
                    required=True,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="claude_code.git_status",
            description=(
                "Get the git status of a task's workspace. Returns the current branch, "
                "tracking info, ahead/behind counts, staged/unstaged/untracked files, "
                "and recent commits. Use this to inspect the state of a cloned repository "
                "after a coding task completes."
            ),
            parameters=[
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="The task ID whose workspace git status to check.",
                    required=True,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="claude_code.git_push",
            description=(
                "Push commits from a task workspace's branch to its remote. "
                "Requires SSH keys to be configured. Returns success/failure with git output. "
                "Use claude_code.git_status first to verify the workspace has commits to push."
            ),
            parameters=[
                ToolParameter(
                    name="task_id",
                    type="string",
                    description="The task ID whose workspace branch to push.",
                    required=True,
                ),
                ToolParameter(
                    name="remote",
                    type="string",
                    description="Remote name to push to (default: 'origin').",
                    required=False,
                ),
                ToolParameter(
                    name="branch",
                    type="string",
                    description=(
                        "Branch to push. Defaults to the current branch. "
                        "Use 'HEAD:refs/heads/<name>' syntax to push to a different remote branch."
                    ),
                    required=False,
                ),
                ToolParameter(
                    name="force",
                    type="boolean",
                    description=(
                        "Force push using --force-with-lease (safe force push). "
                        "Default false. Use when the remote branch has been rebased."
                    ),
                    required=False,
                ),
            ],
            required_permission="admin",
        ),
    ],
)
