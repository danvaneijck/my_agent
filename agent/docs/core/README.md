# Core Service Documentation

Internal documentation for the core orchestrator service (`agent/core/`).

## Purpose

This directory documents the core service internals — the components that power the agent reasoning loop, manage tool execution, route to LLM providers, and build conversation context.

## Documents

| Document | Purpose | Read When |
|----------|---------|-----------|
| [Overview](overview.md) | Core service architecture | Understanding core components |
| [Agent Loop](agent-loop.md) | Reasoning cycle and iteration | Modifying agent behavior |
| [Tool Registry](tool-registry.md) | Module discovery and routing | Working with tool execution |
| [LLM Router](llm-router.md) | Provider abstraction and fallback | Adding LLM providers |
| [Context Builder](context-builder.md) | Prompt and context assembly | Modifying context logic |
| [Memory System](memory-system.md) | Summarization and recall | Working with memory |

## Key Components

- **Agent Loop** (`agent/core/orchestrator/agent_loop.py`) — Main reasoning cycle
- **Tool Registry** (`agent/core/orchestrator/tool_registry.py`) — Module discovery and routing
- **Context Builder** (`agent/core/orchestrator/context_builder.py`) — Prompt construction
- **LLM Router** (`agent/core/llm_router/router.py`) — Provider abstraction
- **Memory System** (`agent/core/memory/`) — Summarization and semantic recall

## Request Flow

```
User Message → Agent Loop
  ↓
Resolve User/Persona/Conversation
  ↓
Build Context (memories + history)
  ↓
Call LLM → Tool Use?
  ↓ yes
Execute Tools → Append Results
  ↓
Loop (up to 10 iterations)
  ↓ no
Return Response
```

## Related Documentation

- [Architecture](../architecture/) — System-wide design
- [Adding LLM Provider](../features/adding-llm-provider.md) — LLM integration guide
- [Core Endpoints](../api-reference/core-endpoints.md) — API reference

---

[Back to Documentation Index](../INDEX.md)
