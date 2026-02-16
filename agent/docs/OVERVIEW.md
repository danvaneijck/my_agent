# AI Agent System — Complete Overview

> **Start here** to understand the AI Agent System architecture, components, and how everything fits together.

## What is This System?

The AI Agent System is a modular, self-hosted AI assistant that connects to multiple chat platforms (Discord, Telegram, Slack) and can orchestrate multi-step tasks using pluggable tool modules. It supports multiple LLM providers with automatic fallback and maintains persistent memory with semantic recall.

## Quick Navigation

- **New Developer?** → [Getting Started](development/getting-started.md)
- **Looking for something specific?** → [Documentation Index](INDEX.md)
- **Understanding architecture?** → [Architecture Overview](architecture/overview.md)
- **Adding a feature?** → [Feature Guides](features/)

---

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Communication Layer                      │
│   Discord Bot  │  Telegram Bot  │  Slack Bot  │ Web Portal  │
│   (discord.py)   (python-telegram) (slack-bolt)  (React)    │
└──────┬─────────────────┬────────────────────┬───────────────┘
       │   IncomingMessage (normalized)       │
       ▼                 ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Core                        │
│  ┌──────────────┐ ┌────────────────┐ ┌──────────────────┐  │
│  │  Agent Loop  │ │ Context Builder│ │  Tool Registry   │  │
│  │ (reason/act) │ │ (memory+ctx)   │ │ (HTTP discovery) │  │
│  └──────┬───────┘ └────────────────┘ └─────────┬────────┘  │
│         │                                      │            │
│  ┌──────┴───────┐          ┌──────────────────┐│            │
│  │  LLM Router  │          │  Memory System   ││            │
│  │ Claude/GPT/  │          │ (semantic recall)││            │
│  │  Gemini      │          └──────────────────┘│            │
│  └──────────────┘                              │            │
└────────────────────────────────────────────────┼────────────┘
       │  POST /execute                          │
       ▼                                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Module Layer                           │
│  Research │ Code Exec │ Knowledge │ File Mgr │ Atlassian │  │
│  Claude Code │ Deployer │ Scheduler │ Project Planner │    │
│  Garmin │ Renpho │ Location │ Git Platform │ ...           │
└─────────────────────────────────────────────────────────────┘
       │
┌──────┴──────────────────────────────────────────────────────┐
│                    Infrastructure                           │
│   PostgreSQL (pgvector)  │  Redis  │  MinIO (S3)            │
└─────────────────────────────────────────────────────────────┘
```

**For detailed architecture:** [Architecture Documentation](architecture/)

---

## Core Concepts

### 1. Communication Layer

Platform-specific bots normalize messages and handle file attachments.

- **Discord Bot** (`agent/comms/discord_bot/`) — Discord.py implementation
- **Telegram Bot** (`agent/comms/telegram_bot/`) — python-telegram-bot
- **Slack Bot** (`agent/comms/slack_bot/`) — slack-bolt
- **Web Portal** (`agent/portal/`) — React SPA with FastAPI backend

**Learn more:** [Communication Layer Docs](comms/)

### 2. Orchestrator Core

The brain of the system — handles the agent reasoning loop, routes to modules, and manages LLM providers.

**Key Components:**
- **Agent Loop** — Reason/Act/Observe cycle (up to 10 iterations)
- **Tool Registry** — Discovers modules via HTTP, routes tool calls
- **LLM Router** — Anthropic, OpenAI, Google providers with fallback
- **Context Builder** — Assembles prompts with memory and history
- **Memory System** — Summarization and semantic recall

**Learn more:** [Core Service Docs](core/)

### 3. Module Layer

Independent microservices that provide tools to the LLM.

**Design:**
- Each module is a FastAPI service with `/manifest`, `/execute`, `/health`
- Modules communicate only through the core (LLM orchestrates)
- Discovery via HTTP manifests cached in Redis
- Permission-based filtering

**Available Modules:**
- `research` — Web search, scraping, summarization
- `file_manager` — File CRUD on MinIO
- `code_executor` — Sandboxed Python/shell
- `knowledge` — Persistent memory with embeddings
- `claude_code` — Automated coding via Claude Code CLI
- `deployer` — Deploy projects to live URLs
- `scheduler` — Background jobs and workflows
- `project_planner` — Project management with autonomous execution
- And more...

**Learn more:** [Module Documentation](modules/)

### 4. Infrastructure

**PostgreSQL** — User data, conversations, messages, file records, schedules
**Redis** — Tool manifest caching, job state
**MinIO** — S3-compatible file storage

**Learn more:** [Architecture/Deployment](architecture/deployment.md)

---

## Request Flow

### 1. User sends message on Discord/Telegram/Slack

```
User: "Search for recent AI news and summarize the top 3 articles"
  ↓
Platform Bot receives message
  ↓
Bot downloads any attachments to MinIO
  ↓
Bot creates IncomingMessage
  {
    platform: "discord",
    platform_user_id: "123456",
    content: "Search for recent AI news...",
    attachments: [...]
  }
  ↓
POST /message to Core
```

### 2. Core Orchestrator processes

```
Core receives IncomingMessage
  ↓
Resolve User (auto-create guest if new)
  ↓
Check token budget
  ↓
Resolve Persona (server → platform → default)
  ↓
Resolve/Create Conversation
  ↓
Filter tools by permission + allowed_modules
  ↓
Build Context:
  - System prompt from persona
  - Semantic memories (pgvector similarity)
  - Conversation summary
  - Recent messages
  - File attachment context
  ↓
Enter Agent Loop
```

### 3. Agent Loop (up to 10 iterations)

```
Call LLM with context + available tools
  ↓
LLM returns: stop_reason = "tool_use"
  tool_use: {
    name: "research.web_search",
    arguments: {query: "AI news 2026", max_results: 5}
  }
  ↓
Tool Registry routes to research module
  POST http://research:8000/execute
  {
    tool_name: "research.web_search",
    arguments: {query: "AI news 2026", max_results: 5},
    user_id: "user-uuid"
  }
  ↓
Research module executes, returns:
  {
    success: true,
    result: [{title: "...", url: "...", snippet: "..."}, ...]
  }
  ↓
Append tool result to context
  ↓
LLM calls research.summarize_text on each article
  ↓
LLM synthesizes summary
  ↓
LLM returns: stop_reason = "end_turn"
  ↓
Loop exits
```

### 4. Core returns response

```
Core creates AgentResponse
  {
    content: "Here are the top 3 AI news summaries:\n\n1. ...",
    files: []
  }
  ↓
Returns to bot
```

### 5. Bot sends to user

```
Bot formats response for platform
  ↓
Sends message to Discord/Telegram/Slack
  ↓
User sees response
```

**For detailed flows:** [Architecture/Data Flow](architecture/data-flow.md)

---

## Key Design Decisions

### Microservice Architecture

**Why:** Independent deployment, language flexibility, fault isolation

Each module is a separate Docker container. If one crashes, others keep working.

### HTTP-based Discovery

**Why:** Language-agnostic, runtime reconfiguration, simple debugging

Modules expose `/manifest` — core discovers tools on startup. No hardcoded dependencies.

### LLM as Orchestrator

**Why:** Natural language understanding, flexible workflows, no rigid state machines

The LLM decides which tools to use based on context. Modules never call each other directly.

### Permission-based Filtering

**Why:** Security, multi-tenancy, gradual trust model

Users progress from guest → user → admin → owner. Tools declare required permission levels.

### Persistent Memory

**Why:** Long-term context, user preferences, cross-conversation knowledge

Conversations are summarized and embedded. Semantic search retrieves relevant memories.

**For rationale:** [Architecture/Overview](architecture/overview.md)

---

## Data Model

### Core Entities

- **User** — Permission level, token budget, created_at
- **UserPlatformLink** — Maps platform user IDs to internal user
- **Persona** — System prompt, allowed modules, default model
- **Conversation** — Thread of messages, persona, last active
- **Message** — User/assistant/tool messages with token counts
- **MemorySummary** — Semantic memory with embeddings
- **FileRecord** — Files in MinIO with metadata
- **ScheduledJob** — Background jobs for workflows
- **Project/Phase/Task** — Project planning and execution

**For complete schema:** [Architecture/Database Schema](architecture/database-schema.md)

---

## Module System

### How Modules Work

1. **Registration** — Add to `module_services` in `shared/config.py` and `docker-compose.yml`
2. **Discovery** — Core calls `GET /manifest` on startup
3. **Caching** — Manifests cached in Redis (1-hour TTL)
4. **Filtering** — Core filters by user permission and persona allowed_modules
5. **Execution** — Core POSTs to `/execute` with ToolCall
6. **Response** — Module returns ToolResult (success + result or error)

### Creating a Module

Minimum required:
- `manifest.py` — Tool definitions
- `tools.py` — Async tool implementations
- `main.py` — FastAPI app with /manifest, /execute, /health
- `Dockerfile` — Python 3.12-slim base
- `requirements.txt` — Dependencies

**Complete guide:** [Adding Modules](modules/ADDING_MODULES.md)

---

## LLM Provider System

### Supported Providers

- **Anthropic** — Claude Sonnet, Haiku, etc.
- **OpenAI** — GPT-4o, GPT-4o-mini
- **Google** — Gemini 2.0 Flash

### Fallback Chain

If primary model fails, tries next in chain:
```
claude-sonnet-4 → gpt-4o → gemini-2.0-flash
```

Models requiring unavailable API keys are skipped instantly.

### Adding Providers

1. Create provider class in `core/llm_router/providers/`
2. Implement `BaseLLMProvider` interface
3. Register in `LLMRouter`

**Complete guide:** [Adding LLM Provider](features/adding-llm-provider.md)

---

## Development Workflow

### Quick Start

```bash
# Clone and setup
git clone <repo>
cd my_agent/agent
cp .env.example .env
# Edit .env with API keys

# First time setup
make setup

# Create owner account
make create-owner DISCORD_ID=<your-discord-id>

# Start all services
make up

# View logs
make logs
```

### Common Tasks

| Task | Command |
|------|---------|
| Add a module | `make restart-module M=modulename` |
| Restart core | `make restart-core` |
| Database migration | `make migrate` |
| Refresh tools | `make refresh-tools` |
| PostgreSQL shell | `make psql` |
| Core shell | `make shell` |

**Full reference:** [Makefile Reference](development/makefile-reference.md)

---

## File Organization

```
my_agent/
├── CLAUDE.md              # Main developer guide (quick reference)
├── README.md              # User-facing quick start
├── Makefile               # Top-level commands
├── agent/
│   ├── .env               # Environment configuration
│   ├── docker-compose.yml # Service definitions
│   ├── Makefile           # Agent-specific commands
│   ├── cli.py             # Admin CLI tool
│   │
│   ├── shared/            # Shared Python package
│   │   └── shared/
│   │       ├── config.py         # Pydantic settings
│   │       ├── database.py       # SQLAlchemy setup
│   │       ├── redis.py          # Redis client
│   │       ├── file_utils.py     # MinIO utilities
│   │       ├── models/           # ORM models
│   │       └── schemas/          # Pydantic schemas
│   │
│   ├── core/              # Orchestrator service
│   │   ├── main.py               # FastAPI app
│   │   ├── orchestrator/         # Agent loop, tool registry
│   │   ├── llm_router/           # LLM providers
│   │   └── memory/               # Summarization, recall
│   │
│   ├── comms/             # Platform bots
│   │   ├── discord_bot/
│   │   ├── telegram_bot/
│   │   └── slack_bot/
│   │
│   ├── modules/           # Tool modules
│   │   ├── research/
│   │   ├── file_manager/
│   │   ├── code_executor/
│   │   ├── knowledge/
│   │   ├── claude_code/
│   │   ├── deployer/
│   │   ├── scheduler/
│   │   ├── project_planner/
│   │   └── ...
│   │
│   ├── alembic/           # Database migrations
│   ├── dashboard/         # Streamlit admin dashboard
│   ├── portal/            # Web portal (React + FastAPI)
│   │
│   └── docs/              # Documentation (you are here!)
│       ├── INDEX.md              # Documentation index
│       ├── OVERVIEW.md           # This file
│       ├── architecture/         # System design
│       ├── core/                 # Core service docs
│       ├── comms/                # Communication layer
│       ├── modules/              # Module docs
│       ├── features/             # Implementation guides
│       ├── api-reference/        # API specs
│       ├── development/          # Developer workflows
│       ├── deployment/           # Production guides
│       └── troubleshooting/      # Problem solving
```

---

## Next Steps

### For New Developers

1. [Getting Started](development/getting-started.md) — Setup and first module
2. [Architecture Overview](architecture/overview.md) — Understand the design
3. [Adding Modules](modules/ADDING_MODULES.md) — Create your first module
4. [Code Standards](development/code-standards.md) — Follow conventions

### For Specific Tasks

- **Add a module** → [Adding Modules](modules/ADDING_MODULES.md)
- **Add an LLM provider** → [Adding LLM Provider](features/adding-llm-provider.md)
- **Add a platform bot** → [Adding Platform Bot](features/adding-platform-bot.md)
- **Work with database** → [Adding Database Table](features/adding-database-table.md)
- **Debug an issue** → [Troubleshooting](troubleshooting/)
- **Deploy to production** → [Production Setup](deployment/production-setup.md)

### Deep Dives

- **Agent Loop** → [Agent Loop](core/agent-loop.md)
- **Tool Registry** → [Tool Registry](core/tool-registry.md)
- **LLM Router** → [LLM Router](core/llm-router.md)
- **Memory System** → [Memory System](core/memory-system.md)
- **Module System** → [Module System](architecture/module-system.md)

---

## Documentation Standards

All documentation follows these principles:

1. **Hierarchical**: Overview → Component → Feature
2. **Progressive**: Quick reference first, details below
3. **Agent-Friendly**: Clear headers, tables, code with context
4. **Cross-Referenced**: Explicit links to related docs
5. **Location Aware**: States which files are described
6. **Searchable**: Consistent naming and keywords

---

## Quick Links

- [Documentation Index](INDEX.md) — Complete catalog
- [Architecture](architecture/) — System design
- [Core Services](core/) — Orchestrator internals
- [Modules](modules/) — Tool modules
- [Features](features/) — Implementation guides
- [API Reference](api-reference/) — Schemas and endpoints
- [Development](development/) — Workflows and standards
- [Troubleshooting](troubleshooting/) — Problem solving

---

**Questions?** Check the [Documentation Index](INDEX.md) or file an issue.
