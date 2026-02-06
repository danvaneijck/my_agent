# Adding New Modules to the AI Agent System

This guide explains how to create a new module that plugs into the agent system. Use this document as context when prompting an LLM to build a module for you.

---

## How Modules Work

A module is an independent FastAPI microservice running in Docker. The orchestrator discovers it by calling `GET /manifest`, which returns the list of tools the module provides. When the LLM decides to use a tool, the orchestrator calls `POST /execute` on the module with the tool name and arguments.

**Key facts:**
- Modules run on the `agent-net` Docker network alongside all other services.
- Modules have access to the shared `.env` file and can use the `shared` Python package for config, database, Redis, and schemas.
- The orchestrator routes tool calls based on the prefix of the tool name (e.g. `my_module.do_thing` routes to the `my_module` service).
- The orchestrator enforces permissions — the module just declares what permission level each tool requires.
- Modules are independently deployable. The system keeps working if a module is stopped.

---

## Step-by-Step: Create a Module

Replace `my_module` with your actual module name throughout.

### 1. Create the directory

```
agent/modules/my_module/
├── __init__.py          # Empty file
├── Dockerfile
├── requirements.txt
├── main.py              # FastAPI app with /manifest, /execute, /health
├── manifest.py          # Tool definitions
└── tools.py             # Tool implementations
```

### 2. Define the manifest (`manifest.py`)

The manifest tells the orchestrator what tools this module provides. Each tool needs a globally unique name prefixed with the module name.

```python
"""My Module manifest — tool definitions."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="my_module",
    description="Short description of what this module does.",
    tools=[
        ToolDefinition(
            name="my_module.do_something",
            description="Clear description of what this tool does. The LLM reads this to decide when to use it.",
            parameters=[
                ToolParameter(
                    name="query",
                    type="string",
                    description="Description of this parameter",
                ),
                ToolParameter(
                    name="limit",
                    type="integer",
                    description="Optional param with default",
                    required=False,
                ),
                ToolParameter(
                    name="mode",
                    type="string",
                    description="Constrained to specific values",
                    enum=["fast", "thorough"],
                    required=False,
                ),
            ],
            required_permission="guest",  # or "user", "admin", "owner"
        ),
        # Add more ToolDefinition entries for additional tools...
    ],
)
```

**Schema reference:**

| Schema | Fields |
|---|---|
| `ModuleManifest` | `module_name: str`, `description: str`, `tools: list[ToolDefinition]` |
| `ToolDefinition` | `name: str`, `description: str`, `parameters: list[ToolParameter]`, `required_permission: str` |
| `ToolParameter` | `name: str`, `type: str`, `description: str`, `required: bool = True`, `enum: list[str] \| None` |

**Tool naming convention:** Always `module_name.tool_name`. The orchestrator splits on the first `.` to route to the correct module.

**Parameter types:** `string`, `integer`, `number`, `boolean`, `array`, `object`

**Permission levels (lowest to highest):** `guest`, `user`, `admin`, `owner`

### 3. Implement the tools (`tools.py`)

Each tool is an async method that accepts the declared parameters and returns a dict (or list, or any JSON-serializable value).

```python
"""My Module tool implementations."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class MyModuleTools:
    """Tool implementations for my module."""

    def __init__(self, some_dependency=None):
        # Initialize clients, connections, etc.
        self.dep = some_dependency

    async def do_something(self, query: str, limit: int = 10, mode: str = "fast") -> dict:
        """Implementation of the do_something tool."""
        # Your logic here
        return {
            "results": [...],
            "count": 5,
        }
```

**Important conventions:**
- Method names must match the part after the `.` in the tool name (e.g. `my_module.do_something` → method `do_something`).
- Methods must be `async`.
- Method parameters must match the names declared in `manifest.py`.
- Return JSON-serializable data (dicts, lists, strings, numbers, booleans).
- Raise exceptions on failure — the `main.py` handler catches them and returns an error `ToolResult`.

### 4. Create the FastAPI app (`main.py`)

Every module must implement exactly three endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/manifest` | GET | Return the `ModuleManifest` |
| `/execute` | POST | Receive a `ToolCall`, return a `ToolResult` |
| `/health` | GET | Return `{"status": "ok"}` |

```python
"""My Module - FastAPI service."""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from modules.my_module.manifest import MANIFEST
from modules.my_module.tools import MyModuleTools
from shared.config import get_settings
from shared.schemas.common import HealthResponse
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()
app = FastAPI(title="My Module", version="1.0.0")

settings = get_settings()
tools: MyModuleTools | None = None


@app.on_event("startup")
async def startup():
    global tools
    # Initialize your tools class with any dependencies
    tools = MyModuleTools()
    logger.info("my_module_ready")


@app.get("/manifest", response_model=ModuleManifest)
async def manifest():
    """Return the module manifest."""
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall):
    """Execute a tool call."""
    if tools is None:
        return ToolResult(tool_name=call.tool_name, success=False, error="Module not ready")

    try:
        # Strip module prefix to get the method name
        tool_name = call.tool_name.split(".")[-1]

        if tool_name == "do_something":
            result = await tools.do_something(**call.arguments)
        # elif tool_name == "other_tool":
        #     result = await tools.other_tool(**call.arguments)
        else:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        return ToolResult(tool_name=call.tool_name, success=True, result=result)
    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e))
        return ToolResult(tool_name=call.tool_name, success=False, error=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
```

**The `/execute` endpoint contract:**

- Receives: `{"tool_name": "my_module.do_something", "arguments": {"query": "hello", "limit": 5}}`
- Returns on success: `{"tool_name": "my_module.do_something", "success": true, "result": {...}, "error": null}`
- Returns on failure: `{"tool_name": "my_module.do_something", "success": false, "result": null, "error": "description of what went wrong"}`

### 5. Create the Dockerfile

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install module requirements
COPY modules/my_module/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY modules/ /app/modules/

ENV PYTHONPATH="/app:/shared"

EXPOSE 8000

CMD ["uvicorn", "modules.my_module.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6. Create `requirements.txt`

Always include the base dependencies for the shared package, plus your module-specific deps:

```
# Base (required by all modules)
fastapi>=0.109
uvicorn[standard]>=0.27
structlog>=24.1
pydantic>=2.5
pydantic-settings>=2.1
sqlalchemy>=2.0
asyncpg>=0.29
pgvector>=0.3
redis>=5.0
tiktoken>=0.5

# Module-specific
# your-library>=1.0
```

### 7. Create an empty `__init__.py`

```python
# agent/modules/my_module/__init__.py
```

### 8. Register the module in three places

**a) `agent/shared/shared/config.py`** — Add to `module_services` default dict:

```python
module_services: dict[str, str] = {
    "research": "http://research:8000",
    "file_manager": "http://file-manager:8000",
    "injective": "http://injective:8000",
    "my_module": "http://my-module:8000",  # <-- add this
}
```

**b) `agent/docker-compose.yml`** — Add a service block under `# --- Modules ---`:

```yaml
  my-module:
    build:
      context: .
      dockerfile: modules/my_module/Dockerfile
    env_file: .env
    depends_on:
      - core   # or other infrastructure services your module needs
    networks:
      - agent-net
    restart: unless-stopped
```

Note: The Docker service name (`my-module` with a hyphen) maps to the hostname on the Docker network. The config entry must match: `"http://my-module:8000"`.

**c) Persona `allowed_modules`** — If you want the default persona to have access to your module, update the persona's `allowed_modules` JSON list. You can do this via the CLI:

```bash
python cli.py persona create --name "Updated" --prompt "..." --modules research,file_manager,my_module
```

Or update the default persona creation in `cli.py` to include it.

---

## Using Infrastructure from Your Module

### Database (PostgreSQL)

Modules can read/write to the shared database using the `shared` package:

```python
from shared.database import get_session_factory
from shared.models.user import User  # or any model

session_factory = get_session_factory()

async def my_tool():
    async with session_factory() as session:
        result = await session.execute(select(User).where(...))
        ...
```

If your module needs its own tables, add a new model in `shared/shared/models/` and create an Alembic migration.

### Redis

```python
from shared.redis import get_redis

async def my_tool():
    redis = await get_redis()
    await redis.set("key", "value", ex=3600)
    value = await redis.get("key")
```

### MinIO (file storage)

```python
from minio import Minio
from shared.config import get_settings

settings = get_settings()
client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False,
)
```

### Orchestrator API (for LLM calls from modules)

If your module needs to call the LLM (e.g. for summarization), POST to the orchestrator:

```python
import httpx
from shared.config import get_settings

settings = get_settings()

async def call_llm(prompt: str) -> str:
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{settings.orchestrator_url}/message",
            json={
                "platform": "internal",
                "platform_user_id": "system",
                "platform_channel_id": "my_module",
                "content": prompt,
            },
        )
        return resp.json().get("content", "")
```

---

## Environment Variables

All modules share the same `.env` file. If your module needs custom config:

1. Add the variable to `.env.example`
2. Add a field to `Settings` in `shared/shared/config.py`
3. Access it via `get_settings().your_new_field`

---

## Checklist

When building a new module, make sure you have:

- [ ] `modules/my_module/__init__.py` (empty)
- [ ] `modules/my_module/manifest.py` with `MANIFEST` — tool names prefixed with `my_module.`
- [ ] `modules/my_module/tools.py` with async methods matching each tool name
- [ ] `modules/my_module/main.py` with `/manifest`, `/execute`, `/health` endpoints
- [ ] `modules/my_module/Dockerfile`
- [ ] `modules/my_module/requirements.txt`
- [ ] Service entry in `docker-compose.yml`
- [ ] URL entry in `module_services` dict in `shared/shared/config.py`
- [ ] Module name added to relevant persona `allowed_modules` lists

---

## Prompt Template for Creating Modules

Copy this into a fresh prompt along with this document to have an LLM build a module for you:

```
I have a modular AI agent system. I need you to create a new module called "[MODULE_NAME]".

The module should provide these tools:
- [tool 1 description]
- [tool 2 description]

[Any specific libraries, APIs, or implementation details]

Follow the module creation guide in docs/ADDING_MODULES.md exactly. Create all required files:
1. modules/[MODULE_NAME]/__init__.py
2. modules/[MODULE_NAME]/manifest.py
3. modules/[MODULE_NAME]/tools.py
4. modules/[MODULE_NAME]/main.py
5. modules/[MODULE_NAME]/Dockerfile
6. modules/[MODULE_NAME]/requirements.txt

Then update the registration points:
7. Add the service URL to module_services in shared/shared/config.py
8. Add the service block to docker-compose.yml

Permission level for tools: [guest/user/admin/owner]
```

---

## Existing Modules for Reference

| Module | Directory | Tools | Notes |
|---|---|---|---|
| `research` | `modules/research/` | `web_search`, `fetch_webpage`, `summarize_text` | Uses duckduckgo-search, httpx, beautifulsoup4 |
| `file_manager` | `modules/file_manager/` | `create_document`, `list_files`, `get_file_link`, `delete_file` | Connects to MinIO and PostgreSQL |
| `injective` | `modules/injective/` | `get_portfolio`, `get_market_price`, `place_order`, `cancel_order`, `get_positions` | Scaffold with mock data, all owner-only |
