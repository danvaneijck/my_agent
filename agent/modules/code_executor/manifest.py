"""Code Executor module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="code_executor",
    description="Execute Python code and shell commands in a sandboxed environment.",
    tools=[
        ToolDefinition(
            name="code_executor.run_python",
            description=(
                "Execute Python code and return stdout, stderr, and any generated files. "
                "Code runs in an isolated subprocess with a 30-second timeout. "
                "Available libraries: math, json, datetime, collections, itertools, re, statistics, "
                "numpy, pandas, matplotlib, requests, scipy, sympy. "
                "To generate downloadable files (plots, CSVs, etc.), save them to /tmp/ — "
                "e.g. plt.savefig('/tmp/chart.png'). Files are automatically uploaded and "
                "returned as download URLs. Generated files are also saved to the file manager "
                "and can be recalled later with file_manager.list_files. "
                "To work with previously stored files, first use code_executor.load_file to "
                "download them into /tmp/, then reference the local_path in your code."
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
            required_permission="guest",
        ),
        ToolDefinition(
            name="code_executor.load_file",
            description=(
                "Download a previously stored file into /tmp/ so it can be used by run_python. "
                "Use file_manager.list_files to find the file_id first. "
                "Returns the local_path where the file was saved (e.g. /tmp/data.csv). "
                "Then reference that path in your Python code."
            ),
            parameters=[
                ToolParameter(
                    name="file_id",
                    type="string",
                    description="The UUID of the file to load (from file_manager.list_files)",
                ),
            ],
            required_permission="guest",
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
            required_permission="guest",
        ),
    ],
)
