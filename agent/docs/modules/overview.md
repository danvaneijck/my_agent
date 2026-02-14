# Module System Overview

## How Modules Work

Modules are independent FastAPI microservices that provide tools to the LLM. The core orchestrator discovers modules on startup, filters tools by user permissions, and routes tool calls during the agent loop.

Modules never call each other directly — the LLM is the orchestrator. It decides which tools to invoke based on the conversation context and available tool definitions.

## Discovery & Registration

1. Core reads `module_services` from `shared/config.py` — a dict mapping module name to internal URL (e.g. `"research": "http://research:8000"`)
2. On startup, core calls `GET /manifest` on each module
3. Manifests are cached in Redis with a 1-hour TTL
4. Use `make refresh-tools` to force re-discovery

**Key file:** `agent/core/orchestrator/tool_registry.py`

## Tool Execution Flow

```
User message → Core /message endpoint
  → Agent loop resolves user, persona, conversation
  → Tool registry filters tools by user permission + persona allowed_modules
  → LLM receives context + filtered tool definitions
  → LLM returns tool_use with tool name + arguments
  → Core injects user_id (and platform context for scheduler/location)
  → Core POSTs to module: POST {module_url}/execute with ToolCall payload
  → Module executes tool, returns ToolResult
  → Core appends result to context, loops back to LLM
  → LLM either calls more tools or returns final text
  → Core returns AgentResponse to bot
```

## Shared Schemas

Defined in `agent/shared/shared/schemas/tools.py`:

- **`ModuleManifest`** — `module_name`, `description`, `tools: list[ToolDefinition]`
- **`ToolDefinition`** — `name` (format: `module.tool_name`), `description`, `parameters: list[ToolParameter]`, `required_permission`
- **`ToolParameter`** — `name`, `type`, `description`, `required` (default true), `enum` (optional)
- **`ToolCall`** — `tool_name`, `arguments: dict`, `user_id: str | None`
- **`ToolResult`** — `tool_name`, `success: bool`, `result: Any`, `error: str | None`

## Permission Filtering

Each tool declares `required_permission`: `guest`, `user`, `admin`, or `owner`.

The hierarchy is `guest < user < admin < owner`. A user with `admin` permission can access tools requiring `admin`, `user`, or `guest`. The orchestrator filters tools before sending them to the LLM, so users never see tools they can't use.

Personas can further restrict which modules are available via `allowed_modules` (JSON array of module names).

## User Context Injection

Before executing a tool call, the orchestrator injects:
- `user_id` — always injected so modules can associate resources with the calling user
- `platform`, `platform_channel_id`, `platform_thread_id` — injected for scheduler and location tools so they can send notifications back
- `conversation_id` — injected for `scheduler.add_job` so the `resume_conversation` mode can re-enter the correct conversation

**Key file:** `agent/core/orchestrator/agent_loop.py` (lines 234-243)

## Timeouts

- Default tool execution timeout: 30 seconds
- Slow modules get 120 seconds: `myfitnesspal`, `garmin`, `renpho_biometrics`, `claude_code`, `deployer`
- Configured via `settings.slow_modules` in `shared/config.py`

## Workflow Chaining

Modules can be chained into multi-step workflows via the scheduler:

1. `claude_code.run_task` starts a coding task, returns `task_id`
2. `scheduler.add_job` polls `claude_code.task_status` with `on_complete="resume_conversation"`
3. When the task completes, the scheduler worker calls core `/continue` to re-enter the agent loop
4. The LLM sees the completion message and can call `deployer.deploy` with the workspace path

This enables autonomous build-then-deploy pipelines without human intervention.

## File Pipeline Integration

Two modules share the file pipeline:
- **file_manager** — CRUD for files stored in MinIO, tracked via `FileRecord` in PostgreSQL
- **code_executor** — auto-uploads files saved to `/tmp/` during Python execution, creates `FileRecord` entries so they appear in `file_manager.list_files`

Files uploaded by bots are also registered as `FileRecord` entries by core after user resolution.

## Workspace Contract (claude_code + deployer)

The `claude_code` module creates workspaces at `/tmp/claude_tasks/{task_id}/`. This path is returned by `run_task` and `task_status`. The `deployer.deploy` tool accepts this path as `project_path` to deploy the generated project. Both modules access the same Docker host filesystem via volume mounts.

## Standard Module Structure

Every module follows the same file layout:

```
agent/modules/<name>/
├── __init__.py          # Empty
├── Dockerfile
├── requirements.txt
├── main.py              # FastAPI app: /manifest, /execute, /health
├── manifest.py          # ToolDefinition list
└── tools.py             # Async tool implementations
```

See `agent/docs/ADDING_MODULES.md` for the full guide on creating new modules.

## Module Infrastructure Requirements

| Module | DB | MinIO | Redis | External |
|--------|:--:|:-----:|:-----:|----------|
| research | | | | DuckDuckGo |
| file_manager | x | x | | |
| code_executor | x | x | | |
| knowledge | x | | | Core /embed |
| atlassian | | | | Jira/Confluence API |
| claude_code | | | | Docker socket |
| deployer | | | | Docker socket |
| scheduler | x | | x | |
| garmin | | | | Garmin Connect |
| renpho_biometrics | | | | Renpho API |
| location | x | | x | OwnTracks, geocoder |
| git_platform | x | | | GitHub/Bitbucket API |
| myfitnesspal | | | | MyFitnessPal API |
| injective | | | | Injective RPC |
