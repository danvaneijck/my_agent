# Writing Good Skills

> **Quick Context**: A practical guide to creating effective, reusable skills in the skills_modules system.

## Related Files

- `agent/modules/skills_modules/tools.py` — SkillsTools implementation
- `agent/modules/skills_modules/manifest.py` — Tool definitions
- `agent/shared/shared/models/user_skill.py` — UserSkill ORM model
- `agent/shared/shared/models/project_skill.py` — ProjectSkill junction model
- `agent/shared/shared/models/task_skill.py` — TaskSkill junction model

## Related Documentation

- [Skills Module Reference](../modules/skills_modules.md) — Complete API reference
- [Project Planner Module](../modules/project_planner.md) — Attaching skills to projects/tasks
- [Database Schema](../architecture/database-schema.md) — skill table definitions

## When to Use This Guide

Read this when you want to:
- Create a skill that will actually get used and stay useful over time
- Understand what separates a good skill from a throwaway snippet
- Build template skills that are safe to render with variables
- Organize a growing skill library so it stays discoverable

---

## Overview

Skills are your personal library of reusable content: code snippets, configuration templates, step-by-step procedures, reference material. The system stores them in the database, lets you attach them to projects and tasks for context, and can render them with Jinja2 variable substitution when you mark them as templates.

A skill that no one (including you) uses later is just clutter. This guide focuses on writing skills that stay valuable over time.

---

## The Five Fields That Matter Most

Every skill has these key fields. Getting them right is the difference between a skill you rediscover and one you ignore.

| Field | Why It Matters |
|-------|----------------|
| `name` | How you find the skill later — make it memorable and specific |
| `description` | What the agent reads to decide whether to suggest this skill |
| `category` | Enables filtering — pick from the standard set |
| `tags` | Fine-grained discoverability — be generous |
| `content` | The actual value — write it as if someone else will use it |

### name

Names are unique per user. They function as identifiers, not sentences. Follow these rules:

- Use underscores, not spaces: `postgres_migration_helper` not `postgres migration helper`
- Be specific, not generic: `fastapi_auth_middleware` not `auth_code`
- Include the tech where it matters: `python_retry_decorator` vs `retry_decorator`
- Avoid version numbers unless the version is the point: `openai_v1_client` is fine when you need to distinguish from a v2 variant

```
# Good names
postgres_upsert_pattern
docker_healthcheck_template
pytest_fixture_factory
deployment_checklist
jinja2_email_template

# Bad names
code1
my_snippet
useful_thing
temp
```

### description

The description is what the agent uses to decide whether a skill is relevant. It is also what you skim when browsing a list of 30 skills. Write one or two sentences that explain:

1. What the skill does
2. When you would use it (context)

```
# Good description
"Async SQLAlchemy session factory pattern for FastAPI dependency injection.
Use this when setting up database access in a new FastAPI service."

# Bad description
"some database code"
"useful"
```

For template skills, the description should also list required variables:

```
"Jinja2 template for a pytest test function.
Required variables: function_name, description, arrange_code, function_call, expected_result."
```

### category

The category field accepts any string but the system works best when everyone uses the same set. Stick to these five:

| Category | Use For |
|----------|---------|
| `code` | Code snippets, functions, classes, patterns |
| `config` | Configuration files, environment templates, YAML/TOML/JSON |
| `procedure` | Step-by-step checklists, runbooks, SOPs |
| `template` | Jinja2 templates — content with `{{ variable }}` placeholders |
| `reference` | Documentation, examples, notes, links |

Note: `template` as a category is a convention for skills where the primary purpose is templating. It pairs naturally with `is_template=true`, but you can have a `code` skill that is also a template — the category describes what it *is*, the `is_template` flag describes how it *renders*.

### tags

Tags are how you cross-cut categories. A skill can only have one category, but it can have many tags. Tag liberally — there is no cost to having many tags, and discoverability only improves.

Good tagging strategies:

- **Technology**: `python`, `postgres`, `redis`, `docker`, `fastapi`, `sqlalchemy`
- **Purpose**: `testing`, `error-handling`, `logging`, `auth`, `caching`
- **Pattern**: `singleton`, `factory`, `middleware`, `decorator`, `template-method`
- **Project context**: `backend-api`, `ml-pipeline` (if skill is project-specific)

```python
# Example: a Python retry decorator
tags: ["python", "error-handling", "decorator", "resilience", "retry"]

# Example: a GitHub Actions workflow template
tags: ["ci-cd", "github-actions", "yaml", "testing", "template"]
```

---

## Writing the Content

### Code Skills

The most common skill type. Write code as if it will be copied directly into a project — because it will be.

**Include:**
- Imports at the top (don't make someone guess what `asyncpg` is)
- A docstring or comment explaining what the code does
- Type hints where they add clarity
- Example usage in a comment at the bottom if the interface is not obvious

**Avoid:**
- Placeholder TODOs without explanation: `# TODO: implement` is useless
- Hardcoded values that should be configurable
- Business logic specific to one project that won't transfer

```python
# Skill: async_retry_decorator
# Category: code
# Language: python
# Tags: python, decorator, error-handling, resilience

import asyncio
import functools
from typing import Callable, Type

def async_retry(
    retries: int = 3,
    delay: float = 1.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
):
    """Retry an async function on failure with exponential backoff.

    Args:
        retries: Maximum number of retry attempts.
        delay: Initial delay in seconds between retries (doubles each attempt).
        exceptions: Exception types to catch and retry on.

    Usage:
        @async_retry(retries=3, delay=0.5, exceptions=(httpx.HTTPError,))
        async def fetch_data(url: str) -> dict:
            ...
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_error = e
                    if attempt < retries:
                        wait = delay * (2 ** attempt)
                        await asyncio.sleep(wait)
            raise last_error
        return wrapper
    return decorator
```

### Config Skills

Configuration files that can be dropped into projects. The most important thing: make them complete. A partial config that requires knowing what the rest looks like is not reusable.

```yaml
# Skill: postgres_docker_service
# Category: config
# Tags: postgres, docker, docker-compose, database

# Add this block to your docker-compose.yml services section.
# Requires: POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD in your .env

  postgres:
    image: postgres:16
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER} -d ${POSTGRES_DB}"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped

# Also add to volumes section:
# volumes:
#   postgres_data:
```

### Procedure Skills

Checklists and runbooks. Write these as numbered steps, not prose. Every step should be atomic — one action, one check.

```markdown
# Skill: pre_release_checklist
# Category: procedure
# Tags: release, git, testing, deployment

## Pre-Release Checklist

### Code Quality
1. Run full test suite: `pytest -x --tb=short`
2. Check coverage (target ≥ 80%): `pytest --cov=src --cov-report=term-missing`
3. Run linter: `ruff check .`
4. Run type checker: `mypy src/`

### Version & Changelog
5. Bump version in `pyproject.toml` following semver
6. Add release notes to `CHANGELOG.md` with date and version header
7. Commit: `git commit -m "chore: bump version to X.Y.Z"`

### Git
8. Tag the release: `git tag -a vX.Y.Z -m "Release X.Y.Z"`
9. Push tag: `git push origin vX.Y.Z`

### Deploy
10. Trigger CI/CD pipeline and confirm all checks pass
11. Monitor logs for 5 minutes post-deploy
12. Smoke test critical paths manually
```

### Reference Skills

Documentation, links, notes — things you look up but don't execute. Keep these concise and organized with headers so you can scan them quickly.

```markdown
# Skill: sqlalchemy_async_cheatsheet
# Category: reference
# Tags: sqlalchemy, python, database, async, orm

## SQLAlchemy Async Quick Reference

### Session Setup
```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
engine = create_async_engine("postgresql+asyncpg://...")
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

### Common Queries
```python
# Select one
result = await session.execute(select(User).where(User.id == uid))
user = result.scalar_one_or_none()

# Select many
result = await session.execute(select(User).order_by(User.created_at.desc()))
users = result.scalars().all()

# Insert
session.add(User(name="Alice"))
await session.commit()

# Update
await session.execute(update(User).where(User.id == uid).values(name="Bob"))
await session.commit()

# Delete
await session.execute(delete(User).where(User.id == uid))
await session.commit()
```

### Gotchas
- Use `expire_on_commit=False` to access attributes after commit
- Use `session.commit()` (not `flush()`) for cross-container visibility
- Always use `DateTime(timezone=True)` in models — asyncpg rejects naive datetimes
```

---

## Template Skills

Template skills use Jinja2 to substitute `{{ variable }}` placeholders at render time. Use them when you have a pattern that stays mostly the same but needs a few values filled in.

### When to Use Templates

Use `is_template=true` when:
- The skill has 2 or more places where a value changes per use
- You would otherwise copy-paste and do a find-replace
- The structure is fixed but the specifics vary

Don't use templates when:
- The entire content changes based on context (just create multiple skills)
- There is only one variable and it appears once (just edit it manually)

### Writing Template Content

Mark the skill `is_template=true` and use `{{ variable_name }}` syntax:

```python
# Skill: fastapi_crud_router
# Category: template
# Is Template: true
# Tags: python, fastapi, crud, router, template
# Description: FastAPI router with full CRUD for a resource.
# Required variables: resource_name, resource_name_plural, schema_name, model_name

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/{{ resource_name_plural }}", tags=["{{ resource_name_plural }}"])


@router.get("/", response_model=list[{{ schema_name }}])
async def list_{{ resource_name_plural }}(
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select({{ model_name }}))
    return result.scalars().all()


@router.get("/{item_id}", response_model={{ schema_name }})
async def get_{{ resource_name }}(item_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    item = await session.get({{ model_name }}, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="{{ resource_name }} not found")
    return item


@router.post("/", response_model={{ schema_name }}, status_code=201)
async def create_{{ resource_name }}(
    data: {{ schema_name }}Create,
    session: AsyncSession = Depends(get_session),
):
    item = {{ model_name }}(**data.model_dump())
    session.add(item)
    await session.commit()
    return item


@router.delete("/{item_id}", status_code=204)
async def delete_{{ resource_name }}(item_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    item = await session.get({{ model_name }}, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="{{ resource_name }} not found")
    await session.delete(item)
    await session.commit()
```

Rendering with:
```json
{
  "resource_name": "widget",
  "resource_name_plural": "widgets",
  "schema_name": "WidgetSchema",
  "model_name": "Widget"
}
```

Produces a fully-formed FastAPI CRUD router with no manual editing required.

### Template Rules

**Use descriptive variable names.** `{{ api_key }}` is always clearer than `{{ k }}`.

**Document variables in the description.** The description is read before the content. If someone needs to know what variables to provide, they should not have to read the whole template to find out.

**List defaults where they apply.** If a variable has a sensible default, mention it in the description: `"timeout_seconds: default 30"`.

**Use Jinja2 control structures sparingly.** Conditionals and loops work, but make templates harder to reason about. Prefer multiple focused skills over one complex template with many branches.

**Test the template before relying on it.** Use `render_skill` with a real set of variables and verify the output compiles or parses correctly before attaching the skill to a project.

### Using Conditionals

Conditionals are useful for optional blocks:

```python
# Skill: python_class_template
# is_template: true

class {{ class_name }}:
    """{{ description }}"""

    def __init__(self, {{ init_params }}):
        {{ init_body }}

    {% if include_repr %}
    def __repr__(self) -> str:
        return f"{{ class_name }}({{ repr_fields }})"
    {% endif %}

    {% if include_str %}
    def __str__(self) -> str:
        return {{ str_implementation }}
    {% endif %}
```

### Security Note

Template rendering uses Jinja2's `SandboxedEnvironment`. This prevents templates from executing arbitrary Python expressions like `{{ os.system("rm -rf /") }}`. Stick to variable substitution and simple Jinja2 control structures — anything that looks like a Python expression will either be sandboxed or fail.

---

## Attaching Skills to Projects and Tasks

Attaching a skill to a project or task creates a link — it does not embed the skill content. The skill remains in your library and can be attached to multiple places simultaneously.

### When to Attach to a Project

Attach when the skill is part of the project's established patterns:

- The project uses a specific API client pattern — attach the API client skill
- The project has a deployment checklist — attach it to the project
- The project follows a particular error-handling convention — attach the reference

This lets anyone (or any agent) working on the project see what patterns apply without searching the whole library.

### When to Attach to a Task

Attach when the skill is directly relevant to completing a specific task:

- A task involves writing tests — attach the test template skill
- A task requires setting up a new service — attach the Docker config skill
- A task involves a complex migration — attach the migration checklist

Task-level attachment provides targeted context. The agent can call `get_task_skills` to understand what patterns to follow when working on that specific task.

### Attachment Workflow

```
# 1. Create the skill
create_skill(
  name="postgres_migration_pattern",
  content="...",
  category="code",
  language="python",
  tags=["postgres", "alembic", "migration"]
)

# 2. Attach to the project that uses this pattern
attach_skill_to_project(project_id="...", skill_id="...")

# 3. Attach to the specific task where it's most immediately needed
attach_skill_to_task(task_id="...", skill_id="...")
```

One skill, attached in two places, serving both broad project context and narrow task context.

---

## Organizing a Growing Library

Skills accumulate. After 20 or 30 skills, discoverability matters. These practices keep the library navigable:

**Consistent category usage.** If you file some config templates under `template` and others under `config`, filtering breaks down. Decide a convention and stick to it. Recommendation: use `category=template` only for Jinja2 template skills (i.e., `is_template=true`); use the actual content category otherwise.

**Tag at creation time.** It is easy to forget to tag a skill you create in a hurry. Adding tags later requires remembering what the skill does. Tag when you create.

**Review periodically.** Skills go stale. Code that worked with library version X may not work with version Y. Procedure skills may become outdated as workflows evolve. A skill that is wrong is worse than no skill — it wastes time.

**Name skills by what they are, not when you created them.** `2024_api_client` becomes meaningless. `httpx_async_client_with_retry` stays useful.

**Detach before deleting.** If you are removing a skill that is attached to active projects or tasks, detach it first so the context is removed cleanly. Deleting a skill cascades and removes all attachments automatically, but reviewing them first lets you decide if replacement skills should be attached instead.

---

## Common Mistakes

### Skill too broad

A skill called `utilities` containing 500 lines of mixed helper functions is not reusable — it is an undifferentiated dump. Split it into focused skills: `string_helpers`, `date_helpers`, `http_helpers`.

**Rule of thumb**: if you can't describe what the skill does in one sentence, split it.

### Skill too narrow

A skill called `fix_for_issue_847` containing a one-line patch is the opposite problem. It is so specific it will never be used again. Either generalize it into a pattern, or just don't make it a skill at all.

### Template with too many variables

A template with 15 variables is too complex. If that many things change between uses, the template is trying to cover too many cases. Create two or three focused templates instead.

### Missing description on a template skill

```
# Bad — no variable documentation
name: "service_dockerfile"
description: "Dockerfile template"
is_template: true

# Good — variables documented
name: "service_dockerfile"
description: "Dockerfile template for a Python microservice.
Required variables: service_name, port (default 8000), python_version (default 3.12)."
is_template: true
```

### Forgetting `is_template=true`

If you create a skill with `{{ variable }}` syntax but don't set `is_template=true`, calling `render_skill` will return the raw content without substitution — it won't error, it will just do nothing. Always set the flag when the content contains placeholders.

---

## Quick Reference

### Skill Creation Checklist

Before saving a new skill, confirm:

- [ ] Name is specific, uses underscores, identifies the technology
- [ ] Description explains what it does and when to use it
- [ ] Category is one of: `code`, `config`, `procedure`, `template`, `reference`
- [ ] Tags cover the technology, purpose, and any relevant patterns
- [ ] `language` is set for code skills
- [ ] `is_template=true` if content contains `{{ variable }}` placeholders
- [ ] Template description lists all required variables
- [ ] Content is complete (imports included, no dangling TODOs)

### Template Checklist

For skills with `is_template=true`:

- [ ] All placeholders use `{{ snake_case_name }}` syntax
- [ ] Variables are documented in the description field
- [ ] Template rendered successfully with `render_skill` before attaching anywhere
- [ ] SandboxedEnvironment limitations understood (no arbitrary Python in templates)

### Category Quick Reference

| You have... | Use category |
|-------------|-------------|
| A function or class | `code` |
| A config file | `config` |
| A step-by-step checklist | `procedure` |
| A Jinja2 template with `{{ vars }}` | `template` |
| Notes, docs, or reference material | `reference` |

---

## See Also

- [Skills Module Reference](../modules/skills_modules.md) — Complete tool API reference
- [Project Planner Module](../modules/project_planner.md) — Creating projects and tasks to attach skills to
- [Database Schema](../architecture/database-schema.md) — `user_skills`, `project_skills`, `task_skills` tables
