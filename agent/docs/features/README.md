# Feature Implementation Guides

Step-by-step guides for implementing common features and development tasks.

## Purpose

This directory contains practical, task-oriented guides that walk you through implementing specific features. Each guide includes complete code examples, prerequisites, and testing strategies.

## Documents

| Document | Purpose | Read When |
|----------|---------|-----------|
| [Adding LLM Provider](adding-llm-provider.md) | Integrate new LLM APIs | Adding Claude, GPT, Gemini alternatives |
| [Adding Platform Bot](adding-platform-bot.md) | Integrate new chat platforms | Adding WhatsApp, Matrix, IRC, etc. |
| [Adding Database Table](adding-database-table.md) | Database schema changes | Adding new tables or modifying schema |
| [Adding Persona Features](adding-persona-features.md) | Extend persona system | Modifying persona behavior |
| [Implementing Workflows](implementing-workflows.md) | Multi-module workflows | Creating complex automation |
| [File Generation](file-generation.md) | Create and return files | Implementing file generation in modules |
| [Background Jobs](background-jobs.md) | Long-running tasks | Using the scheduler for async work |
| [Authentication](authentication.md) | External API auth | OAuth, tokens, credentials |
| [Testing Modules](testing-modules.md) | Module testing | Writing tests for modules |

## Guide Structure

Each guide follows this format:

1. **Overview** — What you'll accomplish
2. **Prerequisites** — What to read/know first
3. **Step-by-Step Instructions** — Detailed implementation
4. **Code Examples** — Copy-paste ready code
5. **Testing** — How to verify it works
6. **Related Documentation** — Further reading

## Common Patterns

### Adding Infrastructure

- **LLM Provider** → Implement `BaseLLMProvider`, register in router
- **Platform Bot** → Normalize messages, POST to core, format responses
- **Database Table** → Create model, generate migration, update references

### Working with Modules

- **File Generation** → Upload to MinIO, create FileRecord, return in ToolResult
- **Background Jobs** → Use scheduler with poll_module or poll_url
- **Authentication** → Store per-user credentials, implement refresh logic

## Related Documentation

- [Modules](../modules/) — Existing module examples
- [Core Services](../core/) — Core component internals
- [API Reference](../api-reference/) — Schemas and models

---

[Back to Documentation Index](../INDEX.md)
