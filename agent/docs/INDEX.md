# Documentation Index

> **Quick Navigation Hub** — Find the documentation you need quickly based on your task.

## How to Use This Index

- **AI Agents**: Use the "When to Read" column to find documentation relevant to your current task
- **Humans**: Browse by category or use the table of contents below
- **New Contributors**: Start with [Getting Started](development/getting-started.md) and [Architecture Overview](architecture/overview.md)

---

## Table of Contents

- [Architecture](#architecture) — System design and infrastructure
- [Core Services](#core-services) — Orchestrator internals
- [Communication Layer](#communication-layer) — Platform bots and messaging
- [Modules](#modules) — Tool modules and their implementations
- [Features](#features) — Step-by-step implementation guides
- [API Reference](#api-reference) — Schemas, models, and endpoints
- [Development](#development) — Developer workflows and standards
- [Deployment](#deployment) — Production deployment guides
- [Troubleshooting](#troubleshooting) — Diagnosing and fixing issues

---

## Architecture

High-level system design, data flows, and infrastructure documentation.

| Document | Description | When to Read |
|----------|-------------|--------------|
| [Overview](architecture/overview.md) | Complete system architecture, component interactions, technology stack | Understanding overall system design, onboarding |
| [Data Flow](architecture/data-flow.md) | Request/response lifecycle, tool execution flow, memory flows | Debugging message handling, understanding execution paths |
| [Database Schema](architecture/database-schema.md) | Complete database schema with relationships and indexes | Adding tables, understanding data model, writing queries |
| [Module System](architecture/module-system.md) | Module architecture, discovery, routing, and isolation | Creating modules, understanding module communication |
| [Deployment](architecture/deployment.md) | Docker Compose setup, networking, volumes, dependencies | Infrastructure changes, deployment configuration |

---

## Core Services

Documentation for the core orchestrator service that powers the agent loop.

| Document | Description | When to Read |
|----------|-------------|--------------|
| [Overview](core/overview.md) | Core service architecture and component relationships | Understanding core internals, onboarding |
| [Agent Loop](core/agent-loop.md) | Reasoning cycle, tool execution, iteration logic | Modifying agent behavior, understanding execution flow |
| [Tool Registry](core/tool-registry.md) | Module discovery, caching, routing, permissions | Adding modules, troubleshooting tool execution |
| [LLM Router](core/llm-router.md) | Provider abstraction, fallback chain, token counting | Adding LLM providers, debugging model calls |
| [Context Builder](core/context-builder.md) | Prompt construction, memory retrieval, history management | Modifying context assembly, debugging prompts |
| [Memory System](core/memory-system.md) | Summarization, semantic recall, embeddings | Working with memory features, understanding recall |

---

## Communication Layer

Platform bot implementations and cross-platform patterns.

| Document | Description | When to Read |
|----------|-------------|--------------|
| [Overview](comms/overview.md) | Common bot architecture, message normalization | Adding new platforms, understanding bot patterns |
| [Discord Bot](comms/discord-bot.md) | Discord.py implementation details | Modifying Discord bot, debugging Discord issues |
| [Telegram Bot](comms/telegram-bot.md) | python-telegram-bot implementation | Modifying Telegram bot, debugging Telegram issues |
| [Slack Bot](comms/slack-bot.md) | slack-bolt implementation | Modifying Slack bot, debugging Slack issues |
| [File Pipeline](comms/file-pipeline.md) | End-to-end file handling across platforms | Working with file uploads/downloads, debugging file issues |

---

## Modules

Individual module documentation with implementation details and usage patterns.

### Module System

| Document | Description | When to Read |
|----------|-------------|--------------|
| [Overview](modules/overview.md) | Module system architecture, discovery, execution | Understanding module system, creating modules |
| [Adding Modules](modules/ADDING_MODULES.md) | Step-by-step guide to creating new modules | Creating a new module |

### Individual Modules

| Module | Description | When to Read |
|--------|-------------|--------------|
| [research](modules/research.md) | Web search, scraping, summarization | Working with research features |
| [file_manager](modules/file_manager.md) | File CRUD on MinIO with DB tracking | Working with file storage |
| [code_executor](modules/code_executor.md) | Sandboxed Python/shell execution | Working with code execution |
| [knowledge](modules/knowledge.md) | Persistent memory with semantic search | Working with memory/knowledge features |
| [atlassian](modules/atlassian.md) | Jira and Confluence integration | Working with Atlassian tools |
| [claude_code](modules/claude_code.md) | Coding tasks via Claude Code CLI | Working with automated coding |
| [deployer](modules/deployer.md) | Deploy projects to live URLs | Working with deployment features |
| [scheduler](modules/scheduler.md) | Background jobs and workflows | Working with scheduled tasks |
| [garmin](modules/garmin.md) | Garmin Connect health data | Working with Garmin integration |
| [renpho_biometrics](modules/renpho_biometrics.md) | Renpho smart scale data | Working with Renpho integration |
| [location](modules/location.md) | OwnTracks geofencing and tracking | Working with location features |
| [git_platform](modules/git_platform.md) | GitHub/Bitbucket integration | Working with Git platform features |
| [project_planner](modules/project_planner.md) | Project planning and execution | Working with project management |
| [injective](modules/injective.md) | Blockchain trading | Working with trading features |
| [portal](modules/portal.md) | Web portal interface | Working with web UI |

---

## Features

Step-by-step guides for implementing common features and patterns.

| Document | Description | When to Read |
|----------|-------------|--------------|
| [Adding LLM Provider](features/adding-llm-provider.md) | Complete guide to integrating new LLM providers | Adding support for a new LLM API |
| [Adding Platform Bot](features/adding-platform-bot.md) | Guide to integrating new chat platforms | Adding support for a new chat platform |
| [Adding Database Table](features/adding-database-table.md) | Database schema changes and migrations | Adding new database tables |
| [Adding Persona Features](features/adding-persona-features.md) | Extending the persona system | Modifying persona behavior |
| [Implementing Workflows](features/implementing-workflows.md) | Multi-module workflow patterns | Creating complex workflows |
| [File Generation](features/file-generation.md) | Creating and returning files from tools | Implementing file generation in modules |
| [Background Jobs](features/background-jobs.md) | Scheduler integration patterns | Implementing long-running tasks |
| [Authentication](features/authentication.md) | External API auth patterns | Integrating APIs with OAuth/tokens |
| [Testing Modules](features/testing-modules.md) | Module testing strategies | Writing tests for modules |

---

## API Reference

Complete reference documentation for schemas, models, and endpoints.

| Document | Description | When to Read |
|----------|-------------|--------------|
| [Shared Schemas](api-reference/shared-schemas.md) | Pydantic schemas (ToolCall, ToolResult, etc.) | Working with shared data structures |
| [Database Models](api-reference/database-models.md) | ORM models with relationships | Querying database, understanding data model |
| [Core Endpoints](api-reference/core-endpoints.md) | Core service HTTP/WebSocket APIs | Calling core endpoints, understanding APIs |
| [Module Contract](api-reference/module-contract.md) | Module endpoint specifications | Implementing module endpoints |
| [Shared Utilities](api-reference/shared-utilities.md) | Config, database, Redis helpers | Using shared package utilities |

---

## Development

Developer workflows, standards, and tooling.

| Document | Description | When to Read |
|----------|-------------|--------------|
| [Getting Started](development/getting-started.md) | Onboarding guide for new developers | First time setting up the project |
| [Testing](development/testing.md) | Testing strategies and tools | Writing or running tests |
| [Debugging](development/debugging.md) | Problem diagnosis techniques | Debugging issues |
| [Makefile Reference](development/makefile-reference.md) | All make commands explained | Using make commands |
| [Code Standards](development/code-standards.md) | Python conventions and best practices | Writing new code |

---

## Deployment

Production deployment, infrastructure, and operations.

| Document | Description | When to Read |
|----------|-------------|--------------|
| [Production Setup](deployment/production-setup.md) | Production deployment guide | Deploying to production |
| [Secrets Management](deployment/secrets-management.md) | API keys and credentials | Managing secrets |
| [Monitoring](deployment/monitoring.md) | Observability and alerting | Setting up monitoring |
| [Backup & Restore](deployment/backup-restore.md) | Data protection procedures | Backing up or restoring data |
| [Scaling](deployment/scaling.md) | Horizontal scaling strategies | Scaling the system |

---

## Troubleshooting

Diagnosing and fixing common issues.

| Document | Description | When to Read |
|----------|-------------|--------------|
| [Common Issues](troubleshooting/common-issues.md) | FAQ and frequent problems | Encountering common errors |
| [Module Issues](troubleshooting/module-issues.md) | Module-specific problems | Module not working correctly |
| [Platform Issues](troubleshooting/platform-issues.md) | Bot connection problems | Bot not responding |
| [Database Issues](troubleshooting/database-issues.md) | Migration and query problems | Database errors |
| [Performance](troubleshooting/performance.md) | Performance debugging | System running slowly |

---

## Quick Reference by Task

### I want to...

- **Add a new module** → [Adding Modules](modules/ADDING_MODULES.md)
- **Add a new LLM provider** → [Adding LLM Provider](features/adding-llm-provider.md)
- **Add a new chat platform** → [Adding Platform Bot](features/adding-platform-bot.md)
- **Add a database table** → [Adding Database Table](features/adding-database-table.md)
- **Understand the agent loop** → [Agent Loop](core/agent-loop.md)
- **Understand module discovery** → [Tool Registry](core/tool-registry.md)
- **Work with files** → [File Pipeline](comms/file-pipeline.md)
- **Create workflows** → [Implementing Workflows](features/implementing-workflows.md)
- **Debug slow responses** → [Performance](troubleshooting/performance.md)
- **Deploy to production** → [Production Setup](deployment/production-setup.md)
- **Get started developing** → [Getting Started](development/getting-started.md)
- **Understand the architecture** → [Architecture Overview](architecture/overview.md)

---

## Documentation Standards

All documentation in this system follows these principles:

1. **Hierarchical Organization**: Overview → Component → Feature
2. **Progressive Disclosure**: Quick reference first, details below
3. **Agent-Friendly**: Clear headers, tables, code examples with full context
4. **Cross-Referenced**: Explicit links to related documentation
5. **Location Aware**: Each doc states which files it describes
6. **Searchable**: Consistent naming, keywords in headers

### Document Template

Each documentation file should include:

- **Quick Context**: Related files, docs, and key concepts
- **Overview**: What this document covers
- **Details**: Progressive disclosure of information
- **Code Examples**: Copy-paste ready with full context
- **Related Documentation**: Links to related docs

---

## Contributing to Documentation

When updating code that affects behavior:

1. Update the relevant documentation in the same commit
2. Check that all cross-references remain valid
3. Add code examples if introducing new patterns
4. Update the INDEX.md if adding new documentation

For questions or suggestions about documentation, please file an issue.
