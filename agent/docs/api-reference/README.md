# API Reference Documentation

Complete reference documentation for schemas, models, endpoints, and shared utilities.

## Purpose

This directory provides detailed API reference documentation for all shared data structures, database models, HTTP endpoints, and utility functions used throughout the system.

## Documents

| Document | Purpose | Read When |
|----------|---------|-----------|
| [Shared Schemas](shared-schemas.md) | Pydantic schemas (ToolCall, ToolResult, etc.) | Working with shared data structures |
| [Database Models](database-models.md) | ORM models with relationships | Querying database, understanding schema |
| [Core Endpoints](core-endpoints.md) | Core service HTTP/WebSocket APIs | Calling core endpoints |
| [Module Contract](module-contract.md) | Module endpoint specifications | Implementing module endpoints |
| [Shared Utilities](shared-utilities.md) | Config, database, Redis helpers | Using shared package utilities |

## What's Documented

### Shared Schemas (`agent/shared/shared/schemas/`)

- **ToolCall** / **ToolResult** — Tool execution request/response
- **ModuleManifest** / **ToolDefinition** — Module discovery
- **IncomingMessage** / **AgentResponse** — Platform messaging
- **HealthResponse** — Service health checks
- Validation rules and field descriptions

### Database Models (`agent/shared/shared/models/`)

- All ORM models with field types
- Relationships (FK, back_populates)
- Unique constraints and indexes
- Common query patterns

### Core Endpoints

- `POST /message` — Send user message, get agent response
- `POST /embed` — Generate embeddings
- `POST /continue` — Resume conversation from scheduler
- `GET /health` — Health check

### Module Contract

- `GET /manifest` — Return module manifest
- `POST /execute` — Execute tool
- `GET /health` — Module health

### Shared Utilities

- `get_settings()` — Access configuration
- `get_session_factory()` — Database sessions
- `get_redis()` — Redis client
- `parse_list()` — Parse comma-separated lists
- `upload_attachment()` — Upload files to MinIO

## Usage Examples

All reference docs include:

- **Type signatures** — Full Python types
- **Field descriptions** — What each field means
- **Validation rules** — Constraints and defaults
- **Usage examples** — Copy-paste ready code
- **Common patterns** — Typical use cases

## Related Documentation

- [Architecture](../architecture/) — System design context
- [Features](../features/) — Implementation guides
- [Development](../development/) — Coding standards

---

[Back to Documentation Index](../INDEX.md)
