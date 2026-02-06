"""Knowledge module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="knowledge",
    description="Persistent user knowledge base. Remember facts and recall them later using semantic search.",
    tools=[
        ToolDefinition(
            name="knowledge.remember",
            description=(
                "Store a fact or piece of information for the user. "
                "Use this when the user says something like 'remember that...', "
                "'my X is Y', or shares important personal context worth retaining."
            ),
            parameters=[
                ToolParameter(
                    name="content",
                    type="string",
                    description="The fact or information to remember",
                ),
                ToolParameter(
                    name="user_id",
                    type="string",
                    description="The user ID (injected by orchestrator)",
                    required=False,
                ),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="knowledge.recall",
            description=(
                "Search the user's stored knowledge for relevant information. "
                "Use this when the user asks about something they previously told you, "
                "or when you need context about the user's preferences, projects, or history."
            ),
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="What to search for in the user's stored knowledge",
                ),
                ToolParameter(
                    name="max_results",
                    type="integer",
                    description="Maximum number of results to return (default 5)",
                    required=False,
                ),
                ToolParameter(
                    name="user_id",
                    type="string",
                    description="The user ID (injected by orchestrator)",
                    required=False,
                ),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="knowledge.list_memories",
            description="List all stored memories for the user, most recent first.",
            parameters=[
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Maximum number of memories to return (default 20)",
                    required=False,
                ),
                ToolParameter(
                    name="user_id",
                    type="string",
                    description="The user ID (injected by orchestrator)",
                    required=False,
                ),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="knowledge.forget",
            description="Delete a specific stored memory by its ID.",
            parameters=[
                ToolParameter(
                    name="memory_id",
                    type="string",
                    description="The ID of the memory to delete",
                ),
                ToolParameter(
                    name="user_id",
                    type="string",
                    description="The user ID (injected by orchestrator)",
                    required=False,
                ),
            ],
            required_permission="guest",
        ),
    ],
)
