# Development Documentation

Developer workflows, standards, and tooling documentation.

## Purpose

This directory contains documentation for developers working on the agent system — how to set up your environment, write tests, debug issues, and follow code standards.

## Documents

| Document | Purpose | Read When |
|----------|---------|-----------|
| [Getting Started](getting-started.md) | Onboarding for new developers | First time setup |
| [Testing](testing.md) | Testing strategies and tools | Writing or running tests |
| [Debugging](debugging.md) | Problem diagnosis techniques | Debugging issues |
| [Makefile Reference](makefile-reference.md) | All make commands explained | Using make targets |
| [Code Standards](code-standards.md) | Python conventions and practices | Writing new code |

## Quick Start

1. **Setup** → [Getting Started](getting-started.md)
2. **Standards** → [Code Standards](code-standards.md)
3. **Testing** → [Testing](testing.md)
4. **Debugging** → [Debugging](debugging.md)

## Development Workflow

### Local Development

```bash
# Start infrastructure
make up

# Make code changes
# ...

# Rebuild and restart service
make restart-core  # or restart-module M=research

# View logs
make logs-core

# Run tests
make test
```

### Common Commands

| Task | Command |
|------|---------|
| Start all services | `make up` |
| Stop all services | `make down` |
| View logs | `make logs` |
| Rebuild service | `make restart-core` |
| Run migrations | `make migrate` |
| Open shell in core | `make shell` |
| PostgreSQL shell | `make psql` |

See [Makefile Reference](makefile-reference.md) for complete list.

## Code Standards

- **Type hints** — Use Python type annotations
- **Async/await** — Async functions for I/O operations
- **Structlog** — JSON structured logging
- **Error handling** — Specific exceptions, descriptive messages
- **Documentation** — Docstrings for public APIs

See [Code Standards](code-standards.md) for details.

## Testing

- **Unit tests** — Test individual functions
- **Integration tests** — Test component interactions
- **Fixtures** — Reusable test data and mocks
- **Coverage** — Track test coverage

See [Testing](testing.md) for strategies and examples.

## Related Documentation

- [Getting Started](getting-started.md) — Setup and onboarding
- [Troubleshooting](../troubleshooting/) — Debugging common issues
- [Features](../features/) — Implementation guides

---

[Back to Documentation Index](../INDEX.md)
