"""Code Executor module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="code_executor",
    description="Execute Python code and shell commands in a sandboxed environment.",
    tools=[
        ToolDefinition(
            name="code_executor.run_python",
            description=(
                "Execute Python code and return stdout, stderr, and the return value. "
                "Code runs in an isolated subprocess with a 30-second timeout. "
                "Common libraries (math, json, datetime, collections, itertools, re, statistics) are available."
            ),
            parameters=[
                ToolParameter(
                    name="code",
                    type="string",
                    description="Python code to execute",
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="Max execution time in seconds (default 30, max 60)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="code_executor.run_shell",
            description=(
                "Execute a shell command and return stdout and stderr. "
                "Runs in an isolated subprocess with a 30-second timeout. "
                "Only safe, read-only commands are allowed (curl, wget, jq, wc, sort, etc.)."
            ),
            parameters=[
                ToolParameter(
                    name="command",
                    type="string",
                    description="Shell command to execute",
                ),
                ToolParameter(
                    name="timeout",
                    type="integer",
                    description="Max execution time in seconds (default 30, max 60)",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
    ],
)
