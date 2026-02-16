# Core Service Overview

> **Quick Context**: Core orchestrator internals — the components that power the agent reasoning loop.
>
> **Related Files**: `agent/core/orchestrator/`, `agent/core/llm_router/`, `agent/core/memory/`
>
> **When to Read**: Understanding core internals, modifying agent behavior, debugging execution flow

## Purpose

The core service is the brain of the AI agent system. It orchestrates the entire request/response cycle from receiving a user message to returning an intelligent response with tool execution capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Core Orchestrator                        │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │           Agent Loop (agent_loop.py)                 │  │
│  │  • User/Conversation Resolution                      │  │
│  │  • Budget Checking                                   │  │
│  │  • Iteration Management (up to 10 loops)             │  │
│  │  • Message Persistence                               │  │
│  └───────┬──────────────────────────────────────────────┘  │
│          │                                                  │
│  ┌───────▼──────────┐  ┌─────────────┐  ┌──────────────┐  │
│  │  Context Builder │  │ Tool Registry│  │  LLM Router  │  │
│  │  (build context) │  │ (discovery)  │  │ (providers)  │  │
│  └──────┬───────────┘  └──────┬──────┘  └──────┬───────┘  │
│         │                     │                 │          │
│         │  ┌─────────────────▼─────────────────▼─────┐    │
│         └──►      Memory System (recall)              │    │
│            │  • Summarization                         │    │
│            │  • Semantic Search (pgvector)            │    │
│            └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Key Components

### 1. Agent Loop
**File**: `agent/core/orchestrator/agent_loop.py`

The main reasoning cycle that coordinates all other components.

**Responsibilities:**
- User and conversation resolution
- Token budget verification
- Persona selection
- Iteration management (up to 10 loops)
- Tool execution orchestration
- Message persistence

**Read more**: [Agent Loop Documentation](agent-loop.md)

### 2. Tool Registry
**File**: `agent/core/orchestrator/tool_registry.py`

Discovers modules and routes tool execution.

**Responsibilities:**
- HTTP-based module discovery (`GET /manifest`)
- Tool manifest caching (Redis, 1-hour TTL)
- Permission-based filtering
- Tool execution routing (`POST /execute`)
- Module health monitoring

**Read more**: [Tool Registry Documentation](tool-registry.md)

### 3. LLM Router
**File**: `agent/core/llm_router/router.py`

Provider abstraction layer with fallback support.

**Responsibilities:**
- Provider registration (Anthropic, OpenAI, Google)
- Fallback chain execution
- Request/response normalization
- Token counting and cost estimation
- Error handling and retries

**Read more**: [LLM Router Documentation](llm-router.md)

### 4. Context Builder
**File**: `agent/core/orchestrator/context_builder.py`

Assembles conversation context for LLM calls.

**Responsibilities:**
- System prompt construction
- Memory retrieval (semantic + summary)
- Conversation history windowing
- File attachment enrichment
- Active project injection
- Token budget management

**Read more**: [Context Builder Documentation](context-builder.md)

### 5. Memory System
**Files**: `agent/core/memory/summarizer.py`, `agent/core/memory/recall.py`

Persistent memory with semantic search.

**Responsibilities:**
- Conversation summarization
- Embedding generation (via `/embed` endpoint)
- Vector similarity search (pgvector)
- Memory creation and retrieval
- Recall scoring and ranking

**Read more**: [Memory System Documentation](memory-system.md)

## Request Lifecycle

### High-Level Flow

```
1. Incoming Message (from bot)
   ↓
2. Agent Loop.run()
   ↓
3. Resolve User → Check Budget → Resolve Persona → Resolve Conversation
   ↓
4. Get Available Tools (filter by permission + allowed_modules)
   ↓
5. Register File Attachments
   ↓
6. Context Builder.build()
   ├─ System Prompt (from persona)
   ├─ Semantic Memories (vector search)
   ├─ Conversation Summary
   ├─ Recent Messages
   └─ File Context
   ↓
7. LOOP (up to 10 iterations):
   ├─ LLM Router.chat() → LLMResponse
   ├─ If stop_reason != "tool_use": break with final content
   ├─ For each tool_call:
   │  ├─ Inject user_id and platform context
   │  ├─ Tool Registry.execute_tool() → ToolResult
   │  ├─ Save tool_call and tool_result messages
   │  └─ Append to context
   └─ Continue loop
   ↓
8. Save final assistant message
   ↓
9. Extract file URLs from tool results
   ↓
10. Return AgentResponse
```

### Detailed Step-by-Step

See [Agent Loop Documentation](agent-loop.md) for detailed explanation of each step.

## Component Dependencies

### Data Flow

```
Agent Loop
  ├─ Uses → Context Builder
  │           ├─ Uses → Memory System (recall)
  │           └─ Uses → Database (messages, summaries)
  ├─ Uses → Tool Registry
  │           ├─ Uses → Redis (manifest cache)
  │           └─ Calls → Modules (HTTP)
  └─ Uses → LLM Router
              ├─ Uses → Anthropic Provider
              ├─ Uses → OpenAI Provider
              └─ Uses → Google Provider

Memory System
  ├─ Uses → LLM Router (/embed endpoint)
  └─ Uses → Database (pgvector queries)
```

### Initialization Order

1. **Settings** loaded from environment
2. **LLM Router** initialized with provider registration
3. **Tool Registry** created (discovery happens on first request or manual refresh)
4. **Context Builder** initialized
5. **Agent Loop** created with all dependencies

## Key Files

### Core Orchestrator

| File | Purpose | Key Classes |
|------|---------|-------------|
| `orchestrator/agent_loop.py` | Main reasoning cycle | `AgentLoop` |
| `orchestrator/tool_registry.py` | Module discovery & routing | `ToolRegistry` |
| `orchestrator/context_builder.py` | Context assembly | `ContextBuilder` |

### LLM Router

| File | Purpose | Key Classes |
|------|---------|-------------|
| `llm_router/router.py` | Provider abstraction | `LLMRouter` |
| `llm_router/token_counter.py` | Token estimation & cost | `estimate_cost()` |
| `llm_router/providers/base.py` | Provider interface | `BaseLLMProvider` |
| `llm_router/providers/anthropic.py` | Claude integration | `AnthropicProvider` |
| `llm_router/providers/openai_provider.py` | GPT integration | `OpenAIProvider` |
| `llm_router/providers/google.py` | Gemini integration | `GoogleProvider` |

### Memory System

| File | Purpose | Key Functions |
|------|---------|---------------|
| `memory/summarizer.py` | Conversation summarization | `summarize_conversation()` |
| `memory/recall.py` | Semantic memory retrieval | `recall_memories()` |

### Main Entry Point

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app, endpoints, startup |

## HTTP Endpoints

The core service exposes these endpoints:

### `POST /message`

Main entry point for user messages.

**Request**: `IncomingMessage`
```python
{
  "platform": "discord",
  "platform_user_id": "123456",
  "platform_channel_id": "789",
  "platform_thread_id": "optional",
  "platform_server_id": "optional",
  "content": "user message text",
  "attachments": [
    {
      "filename": "file.txt",
      "url": "https://...",
      "minio_key": "...",
      "mime_type": "text/plain",
      "size_bytes": 1234
    }
  ]
}
```

**Response**: `AgentResponse`
```python
{
  "content": "assistant response text",
  "files": [
    {
      "filename": "output.png",
      "url": "https://...",
      "minio_key": "..."
    }
  ],
  "error": null,
  "metadata": {
    "tool_calls": [
      {"name": "research.web_search", "success": true, "tool_use_id": "..."}
    ]
  }
}
```

### `POST /embed`

Generate embeddings for semantic search.

**Request**:
```python
{"text": "content to embed"}
```

**Response**:
```python
{"embedding": [0.123, -0.456, ...]}  # 1536 dimensions
```

### `POST /continue`

Resume conversation from scheduler (background jobs).

**Request**:
```python
{
  "conversation_id": "uuid",
  "content": "background job completed message"
}
```

**Response**: `AgentResponse`

### `GET /health`

Health check endpoint.

**Response**:
```python
{"status": "ok"}
```

## Configuration

Key settings from `shared/config.py`:

```python
# Agent behavior
max_agent_iterations: int = 10          # Maximum reasoning loops
tool_result_max_chars: int = 8000       # Truncate large tool results

# LLM defaults
default_model: str | None = None        # Router picks first available
fallback_chain: str = ""                # Comma-separated fallback models

# Module discovery
module_services: dict[str, str]         # Module name → URL mapping
slow_modules: str = "..."               # Modules with 120s timeout

# Budget
default_guest_modules: str = "..."      # Modules available to guests
```

## Common Patterns

### Adding Context to Messages

See [Context Builder](context-builder.md) for:
- Injecting active projects
- Retrieving relevant memories
- Formatting conversation history

### Tool Execution

See [Tool Registry](tool-registry.md) for:
- Discovering new modules
- Permission filtering
- Retry logic

### Provider Fallback

See [LLM Router](llm-router.md) for:
- Configuring fallback chains
- Adding new providers
- Handling provider errors

## Troubleshooting

### Agent not using tools

1. Check tool availability: `make list-modules`
2. Verify user permission level
3. Check persona allowed_modules
4. Refresh tools: `make refresh-tools`

See [Tool Registry](tool-registry.md) for details.

### Context too large / token errors

1. Reduce `max_tokens_per_request` in persona
2. Adjust context builder history window
3. Check for large tool results

See [Context Builder](context-builder.md) for details.

### Slow responses

1. Check LLM provider latency
2. Review module response times: `make logs-module M=modulename`
3. Verify Redis caching is working

See [Performance Troubleshooting](../troubleshooting/performance.md) for details.

## Related Documentation

- [Agent Loop](agent-loop.md) — Detailed reasoning cycle
- [Tool Registry](tool-registry.md) — Module discovery and routing
- [LLM Router](llm-router.md) — Provider abstraction
- [Context Builder](context-builder.md) — Context assembly
- [Memory System](memory-system.md) — Summarization and recall
- [Architecture Overview](../architecture/overview.md) — System-wide design
- [Adding LLM Provider](../features/adding-llm-provider.md) — Provider integration guide

---

[Back to Core Documentation](README.md) | [Documentation Index](../INDEX.md)
