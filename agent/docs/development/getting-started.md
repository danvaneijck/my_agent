# Getting Started — Developer Onboarding

> **Quick Start**: Set up your development environment and create your first module in under 30 minutes.

## What You'll Learn

By the end of this guide, you'll:
- Have a fully functional local development environment
- Understand the system architecture
- Create and test your first module
- Know where to find documentation for any task

---

## Prerequisites

### Required

- **Docker** and **Docker Compose** (v2+)
- **Git**
- **Python 3.12+** (for local development outside Docker)
- **Make** (usually pre-installed on Linux/Mac)

### Recommended

- **Code editor** with Python support (VS Code, PyCharm, etc.)
- **curl** or **Postman** for API testing
- **PostgreSQL client** for database inspection

### Required Knowledge

- Basic Python (async/await, type hints)
- REST APIs and HTTP
- Docker basics
- Git basics

---

## Step 1: Clone and Configure (5 minutes)

### Clone the Repository

```bash
git clone <repository-url>
cd my_agent
```

### Configure Environment

```bash
cd agent
cp .env.example .env
```

Edit `.env` and set **at minimum**:

```bash
# Required: Database password (choose any secure password)
POSTGRES_PASSWORD=your_secure_password_here

# Required: At least one LLM API key
ANTHROPIC_API_KEY=sk-ant-...
# OR
OPENAI_API_KEY=sk-...
# OR
GOOGLE_API_KEY=...

# Required: At least one platform bot token
DISCORD_TOKEN=...
# OR
TELEGRAM_TOKEN=...
# OR
SLACK_BOT_TOKEN=... and SLACK_APP_TOKEN=...
```

**Don't have API keys yet?**
- Anthropic: https://console.anthropic.com/
- OpenAI: https://platform.openai.com/
- Google: https://aistudio.google.com/
- Discord: https://discord.com/developers/applications
- Telegram: https://t.me/BotFather
- Slack: https://api.slack.com/apps

---

## Step 2: Initial Setup (10 minutes)

### Run First-Time Setup

This builds all containers, runs migrations, and creates infrastructure:

```bash
make setup
```

What this does:
1. Builds all Docker images (core, modules, bots)
2. Starts PostgreSQL, Redis, MinIO
3. Runs database migrations
4. Creates MinIO bucket
5. Creates default persona

**Expected output:**
```
Building images...
Starting infrastructure...
Running migrations...
✓ Setup complete!
```

### Create Your Owner Account

```bash
# If using Discord:
make create-owner DISCORD_ID=<your-discord-user-id>

# If using multiple platforms:
make create-owner DISCORD_ID=123 TELEGRAM_ID=456

# If only Telegram:
make create-owner TELEGRAM_ID=<your-telegram-user-id>
```

**How to find your Discord ID:**
1. Enable Developer Mode in Discord settings
2. Right-click your username
3. Click "Copy ID"

**How to find your Telegram ID:**
1. Message @userinfobot on Telegram
2. It will reply with your ID

---

## Step 3: Start the System (2 minutes)

```bash
make up
```

This starts all services. You should see:
```
Starting postgres...
Starting redis...
Starting minio...
Starting core...
Starting discord-bot...
Starting research...
Starting file-manager...
... (all modules)
```

### Verify Services Are Running

```bash
# Check status
make status

# View logs
make logs
```

**All services should show "healthy" or "running".**

---

## Step 4: Test the System (5 minutes)

### Test via Platform Bot

Send a message to your bot on Discord/Telegram/Slack:

```
Hey! Can you search the web for "Python async tutorial"?
```

You should get a response with search results.

### Test via API (Optional)

```bash
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "test",
    "platform_user_id": "test-user",
    "platform_channel_id": "test-channel",
    "content": "Hello! What can you do?"
  }'
```

---

## Step 5: Explore the System (5 minutes)

### View Logs

```bash
# All services
make logs

# Just core
make logs-core

# Specific module
make logs-module M=research

# Follow logs in real-time
make logs-core
# Press Ctrl+C to exit
```

### Access Admin Dashboard

Open http://localhost:8501 in your browser.

You'll see:
- User statistics
- Token usage
- Conversation history
- System health

### Inspect Database

```bash
make psql
```

Try some queries:
```sql
-- View users
SELECT id, permission_level, created_at FROM users;

-- View conversations
SELECT id, platform, started_at FROM conversations LIMIT 5;

-- View messages
SELECT role, LEFT(content, 50) as content_preview, created_at
FROM messages
ORDER BY created_at DESC
LIMIT 10;

-- Exit
\q
```

### Check Redis

```bash
make redis-cli
```

```redis
# View tool manifests
KEYS tool_manifest:*

# View a manifest
GET tool_manifest:research

# Exit
exit
```

---

## Step 6: Create Your First Module (15-30 minutes)

Let's create a simple "hello" module that greets users.

### 1. Create Module Structure

```bash
mkdir -p agent/modules/hello
cd agent/modules/hello
touch __init__.py manifest.py tools.py main.py Dockerfile requirements.txt
```

### 2. Define the Manifest

Edit `manifest.py`:

```python
"""Hello module manifest."""

from shared.schemas.tools import ModuleManifest, ToolDefinition, ToolParameter

MANIFEST = ModuleManifest(
    module_name="hello",
    description="Friendly greeting module for testing.",
    tools=[
        ToolDefinition(
            name="hello.greet",
            description="Greet a user by name with a friendly message.",
            parameters=[
                ToolParameter(
                    name="name",
                    type="string",
                    description="Name of the person to greet",
                    required=True,
                ),
                ToolParameter(
                    name="language",
                    type="string",
                    description="Language for greeting (en, es, fr)",
                    required=False,
                    enum=["en", "es", "fr"],
                ),
            ],
            required_permission="guest",
        ),
    ],
)
```

### 3. Implement the Tool

Edit `tools.py`:

```python
"""Hello module tools."""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class HelloTools:
    """Tools for the hello module."""

    def __init__(self):
        self.greetings = {
            "en": "Hello, {name}! Welcome to the AI Agent System!",
            "es": "¡Hola, {name}! ¡Bienvenido al Sistema de Agente IA!",
            "fr": "Bonjour, {name}! Bienvenue dans le système d'agent IA!",
        }

    async def greet(self, name: str, language: str = "en") -> dict:
        """Greet a user by name.

        Args:
            name: Name of the person to greet
            language: Language code (en, es, fr)

        Returns:
            Dict with greeting message
        """
        logger.info("greeting_user", name=name, language=language)

        greeting_template = self.greetings.get(language, self.greetings["en"])
        message = greeting_template.format(name=name)

        return {
            "greeting": message,
            "language": language,
            "timestamp": "2026-02-16T12:00:00Z",
        }
```

### 4. Create the FastAPI App

Edit `main.py`:

```python
"""Hello module - FastAPI service."""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from modules.hello.manifest import MANIFEST
from modules.hello.tools import HelloTools
from shared.schemas.common import HealthResponse
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()
app = FastAPI(title="Hello Module", version="1.0.0")

tools: HelloTools | None = None


@app.on_event("startup")
async def startup():
    global tools
    tools = HelloTools()
    logger.info("hello_module_ready")


@app.get("/manifest", response_model=ModuleManifest)
async def manifest():
    """Return module manifest."""
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall):
    """Execute a tool call."""
    if tools is None:
        return ToolResult(
            tool_name=call.tool_name,
            success=False,
            error="Module not ready"
        )

    try:
        # Get tool name (remove module prefix)
        tool_name = call.tool_name.split(".")[-1]

        # Convert arguments to dict
        args = dict(call.arguments)

        # Route to correct tool
        if tool_name == "greet":
            result = await tools.greet(**args)
        else:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}"
            )

        return ToolResult(
            tool_name=call.tool_name,
            success=True,
            result=result
        )

    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e))
        return ToolResult(
            tool_name=call.tool_name,
            success=False,
            error=str(e)
        )


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
```

### 5. Create Dockerfile

Edit `Dockerfile`:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install shared package
COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/

# Install module dependencies
COPY modules/hello/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY modules/ /app/modules/

ENV PYTHONPATH="/app:/shared"

EXPOSE 8000

CMD ["uvicorn", "modules.hello.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 6. Create requirements.txt

Edit `requirements.txt`:

```
fastapi>=0.109
uvicorn[standard]>=0.27
structlog>=24.1
pydantic>=2.5
pydantic-settings>=2.1
```

### 7. Register the Module

Edit `agent/shared/shared/config.py`:

Find the `module_services` dict and add:

```python
module_services: dict[str, str] = {
    # ... existing modules ...
    "hello": "http://hello:8000",  # Add this line
}
```

Edit `agent/docker-compose.yml`:

Add service block (after other modules):

```yaml
  hello:
    build:
      context: .
      dockerfile: modules/hello/Dockerfile
    env_file: .env
    depends_on:
      - core
    networks:
      - agent-net
    restart: unless-stopped
```

### 8. Build and Start

```bash
# From agent/ directory
make build-module M=hello
make up
make refresh-tools
```

### 9. Test Your Module

Send a message to your bot:

```
Can you greet me? My name is Alice and I'd like a French greeting.
```

The bot should use your `hello.greet` tool!

**Or test via API:**

```bash
curl -X POST http://localhost:8000/message \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "test",
    "platform_user_id": "test-user",
    "platform_channel_id": "test-channel",
    "content": "Greet me in Spanish, my name is Carlos"
  }'
```

### 10. View Logs

```bash
make logs-module M=hello
```

You should see:
```json
{"event": "hello_module_ready", "timestamp": "..."}
{"event": "greeting_user", "name": "Carlos", "language": "es", ...}
```

---

## Common Development Tasks

### Modify Code

1. Edit files in `agent/modules/<module>/` or `agent/core/`
2. Rebuild: `make restart-module M=<module>` or `make restart-core`
3. View logs: `make logs-module M=<module>`

### Add a Database Table

See [Adding Database Table](../features/adding-database-table.md)

### Add an LLM Provider

See [Adding LLM Provider](../features/adding-llm-provider.md)

### Run Tests

```bash
# From agent/ directory
pytest

# Specific test file
pytest agent/modules/hello/test_tools.py

# With coverage
pytest --cov=agent --cov-report=html
```

### Debug Issues

See [Debugging Guide](debugging.md) and [Troubleshooting](../troubleshooting/)

---

## Development Workflow

### Daily Workflow

```bash
# Start services
make up

# Make code changes
# ...

# Rebuild changed service
make restart-core
# or
make restart-module M=research

# View logs
make logs-core

# Run tests
pytest

# Stop services (end of day)
make down
```

### Branch Workflow

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes, commit
git add .
git commit -m "Add feature X"

# Push
git push -u origin feature/my-feature

# Create PR on GitHub
```

---

## Understanding the Architecture

Now that you have the system running, here's how it works:

### Request Flow

```
User Message (Discord/Telegram/Slack)
  ↓
Bot normalizes to IncomingMessage
  ↓
POST /message to Core Orchestrator
  ↓
Core runs Agent Loop:
  - Resolve user
  - Check permissions
  - Build context (memories + history)
  - Call LLM with available tools
  - LLM decides to use tool → Execute
  - Append result, loop again
  - LLM returns final response
  ↓
Core returns AgentResponse
  ↓
Bot formats for platform
  ↓
User sees response
```

### Module Communication

```
Core discovers modules at startup:
  GET http://module:8000/manifest
  → Returns tool definitions

Core executes tools:
  POST http://module:8000/execute
  → Returns tool result

Modules never call each other directly
LLM orchestrates multi-tool workflows
```

---

## Next Steps

### Learn More

1. **Architecture** → [Architecture Overview](../architecture/overview.md)
2. **Core Services** → [Core Documentation](../core/)
3. **Module System** → [Module Overview](../modules/overview.md)
4. **Code Standards** → [Code Standards](code-standards.md)

### Build Something

Choose a tutorial:
- [Add an LLM Provider](../features/adding-llm-provider.md)
- [Add a Platform Bot](../features/adding-platform-bot.md)
- [Implement Multi-Module Workflows](../features/implementing-workflows.md)

### Join the Community

- Read existing modules for patterns
- Check [Troubleshooting](../troubleshooting/) if stuck
- File issues for bugs or questions

---

## Troubleshooting

### Services Won't Start

```bash
# Check Docker
docker compose ps

# Check logs for errors
make logs

# Restart everything
make down && make up
```

### Module Not Found

```bash
# Refresh tool registry
make refresh-tools

# Check module is registered in config
grep "my_module" agent/shared/shared/config.py

# Check module is in docker-compose.yml
grep "my-module:" agent/docker-compose.yml
```

### Database Connection Errors

```bash
# Check Postgres is running
docker compose ps postgres

# Check connection
make psql

# Restart Postgres
docker compose restart postgres
```

### Permission Denied

```bash
# Check user permission level
make psql
SELECT permission_level FROM users WHERE id = '<user-id>';

# Promote to admin
docker compose exec core python /app/cli.py user promote \
  --platform discord --platform-id <id> --level admin
```

---

**Congratulations!** You now have a working development environment and created your first module.

**Next:** [Code Standards](code-standards.md) | [Testing](testing.md) | [Architecture](../architecture/overview.md)

[Back to Documentation Index](../INDEX.md)
