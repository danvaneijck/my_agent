# Portal Integration Tests

This directory contains integration tests for the portal service, with a focus on terminal functionality.

## Running Tests

### Prerequisites

Install test dependencies:

```bash
pip install -r requirements.txt
```

### Run All Tests

```bash
# From the portal directory
pytest

# With verbose output
pytest -v

# With coverage
pytest --cov=portal --cov-report=html
```

### Run Specific Tests

```bash
# Run only terminal tests
pytest tests/test_terminal.py

# Run a specific test class
pytest tests/test_terminal.py::TestTerminalService

# Run a specific test function
pytest tests/test_terminal.py::TestTerminalService::test_create_session_success
```

### Run with Docker

To run tests in the Docker container:

```bash
# From the project root
docker compose exec portal pytest

# Or build and run in isolation
docker compose run --rm portal pytest
```

## Test Structure

### `test_terminal.py`

Comprehensive tests for terminal service functionality:

- **TestTerminalService**: Tests for the main TerminalService class
  - Container management (get_container, status validation)
  - Session lifecycle (create, attach, cleanup)
  - Session limits and concurrency
  - Error handling for Docker API failures

- **TestTerminalSession**: Tests for the TerminalSession dataclass
  - Session creation and initialization
  - Activity tracking
  - Expiration logic

- **TestCleanupLoop**: Tests for background session cleanup
  - Cleanup loop lifecycle
  - Expired session removal

## Coverage Goals

Target coverage: >80% for terminal-related code

Key areas:
- Terminal service session management
- Error handling and edge cases
- WebSocket protocol compliance
- Container lifecycle integration

## Adding New Tests

When adding new terminal features:

1. Add unit tests for new methods/functions
2. Add integration tests for WebSocket protocol changes
3. Add error case tests for new failure modes
4. Update this README with new test descriptions

## Common Issues

### Docker Not Available

If tests fail with "Docker not available", ensure:
- Docker daemon is running
- Your user has Docker permissions
- Tests are mocked appropriately (see fixtures)

### Async Test Failures

If async tests hang or fail:
- Check `pytest-asyncio` is installed
- Verify `asyncio_mode = auto` in `pytest.ini`
- Ensure async fixtures use `@pytest.fixture` with `async def`
