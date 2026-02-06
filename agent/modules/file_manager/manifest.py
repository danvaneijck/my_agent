"""File Manager module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="file_manager",
    description="Manage files in cloud storage. Create, list, retrieve, and delete documents.",
    tools=[
        ToolDefinition(
            name="file_manager.create_document",
            description="Create a new document (markdown, text, json, or csv) and store it. Returns the public URL.",
            parameters=[
                ToolParameter(name="title", type="string", description="Document title (used as filename)"),
                ToolParameter(name="content", type="string", description="Document content"),
                ToolParameter(
                    name="format",
                    type="string",
                    description="File format",
                    required=False,
                    enum=["md", "txt", "json", "csv"],
                ),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="file_manager.list_files",
            description="List all stored files, optionally filtered by user.",
            parameters=[
                ToolParameter(
                    name="user_id",
                    type="string",
                    description="Filter by user ID (optional)",
                    required=False,
                ),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="file_manager.get_file_link",
            description="Get the public URL for a stored file.",
            parameters=[
                ToolParameter(name="file_id", type="string", description="The file record ID"),
            ],
            required_permission="guest",
        ),
        ToolDefinition(
            name="file_manager.delete_file",
            description="Delete a file from storage.",
            parameters=[
                ToolParameter(name="file_id", type="string", description="The file record ID"),
            ],
            required_permission="user",
        ),
    ],
)
