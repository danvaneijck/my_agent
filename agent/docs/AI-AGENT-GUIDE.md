# AI Agent Development Guide

> **For AI Agents**: Optimized documentation navigation and context access patterns for efficient development.

## Quick Context Access Pattern

### When Working on a Feature

1. **Identify your task category** from the list below
2. **Read the primary doc** (1 file, ~5 min)
3. **Read related code** (referenced files with line numbers)
4. **Implement** with provided patterns

**Goal**: ≤3 file reads to get full context for any task.

---

## Task-Based Navigation

### I need to add a new LLM provider

**Read:** [Adding LLM Provider](features/adding-llm-provider.md)

**Related code:**
- `agent/core/llm_router/providers/base.py` — Interface to implement
- `agent/core/llm_router/providers/anthropic.py` — Reference implementation
- `agent/core/llm_router/router.py` — Registration

**Pattern:** Implement `BaseLLMProvider`, register in router, add config

---

### I need to add a new module

**Read:** [Adding Modules](modules/ADDING_MODULES.md)

**Related code:**
- `agent/modules/research/` — Simple reference module
- `agent/modules/project_planner/` — Complex reference module
- `agent/shared/shared/schemas/tools.py` — Tool schemas

**Pattern:** Manifest + Tools + FastAPI + Dockerfile + Register

---

### I need to modify the agent loop

**Read:** [Agent Loop](core/agent-loop.md)

**Related code:**
- `agent/core/orchestrator/agent_loop.py` — Main loop implementation
- `agent/core/orchestrator/context_builder.py` — Context assembly
- `agent/core/orchestrator/tool_registry.py` — Tool execution

**Pattern:** Understand 9-step cycle, modify specific step

---

### I need to add a database table

**Read:** [Adding Database Table](features/adding-database-table.md)

**Related code:**
- `agent/shared/shared/models/` — Existing models
- `agent/alembic/versions/` — Migration examples
- `agent/shared/shared/database.py` — DB setup

**Pattern:** Create model → Generate migration → Apply → Update queries

---

### I need to add a new platform bot

**Read:** [Adding Platform Bot](features/adding-platform-bot.md)

**Related code:**
- `agent/comms/discord_bot/bot.py` — Discord reference
- `agent/comms/telegram_bot/bot.py` — Telegram reference
- `agent/shared/shared/schemas/messages.py` — Message schemas

**Pattern:** Normalize → POST to core → Format response

---

### I need to implement a workflow

**Read:** [Implementing Workflows](features/implementing-workflows.md)

**Related code:**
- `agent/modules/scheduler/tools.py` — Job creation
- `agent/modules/project_planner/tools.py` — Workflow example
- `agent/core/orchestrator/agent_loop.py:234-243` — Resume conversation

**Pattern:** Module1 → Create job → Module2 polls → Resume conversation

---

### I need to work with files

**Read:** [File Pipeline](comms/file-pipeline.md)

**Related code:**
- `agent/shared/shared/file_utils.py` — Upload utilities
- `agent/modules/file_manager/tools.py` — File CRUD
- `agent/modules/code_executor/tools.py` — File generation example

**Pattern:** Upload to MinIO → Create FileRecord → Return in ToolResult

---

### I need to debug an issue

**Read:** [Debugging](development/debugging.md), [Common Issues](troubleshooting/common-issues.md)

**Tools:**
- `make logs-core` — Core service logs
- `make logs-module M=name` — Module logs
- `make psql` — Database inspection
- `make redis-cli` — Redis inspection

**Pattern:** Check logs → Identify layer → Inspect state → Fix

---

### I need to understand the architecture

**Read:** [Architecture Overview](architecture/overview.md)

**Related:**
- [Data Flow](architecture/data-flow.md) — Request lifecycle
- [Module System](architecture/module-system.md) — Module architecture
- [Database Schema](architecture/database-schema.md) — Data model

**Pattern:** Read overview → Dive into specific component

---

## Code Reference Patterns

### Finding File Locations

All documentation includes file paths in this format:

```
agent/core/orchestrator/agent_loop.py:234-243
└─┬─┘ └──┬──┘ └────┬────┘ └──┬──┘ └──┬──┘
  │     │         │         │       └── Line range
  │     │         │         └── Filename
  │     │         └── Directory path
  │     └── Component (core/comms/modules)
  └── Root directory
```

### Reading Code References

When docs say "See `agent/core/orchestrator/agent_loop.py:234-243`":

1. Open `agent/core/orchestrator/agent_loop.py`
2. Jump to lines 234-243
3. That's the exact implementation being discussed

### Understanding Imports

```python
from shared.config import get_settings
└──┬──┘ └─┬─┘       └────┬──────┘
   │      │               └── Function/Class name
   │      └── Module within package
   └── Package (shared/ directory)
```

Maps to: `agent/shared/shared/config.py`

---

## Documentation Structure

### Quick Reference

```
docs/
├── INDEX.md              # Start here for navigation
├── OVERVIEW.md           # System introduction
├── AI-AGENT-GUIDE.md     # This file (agent-optimized)
│
├── architecture/         # System design (read for understanding)
│   ├── overview.md
│   ├── data-flow.md
│   ├── database-schema.md
│   ├── module-system.md
│   └── deployment.md
│
├── core/                 # Core service internals (modify core)
│   ├── agent-loop.md
│   ├── tool-registry.md
│   ├── llm-router.md
│   ├── context-builder.md
│   └── memory-system.md
│
├── comms/                # Platform bots (add platforms)
│   ├── discord-bot.md
│   ├── telegram-bot.md
│   ├── slack-bot.md
│   └── file-pipeline.md
│
├── modules/              # Module docs (add/modify modules)
│   ├── ADDING_MODULES.md
│   ├── overview.md
│   └── <module>.md
│
├── features/             # Implementation guides (how-to)
│   ├── adding-llm-provider.md
│   ├── adding-platform-bot.md
│   ├── adding-database-table.md
│   ├── implementing-workflows.md
│   ├── file-generation.md
│   ├── background-jobs.md
│   └── authentication.md
│
├── api-reference/        # Schemas and APIs (reference)
│   ├── shared-schemas.md
│   ├── database-models.md
│   ├── core-endpoints.md
│   ├── module-contract.md
│   └── shared-utilities.md
│
├── development/          # Dev workflows (setup/testing)
│   ├── getting-started.md
│   ├── testing.md
│   ├── debugging.md
│   ├── makefile-reference.md
│   └── code-standards.md
│
├── deployment/           # Production (deploy/scale)
│   └── ...
│
└── troubleshooting/      # Problem solving (debug)
    ├── common-issues.md
    ├── module-issues.md
    └── ...
```

### Reading Order by Goal

**Understanding the system:**
1. OVERVIEW.md → architecture/overview.md → core/

**Adding a feature:**
1. INDEX.md (find task) → features/<task>.md → code

**Fixing a bug:**
1. troubleshooting/common-issues.md → development/debugging.md → logs

**Building a module:**
1. modules/ADDING_MODULES.md → modules/overview.md → reference modules

---

## Code Patterns

### Module Structure

Every module follows this structure:

```
agent/modules/<name>/
├── __init__.py          # Empty
├── manifest.py          # Tool definitions
├── tools.py             # Tool implementations
├── main.py              # FastAPI app
├── Dockerfile           # Container build
└── requirements.txt     # Dependencies
```

**Always check:** `manifest.py` for tool schema, `tools.py` for implementation.

### FastAPI Endpoint Pattern

All modules expose exactly 3 endpoints:

```python
@app.get("/manifest")      # Returns tool definitions
@app.post("/execute")      # Executes tool calls
@app.get("/health")        # Health check
```

### Database Access Pattern

```python
from shared.database import get_session_factory
from sqlalchemy import select

session_factory = get_session_factory()

async def my_function():
    async with session_factory() as session:
        result = await session.execute(select(Model).where(...))
        obj = result.scalar_one_or_none()
```

### Tool Implementation Pattern

```python
class MyModuleTools:
    async def tool_name(self, param: str, user_id: str | None = None) -> dict:
        """
        Args:
            param: Description
            user_id: Injected by orchestrator

        Returns:
            JSON-serializable dict
        """
        # Implementation
        return {"result": "value"}
```

---

## Common Gotchas

### 1. Module Discovery

**Problem:** New module not available to LLM

**Solution:**
1. Check `module_services` in `agent/shared/shared/config.py`
2. Check service in `agent/docker-compose.yml`
3. Run `make refresh-tools`
4. Restart core: `make restart-core`

### 2. Tool Name Format

**Problem:** Tool not routing correctly

**Solution:** Tool name MUST be `module_name.tool_name`
- ✅ `research.web_search`
- ❌ `research_web_search`
- ❌ `web_search`

### 3. Async/Await

**Problem:** Blocking operations freeze the service

**Solution:** All tool methods must be `async` and use `await` for I/O:
- ✅ `async def tool(): await client.get()`
- ❌ `def tool(): requests.get()`

### 4. Database Timezone

**Problem:** asyncpg rejects tz-aware datetimes

**Solution:** Always use `mapped_column(DateTime(timezone=True))`
- ✅ `created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))`
- ❌ `created_at: Mapped[datetime]` (defaults to tz-naive)

### 5. Tool Permission

**Problem:** Users can't access tool

**Solution:** Check permission levels match:
- Tool `required_permission`: `"guest"` | `"user"` | `"admin"` | `"owner"`
- User `permission_level` must be ≥ required
- Guest (lowest) < User < Admin < Owner (highest)

---

## Testing Patterns

### Unit Test a Tool

```python
import pytest
from modules.my_module.tools import MyModuleTools

@pytest.mark.asyncio
async def test_tool():
    tools = MyModuleTools()
    result = await tools.my_tool(param="value")
    assert result["key"] == "expected"
```

### Integration Test via Core

```bash
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "test",
    "platform_user_id": "test-user",
    "platform_channel_id": "test-channel",
    "content": "Test message that should trigger my tool"
  }'
```

### Check Tool Was Called

```bash
# View module logs
make logs-module M=my_module | grep tool_execution

# Or core logs
make logs-core | grep tool_use
```

---

## Debugging Workflow

### 1. Identify Layer

```
User message not working?
  ↓
Bot layer? → Check make logs-bots
  ↓ no
Core layer? → Check make logs-core
  ↓ no
Module layer? → Check make logs-module M=name
  ↓ no
LLM provider? → Check logs for API errors
```

### 2. Inspect State

```bash
# Database
make psql
SELECT * FROM users WHERE id = '<user-id>';

# Redis
make redis-cli
GET tool_manifest:research

# Files
docker exec -it <container> ls /tmp/
```

### 3. Test Isolation

```bash
# Test module directly
curl http://localhost:8000/modules/research/execute \
  -X POST -H "Content-Type: application/json" \
  -d '{"tool_name": "research.web_search", "arguments": {"query": "test"}}'

# Test core endpoint
curl http://localhost:8000/message \
  -X POST -H "Content-Type: application/json" \
  -d '<message-json>'
```

---

## Performance Tips

### 1. Use Caching

Tool manifests are cached in Redis (1-hour TTL).

**Force refresh:** `make refresh-tools`

### 2. Limit Context Size

Long conversations slow down:
- Conversations are auto-summarized
- Recent messages are windowed
- Old messages don't affect performance

### 3. Async All the Way

```python
# ✅ Fast
async def tool():
    async with httpx.AsyncClient() as client:
        return await client.get(url)

# ❌ Slow (blocks event loop)
def tool():
    return requests.get(url)
```

### 4. Database Connection Pooling

Session factory handles pooling automatically:

```python
# ✅ Correct (uses pool)
async with session_factory() as session:
    ...

# ❌ Wrong (creates new connection each time)
engine = create_async_engine(...)
async with AsyncSession(engine) as session:
    ...
```

---

## Quick Command Reference

```bash
# Service Management
make up                    # Start all services
make down                  # Stop all services
make restart-core          # Rebuild & restart core
make restart-module M=name # Rebuild & restart module

# Logs
make logs                  # All services
make logs-core             # Core only
make logs-module M=name    # Specific module
make logs-bots             # All bots

# Database
make psql                  # PostgreSQL shell
make migrate               # Run migrations
make shell                 # Core container shell → alembic commands

# Redis
make redis-cli             # Redis shell

# Tools
make refresh-tools         # Re-discover module manifests
make list-modules          # Module health status

# Testing
pytest                     # Run all tests
pytest path/to/test.py     # Specific test
```

---

## Documentation Standards for Code Changes

When you modify code, update docs:

### 1. New Feature → Update Feature Docs

Added LLM provider? Update `features/adding-llm-provider.md` with example.

### 2. API Change → Update API Reference

Changed schema? Update `api-reference/shared-schemas.md`.

### 3. New Module → Create Module Doc

Follow template from existing module docs.

### 4. Bug Fix → Update Troubleshooting

Common issue? Add to `troubleshooting/common-issues.md`.

---

## Getting Help

### Documentation Not Clear?

1. Check [INDEX.md](INDEX.md) for alternative docs
2. Search existing modules for examples
3. Check [Troubleshooting](troubleshooting/)

### Code Not Working?

1. Check logs: `make logs-core`, `make logs-module M=name`
2. Read [Debugging](development/debugging.md)
3. Check [Common Issues](troubleshooting/common-issues.md)

### Understanding Architecture?

1. Read [OVERVIEW.md](OVERVIEW.md)
2. Read [Architecture](architecture/overview.md)
3. Trace code through [Agent Loop](core/agent-loop.md)

---

## Summary: Context Access in 3 Steps

1. **Find task** in [INDEX.md](INDEX.md) "When to Read" column
2. **Read guide** (features/ or core/ doc)
3. **Check code** (file paths in doc + line numbers)

**Total time:** 5-15 minutes to full context for any task.

---

**Next Steps:**
- New to system? → [Getting Started](development/getting-started.md)
- Building feature? → [Features](features/)
- Debugging? → [Troubleshooting](troubleshooting/)

[Back to Documentation Index](INDEX.md)
