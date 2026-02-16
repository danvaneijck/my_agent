# Troubleshooting Documentation

Problem diagnosis and resolution documentation.

## Purpose

This directory contains guides for diagnosing and fixing common issues encountered when developing or operating the agent system.

## Documents

| Document | Purpose | Read When |
|----------|---------|-----------|
| [Common Issues](common-issues.md) | FAQ and frequent problems | Encountering common errors |
| [Module Issues](module-issues.md) | Module-specific problems | Module not working |
| [Platform Issues](platform-issues.md) | Bot connection problems | Bot not responding |
| [Database Issues](database-issues.md) | Migration and query problems | Database errors |
| [Performance](performance.md) | Performance debugging | System running slowly |

## Quick Diagnosis

### The bot isn't responding

1. Check bot is running: `make logs-bots`
2. Verify tokens are configured in `.env`
3. Check core service logs: `make logs-core`
4. See [Platform Issues](platform-issues.md)

### Module not found / Tool execution failed

1. Check module is running: `docker compose ps`
2. Verify module registered in `shared/config.py`
3. Refresh tool registry: `make refresh-tools`
4. Check module logs: `make logs-module M=modulename`
5. See [Module Issues](module-issues.md)

### Database migration failed

1. Check current revision: `make shell` → `alembic current`
2. View migration error in logs
3. Rollback if needed: `alembic downgrade -1`
4. See [Database Issues](database-issues.md)

### Slow agent responses

1. Check LLM provider latency
2. Review database query performance
3. Verify Redis caching is working
4. Check module response times
5. See [Performance](performance.md)

### Permission denied errors

1. Verify user permission level
2. Check tool required_permission
3. Review persona allowed_modules
4. See [Common Issues](common-issues.md)

## Diagnostic Tools

### Logs

```bash
# All services
make logs

# Specific service
make logs-core
make logs-module M=research
make logs-bots

# Follow logs in real-time
docker compose logs -f core
```

### Database

```bash
# PostgreSQL shell
make psql

# Check current migration
make shell
alembic current

# View migration history
alembic history
```

### Redis

```bash
# Redis CLI
make redis-cli

# Check cached manifests
KEYS tool_manifest:*
GET tool_manifest:research
```

### Module Health

```bash
# Check all modules
make list-modules

# Individual module health
curl http://localhost:8000/api/modules
```

## Common Error Patterns

### Module Discovery Failures

**Symptom**: Tool not available to LLM
**Diagnosis**: Check module_services in config, verify module is running
**Fix**: Add to config, rebuild, refresh tools

### Permission Errors

**Symptom**: "User does not have permission"
**Diagnosis**: Check user level vs tool required_permission
**Fix**: Promote user or adjust tool permission level

### Token Budget Exceeded

**Symptom**: "Monthly token budget exceeded"
**Diagnosis**: Check user token_budget_monthly
**Fix**: Reset budget or set to null (unlimited)

### Connection Failures

**Symptom**: "Connection refused" or timeout
**Diagnosis**: Service not running or network issue
**Fix**: Restart service, check Docker network

## Related Documentation

- [Debugging](../development/debugging.md) — Development debugging techniques
- [Common Issues](common-issues.md) — Detailed FAQ
- [Module Issues](module-issues.md) — Module-specific problems

---

[Back to Documentation Index](../INDEX.md)
