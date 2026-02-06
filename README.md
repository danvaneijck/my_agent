# AI Agent System

A modular, self-hosted AI agent that connects to Discord, Telegram, and Slack. The agent can orchestrate multi-step tasks using pluggable modules (web research, file management, blockchain trading, etc.), supports multiple LLM providers, and maintains persistent memory with intelligent context management.

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
│   Research     │  File Manager  │  Injective  │  (yours)    │
│   (web search,   (MinIO CRUD)    (scaffold)     ...         │
│    scrape, etc.)                                            │
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

This builds all containers, starts Postgres/Redis/MinIO, runs database migrations, creates the MinIO bucket, and creates a default persona.

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
make setup           # First-time setup (migrations, bucket, default persona)
make migrate         # Run database migrations
make refresh-tools   # Re-discover module manifests
make shell           # Open a shell in the core container
make psql            # Open a PostgreSQL shell
```

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

Personas control the system prompt, which modules are available, and which LLM model to use.

```bash
# Create a persona bound to a specific Discord server
docker compose exec core python /app/cli.py persona create \
  --name "Research Bot" \
  --prompt "You are a research assistant. Be thorough and cite sources." \
  --platform discord \
  --server-id 123456789 \
  --modules research,file_manager

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

## Modules

| Module | Tools | Description |
|--------|-------|-------------|
| `research` | `web_search`, `fetch_webpage`, `summarize_text` | Search the web, scrape pages, summarize content |
| `file_manager` | `create_document`, `list_files`, `get_file_link`, `delete_file` | Create and manage documents in MinIO storage |
| `injective` | `get_portfolio`, `get_market_price`, `place_order`, `cancel_order`, `get_positions` | Blockchain trading (scaffold, owner-only) |

### Adding New Modules

See [docs/ADDING_MODULES.md](agent/docs/ADDING_MODULES.md) for a complete guide and prompt template.

## LLM Providers

The system supports multiple providers with automatic fallback:

| Provider | Models | Required Key |
|----------|--------|-------------|
| Anthropic | Claude Sonnet, Haiku, etc. | `ANTHROPIC_API_KEY` |
| OpenAI | GPT-4o, GPT-4o-mini, embeddings | `OPENAI_API_KEY` |
| Google | Gemini 2.0 Flash, etc. | `GOOGLE_API_KEY` |

Configure the default model and task-specific routing in `.env`:

```env
DEFAULT_MODEL=claude-sonnet-4-20250514    # Main chat model
SUMMARIZATION_MODEL=gpt-4o-mini           # Used for memory summarization
EMBEDDING_MODEL=text-embedding-3-small    # Used for semantic recall
```

If the primary model fails, the system tries the fallback chain: Claude -> GPT-4o -> Gemini.

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
│   ├── file_manager/
│   └── injective/
├── alembic/         # Database migrations
├── nginx/           # Reverse proxy config
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
