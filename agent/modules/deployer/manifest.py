"""Deployer module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="deployer",
    description=(
        "Deploy projects to live URLs. Supports React, Next.js, static sites, "
        "Node.js servers, and custom Dockerfiles. Inject env vars to link "
        "frontends to backend APIs."
    ),
    tools=[
        ToolDefinition(
            name="deployer.deploy",
            description=(
                "Deploy a project from a local path to a running container with a live URL. "
                "Supports project types: react, nextjs, static, node, docker. "
                "Pass env_vars to inject environment variables (e.g. API URLs for "
                "frontend-backend linking)."
            ),
            parameters=[
                ToolParameter(
                    name="project_path",
                    type="string",
                    description=(
                        "Absolute path to the project directory "
                        "(e.g. /tmp/claude_tasks/{task_id}/)."
                    ),
                    required=True,
                ),
                ToolParameter(
                    name="project_name",
                    type="string",
                    description="Human-readable name for the deployment.",
                    required=True,
                ),
                ToolParameter(
                    name="project_type",
                    type="string",
                    description="Type of project to deploy (default: react).",
                    enum=["react", "nextjs", "static", "node", "docker"],
                    required=False,
                ),
                ToolParameter(
                    name="container_port",
                    type="integer",
                    description=(
                        "Internal port the app listens on. Auto-detected by default: "
                        "80 for react/static, 3000 for nextjs/node, 8000 for docker."
                    ),
                    required=False,
                ),
                ToolParameter(
                    name="env_vars",
                    type="object",
                    description=(
                        'Environment variables to inject into the container, e.g. '
                        '{"REACT_APP_API_URL": "http://localhost:4001"}.'
                    ),
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="deployer.list_deployments",
            description="List all active deployments with their URLs, status, and metadata.",
            parameters=[],
            required_permission="user",
        ),
        ToolDefinition(
            name="deployer.teardown",
            description="Stop and remove a deployment by its deploy_id. Frees the allocated port.",
            parameters=[
                ToolParameter(
                    name="deploy_id",
                    type="string",
                    description="The deployment ID to tear down.",
                    required=True,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="deployer.teardown_all",
            description="Stop and remove ALL active deployments.",
            parameters=[],
            required_permission="admin",
        ),
        ToolDefinition(
            name="deployer.get_logs",
            description="Get the last N lines of logs from a deployment container.",
            parameters=[
                ToolParameter(
                    name="deploy_id",
                    type="string",
                    description="The deployment ID to get logs from.",
                    required=True,
                ),
                ToolParameter(
                    name="lines",
                    type="integer",
                    description="Number of log lines to return (default 50).",
                    required=False,
                ),
            ],
            required_permission="user",
        ),
    ],
)
