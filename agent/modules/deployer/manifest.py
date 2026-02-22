"""Deployer module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="deployer",
    description=(
        "Deploy projects to live URLs. Supports React, Next.js, static sites, "
        "Node.js servers, custom Dockerfiles, and docker-compose stacks. "
        "Inject env vars to link frontends to backend APIs."
    ),
    tools=[
        ToolDefinition(
            name="deployer.deploy",
            description=(
                "Deploy a project from a local path to a running container with a live URL. "
                "Supports project types: react, nextjs, static, node, docker, compose. "
                "If the path is a workspace root, the actual project subdirectory "
                "is auto-detected. If a docker-compose.yml is present, the project is "
                "automatically deployed as a compose stack. "
                "Pass env_vars to inject environment variables (e.g. API URLs for "
                "frontend-backend linking).\n\n"
                "URL PATTERN: The deployed URL is https://{slug}.apps.danvan.xyz where "
                "{slug} is the slugified project_name (lowercase, special chars → hyphens). "
                "For compose stacks with multiple exposed services, the first service gets "
                "the primary slug and additional services get https://{slug}-{service}.apps.danvan.xyz. "
                "IMPORTANT: When building projects with a frontend that calls a backend API, "
                "use these predictable URLs in the code or via environment variables — "
                "never use localhost. For example, if project_name is 'My Todo App' and "
                "the compose backend service is named 'backend', the frontend should call "
                "https://my-todo-app-backend.apps.danvan.xyz instead of http://localhost:8000."
            ),
            parameters=[
                ToolParameter(
                    name="project_path",
                    type="string",
                    description=(
                        "Absolute path to the project directory "
                        "(e.g. /tmp/claude_tasks/{task_id}/). If the project "
                        "is in a subdirectory, it will be auto-detected."
                    ),
                    required=True,
                ),
                ToolParameter(
                    name="project_name",
                    type="string",
                    description=(
                        "Human-readable name for the deployment. This determines the "
                        "subdomain: slugified to lowercase with hyphens "
                        "(e.g. 'My Todo App' → my-todo-app → https://my-todo-app.apps.danvan.xyz)."
                    ),
                    required=True,
                ),
                ToolParameter(
                    name="project_type",
                    type="string",
                    description=(
                        "Type of project to deploy. Auto-detected if omitted. "
                        "'compose' for docker-compose stacks."
                    ),
                    enum=["react", "nextjs", "static", "node", "docker", "compose"],
                    required=False,
                ),
                ToolParameter(
                    name="container_port",
                    type="integer",
                    description=(
                        "Internal port the app listens on (single-container only). "
                        "Auto-detected by default: "
                        "3000 for react/nextjs/static/node, 8000 for docker."
                    ),
                    required=False,
                ),
                ToolParameter(
                    name="env_vars",
                    type="object",
                    description=(
                        'Environment variables to inject. For compose projects, '
                        'these are written to a .env file next to docker-compose.yml. '
                        'For single containers, injected as -e flags. '
                        'Example: {"VITE_API_URL": "https://my-app-backend.apps.danvan.xyz"}.'
                    ),
                    required=False,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="deployer.list_deployments",
            description="List all active deployments with their URLs, status, services, and ports.",
            parameters=[],
            required_permission="user",
        ),
        ToolDefinition(
            name="deployer.teardown",
            description=(
                "Stop and remove a deployment by its deploy_id. "
                "For compose deployments, removes all services and networks."
            ),
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
            description=(
                "Get the last N lines of logs from a deployment. "
                "For compose deployments, returns combined logs from all services."
            ),
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
        ToolDefinition(
            name="deployer.get_services",
            description=(
                "List services in a compose deployment with live status, ports, and images."
            ),
            parameters=[
                ToolParameter(
                    name="deploy_id",
                    type="string",
                    description="The deployment ID.",
                    required=True,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="deployer.get_service_logs",
            description="Get logs for a specific service in a compose deployment.",
            parameters=[
                ToolParameter(
                    name="deploy_id",
                    type="string",
                    description="The deployment ID.",
                    required=True,
                ),
                ToolParameter(
                    name="service_name",
                    type="string",
                    description="The service name (from docker-compose.yml).",
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
        ToolDefinition(
            name="deployer.get_env_vars",
            description="Get current environment variables for a deployment.",
            parameters=[
                ToolParameter(
                    name="deploy_id",
                    type="string",
                    description="The deployment ID.",
                    required=True,
                ),
            ],
            required_permission="user",
        ),
        ToolDefinition(
            name="deployer.update_env_vars",
            description=(
                "Update environment variables for a deployment. "
                "For compose projects, writes to .env file and optionally restarts services."
            ),
            parameters=[
                ToolParameter(
                    name="deploy_id",
                    type="string",
                    description="The deployment ID.",
                    required=True,
                ),
                ToolParameter(
                    name="env_vars",
                    type="object",
                    description="Key-value pairs to set or update.",
                    required=True,
                ),
                ToolParameter(
                    name="restart",
                    type="boolean",
                    description="Whether to restart services after updating (default true).",
                    required=False,
                ),
            ],
            required_permission="admin",
        ),
        ToolDefinition(
            name="deployer.restart",
            description="Restart a deployment (all services for compose, container for single).",
            parameters=[
                ToolParameter(
                    name="deploy_id",
                    type="string",
                    description="The deployment ID to restart.",
                    required=True,
                ),
            ],
            required_permission="admin",
        ),
    ],
)
