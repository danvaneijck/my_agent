# AI Agent System — Developer Guide

## Quick Reference

```
Project root:   /home/user/my_agent
App code:       /home/user/my_agent/agent/
Compose file:   agent/docker-compose.yml
Shared package: agent/shared/shared/
Models:         agent/shared/shared/models/
Schemas:        agent/shared/shared/schemas/
Core service:   agent/core/
Modules:        agent/modules/<name>/
Bots:           agent/comms/<platform>_bot/
Migrations:     agent/alembic/versions/
Makefile:       Makefile (top-level, wraps docker compose)
```

## Architecture Overview

```
 Discord / Telegram / Slack
         │
    Communication Layer (bots)
         │  POST /message (IncomingMessage → AgentResponse)
         ▼
    Core Orchestrator (FastAPI :8000)
    ├── Agent Loop (reason/act/observe cycle, up to 10 iterations)
    ├── LLM Router (Anthropic, OpenAI, Google — with fallback chain)
    ├── Context Builder (system prompt + memories + history)
    └── Tool Registry (discovers modules via GET /manifest)
         │  POST /execute (ToolCall → ToolResult)
         ▼
    Module Layer (independent FastAPI microservices)
    ├── research          — web search, scraping, news
    ├── file_manager      — file CRUD on MinIO + DB records
    ├── code_executor     — sandboxed Python/shell execution
    ├── knowledge         — persistent per-user memory with embeddings
    ├── atlassian         — Jira + Confluence integration
    ├── claude_code       — coding tasks via Claude Code CLI in Docker
    ├── deployer          — deploy projects to live URLs
    ├── scheduler         — background job monitoring + notifications
    ├── garmin            — Garmin Connect health/fitness data
    ├── renpho_biometrics — Renpho smart scale body composition
    ├── location          — OwnTracks geofence reminders + tracking
    ├── project_planner   — project planning, tracking + autonomous execution
    └── injective         — blockchain trading (scaffold)

 Infrastructure: PostgreSQL+pgvector │ Redis │ MinIO (S3)
```

All services communicate over the `agent-net` Docker bridge network. Services are containerized with Python 3.12-slim base images.

## Module Documentation

Detailed per-module docs live in `agent/docs/modules/`:

- [Module System Overview](agent/docs/modules/overview.md) — discovery, routing, permissions, workflow chaining
- [research](agent/docs/modules/research.md) — web search, news, scraping, summarization
- [file_manager](agent/docs/modules/file_manager.md) — file CRUD on MinIO + DB records
- [code_executor](agent/docs/modules/code_executor.md) — sandboxed Python/shell execution
- [knowledge](agent/docs/modules/knowledge.md) — semantic memory with pgvector embeddings
- [atlassian](agent/docs/modules/atlassian.md) — Jira + Confluence integration
- [claude_code](agent/docs/modules/claude_code.md) — coding tasks via Claude Code CLI in Docker
- [deployer](agent/docs/modules/deployer.md) — deploy projects to live URLs
- [scheduler](agent/docs/modules/scheduler.md) — background jobs + workflow chaining
- [garmin](agent/docs/modules/garmin.md) — Garmin Connect health/fitness data
- [renpho_biometrics](agent/docs/modules/renpho_biometrics.md) — Renpho smart scale body composition
- [location](agent/docs/modules/location.md) — OwnTracks geofence reminders + tracking
- [git_platform](agent/docs/modules/git_platform.md) — GitHub/Bitbucket repos, issues, PRs, CI
- [myfitnesspal](agent/docs/modules/myfitnesspal.md) — nutrition and meal tracking
- [project_planner](agent/docs/modules/project_planner.md) — project planning, tracking + autonomous execution
- [injective](agent/docs/modules/injective.md) — blockchain spot and perpetual trading

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Web framework | FastAPI + uvicorn |
| Database | PostgreSQL 16 with pgvector extension |
| ORM | SQLAlchemy 2.0 (async, via asyncpg) |
| Migrations | Alembic |
| Cache | Redis 7 |
| File storage | MinIO (S3-compatible) |
| LLM SDKs | `anthropic`, `openai`, `google-genai` |
| Logging | structlog (JSON output) |
| Config | pydantic-settings v2 |
| Container orchestration | Docker Compose |
| Admin dashboard | Streamlit |

## Database Schema

All tables use UUID primary keys and `DateTime(timezone=True)` for timestamps.

```
users
  id                    UUID PK
  permission_level      str        — "guest" | "user" | "admin" | "owner"
  token_budget_monthly  int | null — null = unlimited
  tokens_used_this_month int
  budget_reset_at       datetime(tz)
  created_at            datetime(tz)

user_platform_links
  id                    UUID PK
  user_id               UUID FK → users.id
  platform              str        — "discord" | "telegram" | "slack"
  platform_user_id      str
  platform_username     str | null
  UNIQUE(platform, platform_user_id)

personas
  id                    UUID PK
  name                  str
  system_prompt         text
  platform              str | null   — scope to a platform
  platform_server_id    str | null   — scope to a server/guild
  allowed_modules       str (JSON)   — e.g. '["research","file_manager"]'
  default_model         str | null
  max_tokens_per_request int         — default 4000
  is_default            bool
  created_at            datetime(tz)

conversations
  id                    UUID PK
  user_id               UUID FK → users.id
  persona_id            UUID FK → personas.id (nullable)
  platform              str
  platform_channel_id   str
  platform_thread_id    str | null
  started_at            datetime(tz)
  last_active_at        datetime(tz)
  is_summarized         bool

messages
  id                    UUID PK
  conversation_id       UUID FK → conversations.id
  role                  str        — "user" | "assistant" | "system" | "tool_call" | "tool_result"
  content               text
  token_count           int | null
  model_used            str | null
  created_at            datetime(tz)

memory_summaries
  id                    UUID PK
  user_id               UUID FK → users.id
  conversation_id       UUID FK → conversations.id (nullable)
  summary               text
  embedding             Vector(1536)
  created_at            datetime(tz)

token_logs
  id                    UUID PK
  user_id               UUID FK → users.id
  conversation_id       UUID FK → conversations.id
  model                 str
  input_tokens          int
  output_tokens         int
  cost_estimate         float | null
  created_at            datetime(tz)

file_records
  id                    UUID PK
  user_id               UUID FK → users.id
  filename              str
  minio_key             str        — path within MinIO bucket
  mime_type             str | null
  size_bytes            int | null
  public_url            str
  created_at            datetime(tz)

scheduled_jobs
  id                    UUID PK
  user_id               UUID FK → users.id
  conversation_id       UUID FK → conversations.id (nullable)
  platform              str
  platform_channel_id   str
  platform_thread_id    str | null
  job_type              str        — "poll_module" | "delay" | "poll_url"
  check_config          JSON
  interval_seconds      int        — default 30
  max_attempts          int        — default 120
  attempts              int        — default 0
  on_success_message    text
  on_failure_message    text | null
  status                str        — "active" | "completed" | "failed" | "cancelled"
  next_run_at           datetime(tz)
  created_at            datetime(tz)
  completed_at          datetime(tz) | null

user_locations
  id                    UUID PK
  user_id               UUID FK → users.id (unique)
  latitude              float
  longitude             float
  accuracy_m            float | null
  speed_mps             float | null
  heading               float | null
  source                str        — default "owntracks"
  updated_at            datetime(tz)
  created_at            datetime(tz)

location_reminders
  id                    UUID PK
  user_id               UUID FK → users.id
  conversation_id       UUID FK → conversations.id (nullable)
  message               str
  place_name            str
  place_lat             float
  place_lng             float
  radius_m              int        — default 150
  platform              str | null
  platform_channel_id   str | null
  platform_thread_id    str | null
  owntracks_rid         str        — OwnTracks region ID
  synced_to_device      bool       — default false
  status                str        — "active" | "triggered" | "cancelled" | "expired"
  triggered_at          datetime(tz) | null
  expires_at            datetime(tz) | null
  cooldown_until        datetime(tz) | null
  created_at            datetime(tz)

user_named_places
  id                    UUID PK
  user_id               UUID FK → users.id
  name                  str
  latitude              float
  longitude             float
  address               str | null
  created_at            datetime(tz)
  UNIQUE(user_id, name)

owntracks_credentials
  id                    UUID PK
  user_id               UUID FK → users.id
  username              str (unique)
  password_hash         str
  device_name           str | null
  is_active             bool       — default true
  last_seen_at          datetime(tz) | null
  created_at            datetime(tz)

projects
  id                    UUID PK
  user_id               UUID FK → users.id
  name                  str
  description           text | null
  design_document       text | null       — full markdown design doc
  repo_owner            str | null
  repo_name             str | null
  default_branch        str               — default "main"
  auto_merge            bool              — default false
  status                str               — "planning" | "active" | "paused" | "completed" | "archived"
  created_at            datetime(tz)
  updated_at            datetime(tz)
  UNIQUE(user_id, name)

project_phases
  id                    UUID PK
  project_id            UUID FK → projects.id (CASCADE)
  name                  str
  description           text | null
  order_index           int               — sort order within project
  status                str               — "planned" | "in_progress" | "completed"
  created_at            datetime(tz)
  updated_at            datetime(tz)

project_tasks
  id                    UUID PK
  phase_id              UUID FK → project_phases.id (CASCADE)
  project_id            UUID FK → projects.id (CASCADE)
  user_id               UUID FK → users.id
  title                 str
  description           text | null
  acceptance_criteria   text | null
  order_index           int               — sort order within phase
  status                str               — "todo" | "doing" | "in_review" | "done" | "failed"
  branch_name           str | null
  pr_number             int | null
  issue_number          int | null
  claude_task_id        str | null
  error_message         text | null
  started_at            datetime(tz) | null
  completed_at          datetime(tz) | null
  created_at            datetime(tz)
  updated_at            datetime(tz)
```

**ORM models** are in `agent/shared/shared/models/`. Each model file exports a single class.

**Important**: Always use `mapped_column(DateTime(timezone=True))` for datetime fields. asyncpg rejects tz-aware datetimes against `TIMESTAMP WITHOUT TIME ZONE`.

### Adding a New Table

1. Create model in `agent/shared/shared/models/new_thing.py`
2. Import it in `agent/shared/shared/models/__init__.py`
3. Create Alembic migration: `make shell` then `alembic revision --autogenerate -m "add new_thing table"`
4. Apply: `make migrate`

## Configuration (Settings)

All config is in `agent/shared/shared/config.py` using pydantic-settings. Environment variables are loaded from `agent/.env`.

Key settings:
- `database_url` — PostgreSQL async connection string
- `redis_url` — Redis connection
- `minio_endpoint`, `minio_access_key`, `minio_secret_key`, `minio_bucket`, `minio_public_url`
- `anthropic_api_key`, `openai_api_key`, `google_api_key` — LLM provider keys
- `default_model` — Primary chat model (default: `claude-sonnet-4-20250514`)
- `fallback_chain` — Comma-separated fallback models
- `module_services` — Dict mapping module name → internal HTTP URL
- `discord_token`, `telegram_token`, `slack_bot_token`, `slack_app_token`

**Gotcha**: `list[str]` fields break with pydantic-settings v2 when env vars contain plain strings like `VAR=foo,bar`. Use `str` type and the `parse_list()` helper at point of use instead.

## How to Implement a New Module

Modules are independent FastAPI microservices. The orchestrator discovers them via `GET /manifest` and routes tool calls via `POST /execute`. Full guide: `agent/docs/ADDING_MODULES.md`.

### File Structure

```
agent/modules/my_module/
├── __init__.py          # Empty
├── Dockerfile
├── requirements.txt
├── main.py              # FastAPI app: /manifest, /execute, /health
├── manifest.py          # ToolDefinition list
└── tools.py             # Async tool method implementations
```

### Step 1: Define the Manifest (`manifest.py`)

```python
from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="my_module",
    description="What this module does.",
    tools=[
        ToolDefinition(
            name="my_module.do_thing",           # MUST be "module_name.tool_name"
            description="Clear description for the LLM to read.",
            parameters=[
                ToolParameter(name="query", type="string", description="...", required=True),
                ToolParameter(name="limit", type="integer", description="...", required=False),
            ],
            required_permission="guest",         # guest | user | admin | owner
        ),
    ],
)
```

Parameter types: `string`, `integer`, `number`, `boolean`, `array`, `object`.

### Step 2: Implement Tools (`tools.py`)

```python
import structlog

logger = structlog.get_logger()

class MyModuleTools:
    def __init__(self):
        pass  # initialize clients, DB connections, etc.

    async def do_thing(self, query: str, limit: int = 10) -> dict:
        """Method name MUST match the part after the dot in tool name."""
        return {"results": [...], "count": 5}
```

- Methods must be `async`
- Method parameter names must match manifest parameter names
- Return any JSON-serializable value (dict, list, str, int, bool)
- Raise exceptions on failure — main.py catches them
- Accept `user_id: str | None = None` if you need user context (injected by orchestrator)

### Step 3: Create the FastAPI App (`main.py`)

```python
from fastapi import FastAPI
from modules.my_module.manifest import MANIFEST
from modules.my_module.tools import MyModuleTools
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult
from shared.schemas.common import HealthResponse

app = FastAPI(title="My Module")
tools: MyModuleTools | None = None

@app.on_event("startup")
async def startup():
    global tools
    tools = MyModuleTools()

@app.get("/manifest", response_model=ModuleManifest)
async def manifest():
    return MANIFEST

@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall):
    if tools is None:
        return ToolResult(tool_name=call.tool_name, success=False, error="Module not ready")
    try:
        tool_name = call.tool_name.split(".")[-1]
        args = dict(call.arguments)
        if call.user_id:
            args["user_id"] = call.user_id
        if tool_name == "do_thing":
            result = await tools.do_thing(**args)
        else:
            return ToolResult(tool_name=call.tool_name, success=False, error=f"Unknown tool: {call.tool_name}")
        return ToolResult(tool_name=call.tool_name, success=True, result=result)
    except Exception as e:
        return ToolResult(tool_name=call.tool_name, success=False, error=str(e))

@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
```

### Step 4: Dockerfile

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/
COPY modules/my_module/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY modules/ /app/modules/
ENV PYTHONPATH="/app:/shared"
EXPOSE 8000
CMD ["uvicorn", "modules.my_module.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Step 5: requirements.txt

```
fastapi>=0.109
uvicorn[standard]>=0.27
structlog>=24.1
pydantic>=2.5
pydantic-settings>=2.1
# Add sqlalchemy>=2.0, asyncpg>=0.29 if using DB
# Add minio>=7.2 if using file storage
```

### Step 6: Register the Module

**a) `agent/shared/shared/config.py`** — Add to `module_services` dict:
```python
"my_module": "http://my-module:8000",
```

**b) `agent/docker-compose.yml`** — Add service block:
```yaml
  my-module:
    build:
      context: .
      dockerfile: modules/my_module/Dockerfile
    env_file: .env
    depends_on:
      - core
    networks:
      - agent-net
    restart: unless-stopped
```

Add `postgres` / `minio` to `depends_on` if your module accesses them directly.

**Note**: Docker service name uses hyphens (`my-module`), Python module name uses underscores (`my_module`). The hostname on the Docker network is the service name.

### Step 7: Build and Start

```bash
make build-module M=my-module
make up
make refresh-tools  # tell core to re-discover manifests
```

## Shared Package Usage

All services install `agent/shared/` as a Python package. Import from `shared.*`:

```python
from shared.config import get_settings, parse_list
from shared.database import get_session_factory
from shared.models.user import User
from shared.models.file import FileRecord
from shared.schemas.tools import ToolCall, ToolResult, ModuleManifest
from shared.schemas.messages import IncomingMessage, AgentResponse
```

### Database Access

```python
from shared.database import get_session_factory
from sqlalchemy import select

session_factory = get_session_factory()

async def my_function():
    async with session_factory() as session:
        result = await session.execute(select(User).where(User.id == some_id))
        user = result.scalar_one_or_none()
```

### MinIO Access

```python
from minio import Minio
from shared.config import get_settings

settings = get_settings()
minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=False,
)
```

### Embeddings (via Core API)

```python
import httpx
from shared.config import get_settings

settings = get_settings()

async def get_embedding(text: str) -> list[float] | None:
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(f"{settings.orchestrator_url}/embed", json={"text": text})
        if resp.status_code == 200:
            return resp.json().get("embedding")
    return None
```

## Core Orchestrator Internals

### Agent Loop (`agent/core/orchestrator/agent_loop.py`)

The main reasoning cycle:

1. **Resolve user** — maps `(platform, platform_user_id)` → `User` record (auto-creates guests)
2. **Check budget** — verify monthly token allowance
3. **Resolve persona** — server-specific → platform-specific → default
4. **Resolve conversation** — find active conversation in channel/thread or create new one
5. **Filter tools** — by user `permission_level` and persona's `allowed_modules`
6. **Register attachments** — create `FileRecord` entries, enrich user message with file context
7. **Build context** — system prompt + semantic memories (pgvector) + conversation summary + recent messages
8. **Loop** (up to `max_agent_iterations`, default 10):
   - Call LLM with context + tools
   - If stop_reason is `tool_use`: execute tools, append results to context, continue
   - Otherwise: break with final text content
9. **Return** `AgentResponse(content, files)`

### LLM Router (`agent/core/llm_router/router.py`)

- Routes to Anthropic (Claude), OpenAI (GPT-4o), or Google (Gemini) based on model name
- Fallback chain: tries next provider if primary fails
- Providers only registered if their API key is set
- Each provider normalizes to a common `LLMResponse` format

### Tool Registry (`agent/core/orchestrator/tool_registry.py`)

- On startup, fetches `GET /manifest` from each module in `module_services`
- Caches manifests in Redis (1-hour TTL)
- Filters tools by user permission level before sending to LLM
- Routes `POST /execute` to the correct module by splitting tool name on first `.`

## Communication Layer (Bots)

Each bot follows the same pattern:

1. Receive platform event (message, mention, etc.)
2. Normalize to `IncomingMessage` (with attachments uploaded to MinIO)
3. POST to core `/message`
4. Format `AgentResponse` for the platform
5. Send reply (with file attachments downloaded from MinIO for inline display)

Key files:
- `agent/comms/discord_bot/bot.py` — Discord.py client
- `agent/comms/telegram_bot/bot.py` — python-telegram-bot
- `agent/comms/slack_bot/bot.py` — slack-bolt

Shared file upload utility: `agent/shared/shared/file_utils.py` — `upload_attachment()` uploads raw bytes to MinIO and returns metadata dict (no DB writes — core creates FileRecords after user resolution).

## Makefile Commands

```bash
make setup              # First-time: build, migrate, create bucket + default persona, start all
make up                 # Start all services
make down               # Stop all services
make build              # Rebuild all images
make build-core         # Rebuild core image
make build-module M=x   # Rebuild specific module
make restart-core       # Rebuild + restart core
make restart-module M=x # Rebuild + restart a module
make restart-bots       # Restart all bots
make logs               # Tail all logs
make logs-core          # Tail core logs
make logs-module M=x    # Tail module logs
make logs-bots          # Tail bot logs
make create-owner DISCORD_ID=123  # Create owner user
make list-users         # List users
make list-modules       # Show module health
make refresh-tools      # Re-discover module manifests
make shell              # Bash into core container
make psql               # PostgreSQL shell
make redis-cli          # Redis CLI
make migrate            # Run Alembic migrations
```

## Permission Levels

From lowest to highest: `guest` → `user` → `admin` → `owner`

- Each tool declares `required_permission` in its manifest
- The orchestrator filters tools so users only see what they're allowed to use
- Guests are auto-created on first message with a limited token budget
- Budget is `null` (unlimited) for admin/owner

## Known Gotchas

### pydantic-settings v2
`list[str]` fields fail with plain env vars like `VAR=foo,bar` — pydantic-settings attempts JSON parse in `decode_complex_value` BEFORE field validators run. **Fix**: use `str` type and `parse_list()` at point of use.

### asyncpg + DateTime
`Mapped[datetime]` maps to `TIMESTAMP WITHOUT TIME ZONE`. asyncpg rejects tz-aware datetimes for it. **Fix**: always use `mapped_column(DateTime(timezone=True), ...)` in models.

### Google GenAI SDK
- Use `contents=` (plural), not `content=` for `embed_content`
- `gemini-embedding-001` outputs 3072 dims by default; use `EmbedContentConfig(output_dimensionality=1536)` to match `Vector(1536)` in DB
- Function names must be alphanumeric + underscore (no dots). The Google provider sanitizes with `__` and maintains a reverse `name_map`
- `MALFORMED_FUNCTION_CALL` is a known transient Gemini issue — the provider retries automatically

### Docker
- Bots with `restart: unless-stopped` + `sys.exit(1)` on missing tokens = crash-loop log spam. Use `time.sleep(86400)` to idle instead
- Module DNS may not resolve when core starts — core has delayed background retry for manifest discovery
- Never create `alembic/__init__.py` in the migrations dir — it shadows the `alembic` library

### Dependencies
- DuckDuckGo search library is `ddgs` (renamed from `duckduckgo-search`), same API: `from ddgs import DDGS`
- `slack-bolt` async mode needs `aiohttp` but doesn't declare it as a hard dependency

### Cross-Container DB Visibility
Use `session.commit()` (not `session.flush()`) when another container needs to see the data. `flush()` writes within the local transaction only.

## File Pipeline

### User uploads a file (Discord/Telegram/Slack)
1. Bot downloads the file from platform CDN
2. Bot uploads to MinIO via `upload_attachment()` from `shared/file_utils.py`
3. Bot sends `IncomingMessage` with `attachments: [{filename, url, minio_key, mime_type, size_bytes}]`
4. Core creates `FileRecord` in DB with the real `user_id` (bots don't know internal user IDs)
5. Core enriches the user message with file context (file_id, usage hints)
6. LLM can use `file_manager.read_document(file_id)` or `code_executor.load_file(file_id)` to access the file

### Agent generates a file (e.g., code_executor creates a plot)
1. Code executor saves to `/tmp/`, detects new files, uploads to MinIO
2. Code executor creates `FileRecord` in DB
3. Tool result includes `files: [{filename, url, minio_key}]`
4. Orchestrator extracts file URLs from tool results (both top-level `url` and nested `files[]`)
5. Bot downloads files from MinIO (internal network) and attaches as native platform files

## Existing Module Reference

| Module | Tools | Infrastructure | Permission |
|---|---|---|---|
| `research` | `web_search`, `news_search`, `fetch_webpage`, `summarize_text` | None | guest |
| `file_manager` | `create_document`, `upload_file`, `read_document`, `list_files`, `get_file_link`, `delete_file` | PostgreSQL, MinIO | guest |
| `code_executor` | `run_python`, `run_shell`, `load_file` | PostgreSQL, MinIO | guest/user |
| `knowledge` | `remember`, `recall`, `list_memories`, `forget` | PostgreSQL (pgvector) | guest |
| `atlassian` | `jira_search`, `jira_get_issue`, `jira_create_issue`, `jira_update_issue`, `confluence_search`, `confluence_get_page`, `confluence_create_page`, `confluence_update_page`, `create_meeting_notes`, `create_feature_doc` | None (external API) | user |
| `claude_code` | `run_task`, `continue_task`, `task_status`, `task_logs`, `cancel_task`, `list_tasks` | Docker socket | admin |
| `deployer` | `deploy`, `list_deployments`, `teardown`, `teardown_all`, `get_logs` | Docker socket | user/admin |
| `scheduler` | `add_job`, `list_jobs`, `cancel_job` | PostgreSQL, Redis | admin |
| `garmin` | `get_daily_summary`, `get_heart_rate`, `get_sleep`, `get_body_composition`, `get_activities`, `get_stress`, `get_steps` | None (external API) | user |
| `renpho_biometrics` | `get_measurements`, `get_latest`, `get_trend` | None (external API) | user |
| `location` | `create_reminder`, `list_reminders`, `cancel_reminder`, `get_location`, `set_named_place`, `generate_pairing_credentials` | PostgreSQL, Redis | user |
| `project_planner` | `create_project`, `update_project`, `get_project`, `list_projects`, `delete_project`, `add_phase`, `update_phase`, `add_task`, `bulk_add_tasks`, `update_task`, `get_task`, `get_phase_tasks`, `get_next_task`, `get_project_status` | PostgreSQL | user/admin |
| `injective` | `get_portfolio`, `get_market_price`, `place_order`, `cancel_order`, `get_positions` | None (scaffold) | owner |
