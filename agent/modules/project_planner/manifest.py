"""Project planner module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="project_planner",
    description=(
        "Project planning and execution tracker. Create projects from design "
        "sessions, break them into phases and tasks, and track implementation "
        "progress. Integrates with claude_code for task execution and "
        "git_platform for branches, PRs, and issues."
    ),
    tools=[
        # ── Project management ──────────────────────────────────────────
        ToolDefinition(
            name="project_planner.create_project",
            description=(
                "Create a new project from a design session. Include the full "
                "design document, repo info, and optionally phases with tasks. "
                "The project starts in 'planning' status."
            ),
            parameters=[
                ToolParameter(name="name", type="string", description="Project name (unique per user)."),
                ToolParameter(name="description", type="string", description="Short project summary.", required=False),
                ToolParameter(
                    name="design_document", type="string",
                    description="Full markdown design document from the planning session.",
                    required=False,
                ),
                ToolParameter(name="repo_owner", type="string", description="GitHub repo owner.", required=False),
                ToolParameter(name="repo_name", type="string", description="GitHub repo name.", required=False),
                ToolParameter(name="default_branch", type="string", description="Base branch (default: main).", required=False),
                ToolParameter(name="auto_merge", type="boolean", description="Auto-merge PRs after CI passes (default: false).", required=False),
                ToolParameter(
                    name="phases", type="array",
                    description=(
                        "Optional list of phases to create: "
                        '[{"name": "Phase 1: Core API", "description": "...", "tasks": ['
                        '{"title": "...", "description": "...", "acceptance_criteria": "..."}]}]'
                    ),
                    required=False,
                ),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="project_planner.update_project",
            description="Update project fields (name, description, design_document, status, repo info, auto_merge, planning_task_id).",
            parameters=[
                ToolParameter(name="project_id", type="string", description="UUID of the project."),
                ToolParameter(name="name", type="string", description="New project name.", required=False),
                ToolParameter(name="description", type="string", description="New description.", required=False),
                ToolParameter(name="design_document", type="string", description="Updated design document.", required=False),
                ToolParameter(name="status", type="string", description="New status: planning, active, paused, completed, archived.", required=False),
                ToolParameter(name="repo_owner", type="string", description="GitHub repo owner.", required=False),
                ToolParameter(name="repo_name", type="string", description="GitHub repo name.", required=False),
                ToolParameter(name="default_branch", type="string", description="Base branch.", required=False),
                ToolParameter(name="auto_merge", type="boolean", description="Auto-merge PRs after CI.", required=False),
                ToolParameter(name="planning_task_id", type="string", description="Claude Code task ID for planning phase.", required=False),
                ToolParameter(name="workflow_id", type="string", description="Active workflow ID for automated sequential execution.", required=False),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="project_planner.get_project",
            description="Get a project with its phases and task status summary.",
            parameters=[
                ToolParameter(name="project_id", type="string", description="UUID of the project."),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="project_planner.list_projects",
            description="List all projects for the user with summary stats.",
            parameters=[
                ToolParameter(
                    name="status_filter", type="string",
                    description="Filter by status.", required=False,
                    enum=["planning", "active", "paused", "completed", "archived"],
                ),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="project_planner.delete_project",
            description="Delete a project and all its phases and tasks.",
            parameters=[
                ToolParameter(name="project_id", type="string", description="UUID of the project to delete."),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="admin",
        ),
        # ── Phase management ────────────────────────────────────────────
        ToolDefinition(
            name="project_planner.add_phase",
            description="Add a phase to a project.",
            parameters=[
                ToolParameter(name="project_id", type="string", description="UUID of the project."),
                ToolParameter(name="name", type="string", description="Phase name."),
                ToolParameter(name="description", type="string", description="What this phase delivers.", required=False),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="project_planner.update_phase",
            description="Update phase fields (name, description, status).",
            parameters=[
                ToolParameter(name="phase_id", type="string", description="UUID of the phase."),
                ToolParameter(name="name", type="string", description="New phase name.", required=False),
                ToolParameter(name="description", type="string", description="New description.", required=False),
                ToolParameter(name="status", type="string", description="New status: planned, in_progress, completed.", required=False),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        # ── Task management ─────────────────────────────────────────────
        ToolDefinition(
            name="project_planner.add_task",
            description="Add a task to a phase.",
            parameters=[
                ToolParameter(name="phase_id", type="string", description="UUID of the phase."),
                ToolParameter(name="title", type="string", description="Short task title."),
                ToolParameter(name="description", type="string", description="What to implement.", required=False),
                ToolParameter(name="acceptance_criteria", type="string", description="How to verify it's done.", required=False),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="project_planner.bulk_add_tasks",
            description=(
                "Add multiple tasks to a phase at once. Useful for initial project setup."
            ),
            parameters=[
                ToolParameter(name="phase_id", type="string", description="UUID of the phase."),
                ToolParameter(
                    name="tasks", type="array",
                    description=(
                        'List of tasks: [{"title": "...", "description": "...", '
                        '"acceptance_criteria": "..."}]'
                    ),
                ),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="project_planner.update_task",
            description=(
                "Update task fields — status, branch, PR number, issue number, "
                "claude_task_id, error_message, etc."
            ),
            parameters=[
                ToolParameter(name="task_id", type="string", description="UUID of the task."),
                ToolParameter(name="title", type="string", description="New title.", required=False),
                ToolParameter(name="description", type="string", description="New description.", required=False),
                ToolParameter(name="acceptance_criteria", type="string", description="New acceptance criteria.", required=False),
                ToolParameter(
                    name="status", type="string", description="New status.",
                    required=False, enum=["todo", "doing", "in_review", "done", "failed"],
                ),
                ToolParameter(name="branch_name", type="string", description="Git branch name.", required=False),
                ToolParameter(name="pr_number", type="integer", description="GitHub PR number.", required=False),
                ToolParameter(name="issue_number", type="integer", description="GitHub issue number.", required=False),
                ToolParameter(name="claude_task_id", type="string", description="Claude Code task ID.", required=False),
                ToolParameter(name="error_message", type="string", description="Error message if task failed.", required=False),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="project_planner.get_task",
            description="Get full detail for a single task.",
            parameters=[
                ToolParameter(name="task_id", type="string", description="UUID of the task."),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        # ── Execution helpers ───────────────────────────────────────────
        ToolDefinition(
            name="project_planner.get_phase_tasks",
            description="Get all tasks for a phase, ordered by order_index.",
            parameters=[
                ToolParameter(name="phase_id", type="string", description="UUID of the phase."),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="project_planner.get_next_task",
            description=(
                "Get the next 'todo' task (by order_index). "
                "Pass project_id to auto-pick the current phase, or phase_id for a specific phase. "
                "Returns null if all tasks are done or in progress."
            ),
            parameters=[
                ToolParameter(name="project_id", type="string", description="UUID of the project. Finds the earliest phase with todo tasks.", required=False),
                ToolParameter(name="phase_id", type="string", description="UUID of a specific phase. Takes priority over project_id.", required=False),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        # ── Batch execution ──────────────────────────────────────────────
        ToolDefinition(
            name="project_planner.get_execution_plan",
            description=(
                "Get a batch execution plan for a project. Gathers all todo "
                "tasks across specified phases (or all phases) and returns a "
                "structured plan with the design document, tasks in order, "
                "and a pre-built prompt for a single claude_code.run_task call. "
                "Use this instead of get_next_task when implementing multiple "
                "phases at once."
            ),
            parameters=[
                ToolParameter(
                    name="project_id", type="string",
                    description="UUID of the project.",
                ),
                ToolParameter(
                    name="phase_ids", type="array",
                    description=(
                        "Optional list of phase UUIDs to include. "
                        "If omitted, all phases with todo tasks are included."
                    ),
                    required=False,
                ),
                ToolParameter(
                    name="user_id", type="string",
                    description="User ID (injected by orchestrator).",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="project_planner.bulk_update_tasks",
            description=(
                "Update multiple tasks at once. Use with get_execution_plan "
                "to mark all tasks as 'doing' before batch execution, then "
                "'done' after completion. Pass the todo_task_ids from the "
                "execution plan."
            ),
            parameters=[
                ToolParameter(
                    name="task_ids", type="array",
                    description="List of task UUID strings to update.",
                ),
                ToolParameter(
                    name="status", type="string",
                    description="New status for all tasks.",
                    enum=["todo", "doing", "in_review", "done", "failed"],
                ),
                ToolParameter(
                    name="claude_task_id", type="string",
                    description=(
                        "Claude Code task ID to set on all tasks "
                        "(they share a single execution)."
                    ),
                    required=False,
                ),
                ToolParameter(
                    name="error_message", type="string",
                    description="Error message to set on all tasks (for failed status).",
                    required=False,
                ),
                ToolParameter(
                    name="user_id", type="string",
                    description="User ID (injected by orchestrator).",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        # ── Reporting ───────────────────────────────────────────────────
        ToolDefinition(
            name="project_planner.get_project_status",
            description=(
                "Get a summary of project progress: task counts by status, "
                "current phase, and any failed/blocked tasks."
            ),
            parameters=[
                ToolParameter(name="project_id", type="string", description="UUID of the project."),
                ToolParameter(name="user_id", type="string", description="User ID (injected by orchestrator).", required=False),
            ],
            required_permission="user",
        ),
        # ── Sequential Phase Execution ──────────────────────────────────
        ToolDefinition(
            name="project_planner.execute_next_phase",
            description=(
                "Execute the next phase in sequence. For phase 0, reuses planning task "
                "context if available. Creates scheduler job for monitoring."
            ),
            parameters=[
                ToolParameter(
                    name="project_id",
                    type="string",
                    description="Project ID",
                    required=True,
                ),
                ToolParameter(
                    name="auto_push",
                    type="boolean",
                    description="Automatically push branch after completion",
                    required=False,
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="Task timeout in seconds (default 1800)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="project_planner.complete_phase",
            description=(
                "Complete a phase after its claude_code task finishes. Creates PR, "
                "updates all phase tasks to 'in_review', marks phase as completed. "
                "Returns whether to trigger next phase."
            ),
            parameters=[
                ToolParameter(
                    name="phase_id",
                    type="string",
                    description="Phase ID",
                    required=True,
                ),
                ToolParameter(
                    name="claude_task_id",
                    type="string",
                    description="Claude Code task ID that executed this phase",
                    required=True,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="project_planner.start_project_workflow",
            description=(
                "Start fully automated sequential phase execution. Launches first phase "
                "and creates scheduler workflow that auto-progresses through all phases, "
                "creating PRs between each."
            ),
            parameters=[
                ToolParameter(
                    name="project_id",
                    type="string",
                    description="Project ID",
                    required=True,
                ),
                ToolParameter(
                    name="workflow_id",
                    type="string",
                    description="Optional workflow ID for grouping jobs (auto-generated if not provided)",
                    required=False,
                ),
                ToolParameter(
                    name="auto_push",
                    type="boolean",
                    description="Automatically push branches after completion",
                    required=False,
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="Per-phase timeout in seconds (default 1800)",
                    required=False,
                ),
                ToolParameter(
                    name="platform",
                    type="string",
                    description="Platform for notifications (e.g. 'web', 'discord'). Required for workflow scheduling.",
                    required=False,
                ),
                ToolParameter(
                    name="platform_channel_id",
                    type="string",
                    description="Channel ID for notifications. For web portal, use the user's UUID.",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
    ],
)
