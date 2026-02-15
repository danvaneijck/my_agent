# ModuFlow

**Your Modular AI Agent Framework**

A professional, modular AI agent framework for building intelligent assistants that orchestrate multi-step tasks. Connect to Discord, Telegram, and Slack with a plug-and-play architecture featuring web research, code execution, persistent memory, file management, and more. Supports multiple LLM providers with automatic fallback.

🌐 **Production**: [agent.danvan.xyz](https://agent.danvan.xyz)

## Features

- **Modular Architecture**: Plug-and-play modules for extensible functionality
- **Multi-Platform Support**: Discord, Telegram, and Slack integrations
- **Multi-LLM Support**: Anthropic Claude, OpenAI GPT, Google Gemini with automatic fallback
- **Persistent Memory**: Semantic recall using pgvector for context-aware conversations
- **Background Jobs**: Scheduler for long-running tasks and proactive notifications
- **Code Execution**: Sandboxed Python and shell execution with popular data science libraries
- **File Management**: MinIO-backed storage for documents and generated files
- **Web Research**: Search, scraping, and summarization capabilities
- **Development Tools**: Claude Code integration for autonomous coding tasks
- **Project Deployment**: Deploy React, Next.js, and Node.js projects to live URLs
- **Health & Fitness**: Garmin and Renpho integrations for personal data tracking
- **Location Services**: OwnTracks integration for geofence reminders
- **Atlassian Integration**: Jira and Confluence automation
- **Self-Hosted**: Full control over your data and infrastructure

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Communication Layer                      │
│   Discord Bot  │  Telegram Bot  │  Slack Bot                │
│   (discord.py)   (python-telegram-bot) (slack-bolt)         │
└──────┬─────────────────┬────────────────────┬───────────────┘
       │   IncomingMessage (normalized)       │
       ▼                 ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                    Orchestrator Core                        │
│  ┌──────────────┐ ┌────────────────┐ ┌──────────────────┐   │
│  │  Agent Loop  │ │ Context Builder│ │  Tool Registry   │   │
│  │ (reason/act) │ │ (memory+ctx)   │ │ (HTTP discovery) │   │
│  └──────┬───────┘ └────────────────┘ └─────────┬────────┘   │
│         │                                      │            │
│  ┌──────┴───────┐          ┌──────────────────┐│            │
│  │  LLM Router  │          │  Memory System   ││            │
│  │ Claude/GPT/  │          │ (summarizer +    ││            │
│  │  Gemini      │          │  semantic recall)││            │
│  └──────────────┘          └──────────────────┘│            │
└────────────────────────────────────────────────┼────────────┘
       │  POST /execute                          │
       ▼                                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Module Layer                           │
│  Research │ Code Exec │ Knowledge │ File Mgr │ Atlassian │  ...  │
│  (search,   (Python/    (remember/   (MinIO    (Jira/          │
│   scrape)    shell)      recall)      CRUD)    Confluence)     │
│  Claude Code │ Deployer │ Scheduler │ Garmin │ Renpho │ Loc.  │
│  (coding in    (live URL   (background  (health  (body    (geo- │
│   Docker)       deploy)     jobs)       data)    comp)   fence)│
└─────────────────────────────────────────────────────────────┘
       │
┌──────┴──────────────────────────────────────────────────────┐
│                    Infrastructure                           │
│   PostgreSQL (pgvector)  │  Redis  │  MinIO (S3)            │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Configure environment

```bash
cd agent
cp .env.example .env
```

Edit `.env` and fill in at minimum:
- `POSTGRES_PASSWORD` — any secure password
- At least one LLM API key (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GOOGLE_API_KEY`)
- At least one platform bot token (`DISCORD_TOKEN`, `TELEGRAM_TOKEN`, or `SLACK_BOT_TOKEN` + `SLACK_APP_TOKEN`)

### 2. Start infrastructure and run setup

```bash
make setup
```

This builds all containers, starts Postgres/Redis/MinIO, runs database migrations, and creates the MinIO bucket. A default persona is automatically created on first startup with access to all registered modules.

### 3. Create your owner account

```bash
make create-owner DISCORD_ID=123456789
# or with multiple platforms:
make create-owner DISCORD_ID=123 TELEGRAM_ID=456 SLACK_ID=789
```

### 4. Start everything

```bash
make up
```

### 5. Message your bot

Send a message to your bot on Discord/Telegram/Slack. It will respond using the configured LLM and available tools.

## Common Operations

```bash
make up              # Start all services
make down            # Stop all services
make restart         # Restart all services
make logs            # Tail logs from all services
make logs-core       # Tail logs from core only
make status          # Show service status
make setup           # First-time setup (migrations, bucket)
make migrate         # Run database migrations
make refresh-tools   # Re-discover module manifests
make shell           # Open a shell in the core container
make psql            # Open a PostgreSQL shell
```

## Modules

| Module | Tools | Description |
|--------|-------|-------------|
| `research` | `web_search`, `fetch_webpage`, `summarize_text`, `news_search` | Search the web, scrape pages, summarize content, search recent news |
| `code_executor` | `run_python`, `run_shell` | Execute Python code (with numpy, pandas, matplotlib, scipy, sympy, requests) and shell commands in sandboxed subprocesses |
| `knowledge` | `remember`, `recall`, `list_memories`, `forget` | Persistent per-user knowledge base with semantic search via pgvector |
| `file_manager` | `create_document`, `list_files`, `get_file_link`, `delete_file`, `read_document` | Create, read, and manage documents in MinIO storage |
| `atlassian` | `jira_search`, `jira_get_issue`, `jira_create_issue`, `jira_update_issue`, `confluence_search`, `confluence_get_page`, `confluence_create_page`, `confluence_update_page`, `create_meeting_notes`, `create_feature_doc` | Jira and Confluence integration — search, create, update issues and pages; structured meeting notes and feature docs with optional Jira ticket creation |
| `claude_code` | `run_task`, `continue_task`, `task_status`, `task_logs`, `cancel_task`, `list_tasks` | Execute coding tasks using Claude Code CLI in disposable Docker containers; iterate on existing workspaces |
| `deployer` | `deploy`, `list_deployments`, `teardown`, `teardown_all`, `get_logs` | Deploy projects (React, Next.js, static, Node, Docker) to live URLs with environment variable injection |
| `scheduler` | `add_job`, `list_jobs`, `cancel_job` | Background job scheduler for monitoring long-running tasks and sending proactive notifications |
| `garmin` | `get_daily_summary`, `get_heart_rate`, `get_sleep`, `get_body_composition`, `get_activities`, `get_stress`, `get_steps` | Fetch health, fitness, and activity data from Garmin Connect |
| `renpho_biometrics` | `get_measurements`, `get_latest`, `get_trend` | Fetch body composition and biometric data from Renpho smart scales |
| `location` | `create_reminder`, `list_reminders`, `cancel_reminder`, `get_location`, `set_named_place`, `generate_pairing_credentials` | Location-based reminders via OwnTracks geofences, named places, and GPS tracking |
| `injective` | `get_portfolio`, `get_market_price`, `place_order`, `cancel_order`, `get_positions` | Blockchain trading (scaffold, owner-only) |

### Adding New Modules

See [docs/ADDING_MODULES.md](agent/docs/ADDING_MODULES.md) for a complete guide and prompt template.

## Admin Dashboard

A web-based analytics dashboard is available at `http://localhost:8501` (configurable via `DASHBOARD_PORT`). It shows:

- User statistics and token usage
- Conversation history
- System health (Postgres, Redis, MinIO)
- Tool usage breakdown
- Platform distribution
- Persona management overview

## User Management

```bash
# Create the owner account (unlimited tokens, all permissions)
make create-owner DISCORD_ID=123456789

# Promote a user
docker compose exec core python /app/cli.py user promote \
  --platform discord --platform-id 123456789 --level admin

# Set a token budget
docker compose exec core python /app/cli.py user set-budget \
  --platform discord --platform-id 123456789 --tokens 50000

# List all users
docker compose exec core python /app/cli.py user list
```

## Persona Management

Personas control the system prompt, which modules are available, and which LLM model to use. A default persona is automatically created at startup with access to all registered modules, and is updated whenever new modules are added.

```bash
# Create a persona bound to a specific Discord server
docker compose exec core python /app/cli.py persona create \
  --name "Research Bot" \
  --prompt "You are a research assistant. Be thorough and cite sources." \
  --platform discord \
  --server-id 123456789 \
  --modules research,file_manager,code_executor,knowledge

# List personas
docker compose exec core python /app/cli.py persona list

# Set the default persona
docker compose exec core python /app/cli.py persona set-default --id <persona-uuid>
```

## Permission Levels

| Level | Description | Default Budget |
|-------|-------------|----------------|
| `owner` | Full access to all tools including trading | Unlimited |
| `admin` | Access to admin-level tools | Unlimited |
| `user` | Standard access | Configurable |
| `guest` | Auto-created on first message, limited modules | 5,000 tokens/month |

## LLM Providers

The system supports multiple providers with automatic fallback. Only one API key is required — the system automatically selects a working default model based on available providers.

| Provider | Models | Required Key |
|----------|--------|-------------|
| Anthropic | Claude Sonnet, Haiku, etc. | `ANTHROPIC_API_KEY` |
| OpenAI | GPT-4o, GPT-4o-mini, embeddings | `OPENAI_API_KEY` |
| Google | Gemini 2.0 Flash, embeddings | `GOOGLE_API_KEY` |

If the primary model fails, the system tries the fallback chain. Models requiring unavailable providers are skipped instantly.

## Project Structure

```
agent/
├── shared/          # Shared Python package (config, models, schemas)
├── core/            # Orchestrator service (FastAPI)
│   ├── orchestrator/  # Agent loop, context builder, tool registry
│   ├── llm_router/    # Provider abstraction (Anthropic, OpenAI, Google)
│   └── memory/        # Summarizer and semantic recall
├── comms/           # Platform bots
│   ├── discord_bot/
│   ├── telegram_bot/
│   └── slack_bot/
├── modules/         # Pluggable tool modules
│   ├── research/
│   ├── code_executor/
│   ├── knowledge/
│   ├── file_manager/
│   ├── atlassian/
│   ├── claude_code/
│   ├── deployer/
│   ├── scheduler/
│   ├── garmin/
│   ├── renpho_biometrics/
│   ├── location/
│   └── injective/
├── dashboard/       # Admin analytics dashboard
├── alembic/         # Database migrations
├── nginx/           # Reverse proxy config
├── docs/            # Documentation
├── cli.py           # Admin CLI
└── docker-compose.yml
```

## Development

```bash
make build           # Rebuild all Docker images
make build-core      # Rebuild just the core service
make build-module M=research  # Rebuild a specific module
make restart-core    # Rebuild and restart core
make restart-module M=research  # Rebuild and restart a module
```

### Running individual services locally

For development outside Docker, install the shared package first:

```bash
cd agent/shared && pip install -e .
```

Then run any service:

```bash
cd agent && uvicorn core.main:app --reload --port 8000
```

You'll need Postgres, Redis, and MinIO running (use `make infra` to start just infrastructure).

## Documentation

- **[Brand Guidelines](agent/docs/BRANDING.md)** - Logo usage, color palette, typography, and brand voice
- **[Adding Modules](agent/docs/ADDING_MODULES.md)** - Complete guide for creating new modules
- **[Portal Documentation](agent/docs/portal.md)** - Web portal setup and usage
- **[Module Documentation](agent/docs/modules/)** - Detailed docs for each module

## Branding

ModuFlow uses a modern, professional brand identity:

- **Colors**: Indigo (#6366f1) primary, Teal (#06b6d4) secondary
- **Font**: Inter from Google Fonts
- **Logo**: Connected hexagons representing modular architecture
- **Theme**: Dark-first design optimized for developer experience

See the [Brand Guidelines](agent/docs/BRANDING.md) for complete details.

## License

This project is open source and available for personal and commercial use.

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.
