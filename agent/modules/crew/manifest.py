"""Tool manifest for the crew module."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="crew",
    description="Multi-agent crew sessions — coordinate multiple Claude Code agents working on a project in parallel with shared context and automated merge integration.",
    tools=[
        ToolDefinition(
            name="crew.create_session",
            description="Create a new crew session linked to a project. Analyzes task dependencies and computes execution waves.",
            parameters=[
                ToolParameter(name="project_id", type="string", description="Project to run as a crew", required=True),
                ToolParameter(name="name", type="string", description="Session name", required=False),
                ToolParameter(name="max_agents", type="integer", description="Maximum concurrent agents (default 4, max 6)", required=False),
                ToolParameter(name="role_assignments", type="object", description="Map of task_id → role (architect|backend|frontend|tester|reviewer)", required=False),
                ToolParameter(name="auto_push", type="boolean", description="Auto-push branches after completion (default true)", required=False),
                ToolParameter(name="timeout", type="integer", description="Timeout per agent in seconds (default 1800)", required=False),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="crew.start_session",
            description="Start a crew session — begins dispatching wave 1 agents.",
            parameters=[
                ToolParameter(name="session_id", type="string", description="Crew session ID", required=True),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="crew.get_session",
            description="Get full crew session detail with members, context board, and progress.",
            parameters=[
                ToolParameter(name="session_id", type="string", description="Crew session ID", required=True),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="crew.list_sessions",
            description="List crew sessions for the current user.",
            parameters=[
                ToolParameter(name="status_filter", type="string", description="Filter by status (configuring|running|paused|completed|failed)", required=False),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="crew.pause_session",
            description="Pause a running crew session. Currently working agents will finish but no new waves dispatch.",
            parameters=[
                ToolParameter(name="session_id", type="string", description="Crew session ID", required=True),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="crew.resume_session",
            description="Resume a paused crew session.",
            parameters=[
                ToolParameter(name="session_id", type="string", description="Crew session ID", required=True),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="crew.cancel_session",
            description="Cancel a crew session. All running agents are stopped.",
            parameters=[
                ToolParameter(name="session_id", type="string", description="Crew session ID", required=True),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="crew.post_context",
            description="Post an entry to the crew's shared context board. All agents in subsequent waves will see this.",
            parameters=[
                ToolParameter(name="session_id", type="string", description="Crew session ID", required=True),
                ToolParameter(name="entry_type", type="string", description="Entry type: decision|api_contract|interface|note|blocker", required=True),
                ToolParameter(name="title", type="string", description="Short title for the entry", required=True),
                ToolParameter(name="content", type="string", description="Full content of the entry", required=True),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="crew.get_context_board",
            description="Get all entries from the crew's shared context board.",
            parameters=[
                ToolParameter(name="session_id", type="string", description="Crew session ID", required=True),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="crew.advance_session",
            description="Called by the scheduler when a crew member completes. Handles merge, wave transitions, and next dispatch.",
            parameters=[
                ToolParameter(name="session_id", type="string", description="Crew session ID", required=True),
                ToolParameter(name="member_id", type="string", description="Crew member ID that completed", required=True),
                ToolParameter(name="claude_task_id", type="string", description="Claude Code task ID of the completed member", required=True),
            ],
            required_permission="admin",
        ),
    ],
)
