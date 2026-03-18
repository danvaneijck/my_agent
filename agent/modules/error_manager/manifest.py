"""Error manager module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="error_manager",
    description="View, dismiss, and resolve captured system errors.",
    tools=[
        ToolDefinition(
            name="error_manager.list_errors",
            description=(
                "List captured error logs with optional filters. Returns errors "
                "sorted by most recent first. Use this to review what's failing "
                "in the system."
            ),
            parameters=[
                ToolParameter(
                    name="status",
                    type="string",
                    description="Filter by status. Defaults to 'open' to show unresolved errors.",
                    enum=["open", "dismissed", "resolved"],
                    required=False,
                ),
                ToolParameter(
                    name="service",
                    type="string",
                    description="Filter by service name (e.g. 'core', 'research', 'claude_code').",
                    required=False,
                ),
                ToolParameter(
                    name="error_type",
                    type="string",
                    description="Filter by error type (e.g. 'tool_execution', 'llm_call', 'agent_loop', 'module_startup').",
                    required=False,
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Max number of errors to return (default 20).",
                    required=False,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="error_manager.error_summary",
            description=(
                "Get a high-level summary of error counts by status and "
                "a breakdown of open errors by service and error type. "
                "Use this first to understand the overall error landscape."
            ),
            parameters=[],
            required_permission="admin",
        ),
        ToolDefinition(
            name="error_manager.get_error",
            description=(
                "Get full details of a specific error including stack trace, "
                "tool arguments, and context for reproduction."
            ),
            parameters=[
                ToolParameter(
                    name="error_id",
                    type="string",
                    description="The UUID of the error to inspect.",
                    required=True,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="error_manager.dismiss_error",
            description=(
                "Mark an error as dismissed (acknowledged but not necessarily fixed). "
                "Use this for known issues, transient failures, or errors that don't "
                "need a code fix."
            ),
            parameters=[
                ToolParameter(
                    name="error_id",
                    type="string",
                    description="The UUID of the error to dismiss.",
                    required=True,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="error_manager.resolve_error",
            description=(
                "Mark an error as resolved (fix has been deployed). "
                "Sets the resolved_at timestamp."
            ),
            parameters=[
                ToolParameter(
                    name="error_id",
                    type="string",
                    description="The UUID of the error to resolve.",
                    required=True,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="error_manager.bulk_dismiss",
            description=(
                "Dismiss multiple errors at once. Useful for clearing out "
                "a batch of known or transient errors after reviewing them."
            ),
            parameters=[
                ToolParameter(
                    name="error_ids",
                    type="array",
                    description="List of error UUIDs to dismiss.",
                    required=True,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="error_manager.bulk_resolve",
            description=(
                "Resolve multiple errors at once. Useful after deploying "
                "a fix that addresses several related errors."
            ),
            parameters=[
                ToolParameter(
                    name="error_ids",
                    type="array",
                    description="List of error UUIDs to resolve.",
                    required=True,
                ),
            ],
            required_permission="admin",
        ),
    ],
)
