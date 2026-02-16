# Documentation

Welcome to the AI Agent System documentation. This directory contains comprehensive documentation for developers working with and extending the agent system.

## Quick Start

- **New to the project?** Start with [Getting Started](development/getting-started.md)
- **Looking for something specific?** Check the [Documentation Index](INDEX.md)
- **Working on a feature?** Use the index's "When to Read" column to find relevant docs

## Documentation Structure

```
docs/
├── INDEX.md                    # Complete documentation index (start here!)
├── architecture/               # System design and infrastructure
├── core/                       # Core orchestrator service internals
├── comms/                      # Platform bots (Discord, Telegram, Slack)
├── modules/                    # Individual tool modules
├── features/                   # Step-by-step implementation guides
├── api-reference/              # Schemas, models, and API specs
├── development/                # Developer workflows and standards
├── deployment/                 # Production deployment guides
└── troubleshooting/            # Problem diagnosis and solutions
```

## Navigation

### For AI Agents

The documentation is optimized for quick context access:

1. **Start with** [INDEX.md](INDEX.md) — Use the "When to Read" column
2. **Find your task** — Each doc has clear scope and prerequisites
3. **Get context** — Code references include file paths and line numbers
4. **Find examples** — Working code examples with full context

### For Human Developers

Browse by category or follow these learning paths:

**Onboarding Path:**
1. [Getting Started](development/getting-started.md)
2. [Architecture Overview](architecture/overview.md)
3. [Adding Modules](modules/ADDING_MODULES.md)
4. [Code Standards](development/code-standards.md)

**Module Development Path:**
1. [Module System](architecture/module-system.md)
2. [Adding Modules](modules/ADDING_MODULES.md)
3. [Module Contract](api-reference/module-contract.md)
4. [Testing Modules](features/testing-modules.md)

**Core Development Path:**
1. [Core Overview](core/overview.md)
2. [Agent Loop](core/agent-loop.md)
3. [Tool Registry](core/tool-registry.md)
4. [LLM Router](core/llm-router.md)

## Documentation Principles

All documentation follows these standards:

- **Hierarchical**: Overview → Component → Feature
- **Progressive**: Quick reference first, details below
- **Agent-Friendly**: Clear headers, tables, code with context
- **Cross-Referenced**: Explicit links to related docs
- **Location Aware**: States which files are described
- **Searchable**: Consistent naming and keywords

## Quick Reference

### Common Tasks

| Task | Documentation |
|------|---------------|
| Add a new module | [Adding Modules](modules/ADDING_MODULES.md) |
| Add an LLM provider | [Adding LLM Provider](features/adding-llm-provider.md) |
| Add a chat platform | [Adding Platform Bot](features/adding-platform-bot.md) |
| Add a database table | [Adding Database Table](features/adding-database-table.md) |
| Debug an issue | [Troubleshooting](troubleshooting/common-issues.md) |
| Deploy to production | [Production Setup](deployment/production-setup.md) |

### Quick Lookups

| What | Where |
|------|-------|
| Database schema | [Database Schema](architecture/database-schema.md) |
| API schemas | [Shared Schemas](api-reference/shared-schemas.md) |
| Make commands | [Makefile Reference](development/makefile-reference.md) |
| Known issues | [Common Issues](troubleshooting/common-issues.md) |

## Contributing

When making changes that affect documentation:

1. **Update docs in the same commit** as code changes
2. **Check cross-references** remain valid
3. **Add examples** for new patterns
4. **Update INDEX.md** if adding new docs

## Need Help?

- Can't find what you're looking for? Check [INDEX.md](INDEX.md)
- Found an issue? File a bug report
- Have suggestions? Open a discussion

---

**Main Entry Points:**
- [Documentation Index](INDEX.md) — Complete documentation catalog
- [Architecture Overview](architecture/overview.md) — System design
- [Getting Started](development/getting-started.md) — Developer onboarding
