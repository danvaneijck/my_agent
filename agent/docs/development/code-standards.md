# Code Standards and Best Practices

> **Quick Context**: Python conventions, async patterns, and best practices for the AI Agent System.

## Related Documentation

- [Getting Started](getting-started.md) — Development setup
- [Testing](testing.md) — Testing strategies
- [API Reference](../api-reference/) — Schemas and models

---

## Python Version and Style

### Python 3.12+

All code uses Python 3.12 features:
- Type hints with `|` union syntax
- `match`/`case` statements (where appropriate)
- Modern async/await patterns

### Code Formatting

Follow PEP 8 with these specifics:

```python
# Line length: 100 characters (not 80)
# Use Black formatter defaults

# Imports: standard → third-party → local
import os
from typing import Any

import structlog
from fastapi import FastAPI

from shared.config import get_settings
from shared.models.user import User
```

---

## Type Hints

### Always Use Type Hints

```python
# ✅ Good
async def get_user(user_id: str) -> User | None:
    """Get user by ID."""
    ...

def process_data(items: list[dict[str, Any]]) -> dict[str, int]:
    """Process items and return counts."""
    ...

# ❌ Bad
async def get_user(user_id):
    ...

def process_data(items):
    ...
```

### Modern Union Syntax

```python
# ✅ Good (Python 3.10+)
from typing import Any

def foo(x: str | None) -> dict[str, Any]:
    ...

# ❌ Old syntax (don't use)
from typing import Optional, Dict, Any

def foo(x: Optional[str]) -> Dict[str, Any]:
    ...
```

### Generic Types

```python
# ✅ Good
from typing import Any

items: list[str] = ["a", "b"]
mapping: dict[str, int] = {"a": 1}
result: list[dict[str, Any]] = [{"key": "value"}]

# ❌ Old (don't use List, Dict)
from typing import List, Dict

items: List[str] = ["a", "b"]
```

---

## Async/Await Patterns

### All I/O Must Be Async

```python
# ✅ Good - async I/O
import httpx

async def fetch_data(url: str) -> dict[str, Any]:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()

# ❌ Bad - blocking I/O
import requests

def fetch_data(url: str) -> dict:
    response = requests.get(url)  # Blocks event loop!
    return response.json()
```

### Database Access

```python
# ✅ Good - async SQLAlchemy
from shared.database import get_session_factory
from sqlalchemy import select

async def get_users() -> list[User]:
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(User))
        return list(result.scalars().all())

# ❌ Bad - sync SQLAlchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

def get_users() -> list[User]:
    engine = create_engine(...)  # Blocks!
    with Session(engine) as session:
        return session.query(User).all()
```

### File I/O

```python
# ✅ Good - async file operations
import aiofiles

async def read_file(path: str) -> str:
    async with aiofiles.open(path, "r") as f:
        return await f.read()

# ❌ Bad - blocking file I/O
def read_file(path: str) -> str:
    with open(path, "r") as f:
        return f.read()  # Blocks!
```

### CPU-Bound Work

For CPU-intensive tasks, use process pool:

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

async def process_data(data: list[int]) -> list[int]:
    """CPU-intensive work in separate process."""
    loop = asyncio.get_event_loop()
    with ProcessPoolExecutor() as executor:
        result = await loop.run_in_executor(
            executor,
            expensive_computation,
            data
        )
    return result
```

---

## Logging with Structlog

### Always Use Structlog

```python
import structlog

logger = structlog.get_logger()

# ✅ Good - structured logging
logger.info(
    "user_action",
    action="login",
    user_id=user.id,
    platform="discord"
)

# ❌ Bad - string logging
import logging
logging.info(f"User {user.id} logged in from discord")
```

### Log Levels

```python
# DEBUG - Development details
logger.debug("cache_hit", key=cache_key, value=value)

# INFO - Normal operations
logger.info("user_created", user_id=user.id)

# WARNING - Unexpected but handled
logger.warning("rate_limit_approached", current=95, limit=100)

# ERROR - Errors that should be investigated
logger.error("api_call_failed", provider="openai", error=str(e))

# CRITICAL - System-level failures (rare)
logger.critical("database_connection_lost", retries=3)
```

### Error Logging

```python
# ✅ Good - log with context
try:
    result = await external_api_call()
except Exception as e:
    logger.error(
        "api_error",
        operation="fetch_data",
        provider="example",
        error=str(e),
        exc_info=True  # Include stack trace
    )
    raise

# ❌ Bad - generic logging
except Exception as e:
    logger.error(str(e))
    raise
```

---

## Error Handling

### Specific Exceptions

```python
# ✅ Good - specific exceptions
from fastapi import HTTPException

async def get_user(user_id: str) -> User:
    user = await db.get_user(user_id)
    if user is None:
        raise HTTPException(
            status_code=404,
            detail=f"User {user_id} not found"
        )
    return user

# ❌ Bad - generic exceptions
async def get_user(user_id: str) -> User:
    user = await db.get_user(user_id)
    if user is None:
        raise Exception("User not found")  # Too generic
    return user
```

### Tool Error Handling

```python
from shared.schemas.tools import ToolResult

async def execute_tool(call: ToolCall) -> ToolResult:
    try:
        result = await tools.do_thing(**call.arguments)
        return ToolResult(
            tool_name=call.tool_name,
            success=True,
            result=result
        )
    except ValueError as e:
        # Validation error - user's fault
        logger.warning("invalid_tool_input", error=str(e))
        return ToolResult(
            tool_name=call.tool_name,
            success=False,
            error=f"Invalid input: {e}"
        )
    except Exception as e:
        # Unexpected error - our fault
        logger.error("tool_execution_error", error=str(e), exc_info=True)
        return ToolResult(
            tool_name=call.tool_name,
            success=False,
            error=f"Tool execution failed: {e}"
        )
```

---

## Database Patterns

### Model Definitions

```python
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from uuid import UUID

from shared.database import Base

class User(Base):
    __tablename__ = "users"

    # Always use UUID for IDs
    id: Mapped[UUID] = mapped_column(primary_key=True)

    # Always use DateTime(timezone=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )

    # String columns with length
    email: Mapped[str] = mapped_column(String(255), unique=True)

    # Optional columns
    name: Mapped[str | None] = mapped_column(String(100))

    # Relationships
    posts: Mapped[list["Post"]] = relationship(back_populates="author")
```

### Query Patterns

```python
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload

# Simple query
async def get_user(user_id: UUID) -> User | None:
    async with session_factory() as session:
        result = await session.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

# Query with relationships
async def get_user_with_posts(user_id: UUID) -> User | None:
    async with session_factory() as session:
        result = await session.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.posts))
        )
        return result.scalar_one_or_none()

# Multiple conditions
async def find_users(platform: str, active: bool) -> list[User]:
    async with session_factory() as session:
        result = await session.execute(
            select(User).where(
                and_(
                    User.platform == platform,
                    User.is_active == active
                )
            )
        )
        return list(result.scalars().all())
```

### Transactions

```python
# Auto-commit on context exit
async def create_user(email: str) -> User:
    async with session_factory() as session:
        user = User(email=email)
        session.add(user)
        # Auto-commits when context exits successfully

# Manual commit for cross-container visibility
async def create_user_visible(email: str) -> User:
    async with session_factory() as session:
        user = User(email=email)
        session.add(user)
        await session.commit()  # Commit immediately
        await session.refresh(user)  # Reload to get defaults
        return user

# Rollback on error
async def update_user(user_id: UUID, email: str) -> User:
    async with session_factory() as session:
        user = await session.get(User, user_id)
        if not user:
            raise ValueError("User not found")

        user.email = email
        await session.commit()  # Commits
        return user
    # If exception raised, auto-rolls back
```

---

## Configuration

### Using Settings

```python
from shared.config import get_settings

# ✅ Good - use get_settings()
settings = get_settings()
api_key = settings.anthropic_api_key

# ❌ Bad - don't instantiate directly
from shared.config import Settings
settings = Settings()  # Don't do this
```

### Adding Settings

```python
# agent/shared/shared/config.py

class Settings(BaseSettings):
    # Existing settings...

    # New setting with type hint and default
    my_new_setting: str = "default_value"

    # Optional setting
    my_optional_setting: str | None = None

    # List setting (use str + parse_list helper)
    my_list_setting: str = "item1,item2,item3"

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )
```

### Using List Settings

```python
from shared.config import get_settings, parse_list

settings = get_settings()

# ✅ Good - parse at use
allowed_items = parse_list(settings.my_list_setting)

# ❌ Bad - list[str] field type
# This breaks with pydantic-settings v2
class Settings(BaseSettings):
    my_list: list[str] = ["a", "b"]  # Don't do this
```

---

## FastAPI Patterns

### Module Endpoints

```python
from fastapi import FastAPI
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult
from shared.schemas.common import HealthResponse

app = FastAPI(title="My Module")

@app.get("/manifest", response_model=ModuleManifest)
async def manifest():
    """Return module manifest."""
    return MANIFEST

@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall):
    """Execute tool call."""
    # Implementation
    ...

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check."""
    return HealthResponse(status="ok")
```

### Request Validation

```python
from pydantic import BaseModel, Field, validator

class CreateUserRequest(BaseModel):
    email: str = Field(..., description="User email")
    name: str = Field(..., min_length=1, max_length=100)
    age: int | None = Field(None, ge=0, le=150)

    @validator("email")
    def validate_email(cls, v):
        if "@" not in v:
            raise ValueError("Invalid email")
        return v.lower()

@app.post("/users")
async def create_user(request: CreateUserRequest):
    # Request is automatically validated
    ...
```

---

## Testing Standards

### Test File Organization

```python
# agent/modules/my_module/test_tools.py

import pytest
from modules.my_module.tools import MyModuleTools

class TestMyModuleTools:
    """Test suite for MyModule tools."""

    @pytest.mark.asyncio
    async def test_basic_operation(self):
        """Test basic tool operation."""
        tools = MyModuleTools()
        result = await tools.my_tool(param="value")
        assert result["key"] == "expected"

    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test tool handles errors correctly."""
        tools = MyModuleTools()
        with pytest.raises(ValueError):
            await tools.my_tool(param="invalid")
```

### Fixtures

```python
# conftest.py

import pytest
from shared.database import get_session_factory

@pytest.fixture
async def db_session():
    """Provide test database session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session
        await session.rollback()  # Rollback test data

@pytest.fixture
def mock_api_client(mocker):
    """Mock external API client."""
    client = mocker.Mock()
    client.get.return_value = {"data": "test"}
    return client
```

---

## Common Patterns

### Retry Logic

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
async def call_external_api() -> dict:
    """Call API with retry."""
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.example.com/data")
        response.raise_for_status()
        return response.json()
```

### Context Managers

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def get_client():
    """Provide client with automatic cleanup."""
    client = MyClient()
    try:
        await client.connect()
        yield client
    finally:
        await client.disconnect()

# Usage
async with get_client() as client:
    await client.do_something()
```

### Dependency Injection

```python
from fastapi import Depends

async def get_current_user(token: str) -> User:
    """Dependency that validates and returns user."""
    # Validate token, get user
    return user

@app.post("/protected")
async def protected_endpoint(
    user: User = Depends(get_current_user)
):
    """Endpoint with automatic user validation."""
    return {"user_id": user.id}
```

---

## Security

### Never Log Secrets

```python
# ✅ Good
logger.info("api_call", provider="openai")

# ❌ Bad
logger.info("api_call", api_key=settings.openai_api_key)
```

### Validate User Input

```python
# ✅ Good - validate before use
def sanitize_filename(filename: str) -> str:
    """Remove dangerous characters from filename."""
    return "".join(c for c in filename if c.isalnum() or c in "._- ")

# ❌ Bad - use input directly
import os
os.path.join("/uploads", user_input)  # Path traversal risk!
```

### SQL Injection Prevention

```python
# ✅ Good - use SQLAlchemy ORM
result = await session.execute(
    select(User).where(User.email == user_email)
)

# ❌ Bad - string concatenation
query = f"SELECT * FROM users WHERE email = '{user_email}'"
await session.execute(query)  # SQL injection!
```

---

## Documentation

### Docstrings

```python
def calculate_score(items: list[dict], weight: float = 1.0) -> float:
    """Calculate weighted score from items.

    Args:
        items: List of items with 'value' key
        weight: Multiplier for final score

    Returns:
        Weighted total score

    Raises:
        ValueError: If items is empty or weight is negative

    Example:
        >>> calculate_score([{"value": 10}, {"value": 20}], weight=2.0)
        60.0
    """
    if not items or weight < 0:
        raise ValueError("Invalid inputs")

    total = sum(item["value"] for item in items)
    return total * weight
```

### Comments

```python
# ✅ Good - explain WHY
# Cache manifests for 1 hour to reduce HTTP overhead
# during high-frequency tool calls
MANIFEST_TTL = 3600

# ❌ Bad - explain WHAT (code already does this)
# Set TTL to 3600
MANIFEST_TTL = 3600
```

---

## Performance

### Use Generators for Large Data

```python
# ✅ Good - memory efficient
async def process_users():
    async for user in stream_users():
        await process(user)

# ❌ Bad - loads everything into memory
async def process_users():
    users = await get_all_users()  # Could be millions!
    for user in users:
        await process(user)
```

### Batch Database Operations

```python
# ✅ Good - bulk insert
async def create_users(emails: list[str]):
    users = [User(email=email) for email in emails]
    async with session_factory() as session:
        session.add_all(users)
        await session.commit()

# ❌ Bad - one at a time
async def create_users(emails: list[str]):
    for email in emails:
        async with session_factory() as session:
            user = User(email=email)
            session.add(user)
            await session.commit()  # New transaction each time!
```

---

## Summary Checklist

When writing code, ensure:

- [ ] Type hints on all functions
- [ ] All I/O is async
- [ ] Structlog for logging
- [ ] Specific exceptions with context
- [ ] Database uses async SQLAlchemy
- [ ] Settings via get_settings()
- [ ] Docstrings on public functions
- [ ] Tests for new functionality
- [ ] No secrets in logs
- [ ] Input validation

---

**Related Documentation:**
- [Getting Started](getting-started.md) — Development setup
- [Testing](testing.md) — Testing patterns
- [Debugging](debugging.md) — Debugging techniques

[Back to Documentation Index](../INDEX.md)
