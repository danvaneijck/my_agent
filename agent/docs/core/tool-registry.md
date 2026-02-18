# Tool Registry

> **Quick Context**: Module discovery, manifest caching, and tool execution routing.
>
> **Related Files**: `agent/core/orchestrator/tool_registry.py`
>
> **Related Docs**: [Core Overview](overview.md), [Agent Loop](agent-loop.md), [Module System](../architecture/module-system.md)
>
> **When to Read**: Adding modules, troubleshooting tool execution, understanding module discovery

## Purpose

The Tool Registry is responsible for:
- **Discovering modules** via HTTP (`GET /manifest`)
- **Caching manifests** in Redis (1-hour TTL)
- **Filtering tools** by user permission and persona allowed modules
- **Routing tool calls** to the correct module (`POST /execute`)
- **Converting tool formats** for LLM providers

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    Tool Registry                         │
│                                                          │
│  ┌─────────────────────────────────────────────────────┐│
│  │ discover_all()                                      ││
│  │   For each module in module_services:              ││
│  │   GET {url}/manifest → ModuleManifest              ││
│  │   Cache in Redis (1 hour TTL)                      ││
│  └─────────────────────────────────────────────────────┘│
│                          ↓                              │
│  ┌─────────────────────────────────────────────────────┐│
│  │ get_tools_for_user(permission, allowed_modules)    ││
│  │   Filter by:                                       ││
│  │   - User permission level (guest → owner)          ││
│  │   - Persona's allowed_modules                      ││
│  └─────────────────────────────────────────────────────┘│
│                          ↓                              │
│  ┌─────────────────────────────────────────────────────┐│
│  │ tools_to_openai_format(tools)                      ││
│  │   Convert ToolDefinition → OpenAI function format  ││
│  └─────────────────────────────────────────────────────┘│
│                          ↓                              │
│  ┌─────────────────────────────────────────────────────┐│
│  │ execute_tool(ToolCall)                             ││
│  │   Split tool_name → module_name                    ││
│  │   POST {module_url}/execute                        ││
│  │   Return ToolResult                                ││
│  └─────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────┘
```

## Module Discovery

### Discovery Flow

```
Startup / Refresh Request
  ↓
For each module in module_services:
  ↓
  GET http://module:8000/manifest
  ↓
  ┌─ Success (200 OK)
  │  ├─ Parse ModuleManifest
  │  ├─ Store in self.manifests dict
  │  ├─ Cache in Redis (key: "module_manifest:{name}", TTL: 3600s)
  │  └─ Log success
  │
  └─ Failure
     ├─ Log warning (module_manifest_error or module_unreachable)
     └─ Continue to next module
```

### Code: `discover_all()`

**File**: `tool_registry.py:27-59`

```python
async def discover_all(self) -> None:
    """Query all configured modules for their manifests and cache them."""
    redis = await get_redis()
    async with httpx.AsyncClient(timeout=10.0) as client:
        for module_name, url in self.settings.module_services.items():
            try:
                resp = await client.get(f"{url}/manifest")
                if resp.status_code == 200:
                    manifest = ModuleManifest(**resp.json())
                    self.manifests[module_name] = manifest

                    # Cache in Redis
                    await redis.set(
                        f"module_manifest:{module_name}",
                        manifest.model_dump_json(),
                        ex=3600,  # 1 hour TTL
                    )

                    logger.info(
                        "module_discovered",
                        module=module_name,
                        tools=len(manifest.tools),
                    )
                else:
                    logger.warning(
                        "module_manifest_error",
                        module=module_name,
                        status=resp.status_code,
                    )
            except Exception as e:
                logger.warning(
                    "module_unreachable",
                    module=module_name,
                    error=str(e),
                )
```

**Timeout**: 10 seconds per module

**Error Handling**:
- Discovery failures are logged but don't crash the system
- Failed modules simply won't have tools available
- Retry on next `discover_all()` call

### When Discovery Happens

1. **Manual refresh**: `make refresh-tools` or `POST /refresh-tools`
2. **First tool filter request**: Lazy discovery if cache is empty
3. **Module restart**: After rebuilding a module

### Checking Discovery Status

```bash
# View discovered modules
make list-modules

# Or via logs
make logs-core | grep "module_discovered"

# Check Redis cache
make redis-cli
> KEYS module_manifest:*
> GET module_manifest:research
```

## Manifest Caching

### Redis Cache Strategy

**Key Format**: `module_manifest:{module_name}`

**TTL**: 3600 seconds (1 hour)

**Why Cache?**
- Avoid HTTP calls on every request
- Faster tool filtering
- Resilience if module temporarily unreachable

### Code: `load_from_cache()`

**File**: `tool_registry.py:61-67`

```python
async def load_from_cache(self) -> None:
    """Load manifests from Redis cache."""
    redis = await get_redis()
    for module_name in self.settings.module_services:
        cached = await redis.get(f"module_manifest:{module_name}")
        if cached:
            self.manifests[module_name] = ModuleManifest(**json.loads(cached))
```

**When Used**:
- On startup (before first request)
- After cache expiry (1 hour)

### Cache Invalidation

```bash
# Invalidate all manifests
make redis-cli
> DEL module_manifest:research
> DEL module_manifest:file_manager
# ... or
> FLUSHDB  # careful: clears all Redis data

# Then refresh
make refresh-tools
```

## Permission Filtering

### Permission Hierarchy

```
guest (0) < user (1) < admin (2) < owner (3)
```

**Defined in**: `tool_registry.py:17`
```python
PERMISSION_LEVELS = ["guest", "user", "admin", "owner"]
```

### Filtering Logic

**Code**: `tool_registry.py:69-84`

```python
def get_tools_for_user(
    self,
    user_permission: str,
    allowed_modules: list[str],
) -> list[ToolDefinition]:
    """Filter tools based on user permission and persona's allowed modules."""
    user_level = PERMISSION_LEVELS.index(user_permission) if user_permission in PERMISSION_LEVELS else 0

    tools = []
    for module_name, manifest in self.manifests.items():
        # Check if module is in allowed_modules
        if module_name not in allowed_modules:
            continue

        for tool in manifest.tools:
            required_level = PERMISSION_LEVELS.index(tool.required_permission) if tool.required_permission in PERMISSION_LEVELS else 0

            # Check if user has sufficient permission
            if user_level >= required_level:
                tools.append(tool)

    return tools
```

### Two-Stage Filtering

1. **Module Level**: Check `allowed_modules` from persona
2. **Tool Level**: Check `user_permission` vs `tool.required_permission`

### Example

```python
# User
user.permission_level = "user"  # level 1

# Persona
persona.allowed_modules = ["research", "file_manager", "code_executor"]

# Module manifests
research.tools = [
    ToolDefinition(name="research.web_search", required_permission="guest"),     # level 0
    ToolDefinition(name="research.fetch_webpage", required_permission="guest"),  # level 0
]

file_manager.tools = [
    ToolDefinition(name="file_manager.create_document", required_permission="guest"),  # level 0
    ToolDefinition(name="file_manager.delete_file", required_permission="user"),       # level 1
]

code_executor.tools = [
    ToolDefinition(name="code_executor.run_python", required_permission="user"),  # level 1
    ToolDefinition(name="code_executor.run_shell", required_permission="admin"),  # level 2 ❌
]

scheduler.tools = [
    ToolDefinition(name="scheduler.add_job", required_permission="admin"),  # level 2 ❌
]

# Result: user gets these tools
[
    "research.web_search",        # ✓ guest ≤ user, module allowed
    "research.fetch_webpage",     # ✓ guest ≤ user, module allowed
    "file_manager.create_document",  # ✓ guest ≤ user, module allowed
    "file_manager.delete_file",      # ✓ user ≤ user, module allowed
    "code_executor.run_python",   # ✓ user ≤ user, module allowed
    # code_executor.run_shell excluded (admin > user)
    # scheduler.add_job excluded (module not in allowed_modules)
]
```

## Tool Name Routing

### Naming Convention

All tool names follow the pattern: `{module_name}.{tool_method_name}`

Examples:
- `research.web_search`
- `file_manager.create_document`
- `code_executor.run_python`
- `scheduler.add_job`

### Routing Logic

**Code**: `tool_registry.py:117-126`

```python
# Extract module name from tool name
parts = tool_call.tool_name.split(".", 1)
if len(parts) != 2:
    return ToolResult(
        tool_name=tool_call.tool_name,
        success=False,
        error=f"Invalid tool name format: {tool_call.tool_name}. Expected 'module.tool_name'.",
    )

module_name = parts[0]  # "research" from "research.web_search"
```

**Why Split on First `.` Only?**

Allows tool names like `git_platform.issue.create` if needed (though current convention is flat).

### Module URL Lookup

```python
if module_name not in self.settings.module_services:
    return ToolResult(
        tool_name=tool_call.tool_name,
        success=False,
        error=f"Unknown module: {module_name}",
    )

url = self.settings.module_services[module_name]
# e.g. "http://research:8000"
```

**module_services Definition**: `shared/config.py`
```python
module_services: dict[str, str] = {
    "research": "http://research:8000",
    "file_manager": "http://file-manager:8000",
    "code_executor": "http://code-executor:8000",
    # ...
}
```

## Tool Execution

### Execution Flow

```
ToolCall from LLM
  ↓
Split tool_name → module_name + method_name
  ↓
Lookup module URL
  ↓
Determine timeout (30s default, 120s for slow modules)
  ↓
POST {module_url}/execute
  ├─ Payload: {tool_name, arguments, user_id}
  ├─ Timeout: 30s or 120s
  └─ HTTP Client: httpx.AsyncClient
  ↓
┌─ Success (200 OK)
│  └─ Return ToolResult(**resp.json())
│
├─ HTTP Error (4xx/5xx)
│  └─ Return ToolResult(success=False, error="...")
│
├─ Timeout
│  └─ Return ToolResult(success=False, error="Timed out")
│
└─ Network Error
   └─ Return ToolResult(success=False, error="...")
```

### Code: `execute_tool()`

**File**: `tool_registry.py:117-167`

```python
async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
    """Route a tool call to the correct module service."""
    # Extract module name
    parts = tool_call.tool_name.split(".", 1)
    if len(parts) != 2:
        return ToolResult(
            tool_name=tool_call.tool_name,
            success=False,
            error=f"Invalid tool name format: {tool_call.tool_name}",
        )

    module_name = parts[0]
    if module_name not in self.settings.module_services:
        return ToolResult(
            tool_name=tool_call.tool_name,
            success=False,
            error=f"Unknown module: {module_name}",
        )

    url = self.settings.module_services[module_name]

    # Determine timeout
    slow_modules = parse_list(self.settings.slow_modules)
    timeout = (
        float(self.settings.tool_execution_timeout)
        if module_name in slow_modules
        else 30.0
    )

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            payload = {
                "tool_name": tool_call.tool_name,
                "arguments": tool_call.arguments,
            }
            if tool_call.user_id:
                payload["user_id"] = tool_call.user_id

            resp = await client.post(f"{url}/execute", json=payload)

            if resp.status_code == 200:
                return ToolResult(**resp.json())
            else:
                return ToolResult(
                    tool_name=tool_call.tool_name,
                    success=False,
                    error=f"Module returned status {resp.status_code}: {resp.text}",
                )

        except httpx.TimeoutException:
            return ToolResult(
                tool_name=tool_call.tool_name,
                success=False,
                error=f"Tool execution timed out ({timeout:.0f}s).",
            )

        except Exception as e:
            return ToolResult(
                tool_name=tool_call.tool_name,
                success=False,
                error=f"Tool execution error: {str(e)}",
            )
```

### Timeouts

**Default**: 30 seconds

**Slow Modules**: 120 seconds

**Configuration**: `shared/config.py`
```python
slow_modules: str = "garmin,renpho_biometrics,claude_code,deployer"
tool_execution_timeout: int = 120
```

**Why Longer Timeouts?**
- `garmin`, `renpho_biometrics` — External API calls with slow responses
- `claude_code` — May compile code, run tests
- `deployer` — Docker build and container startup

### User Context Injection

```python
if tool_call.user_id:
    payload["user_id"] = tool_call.user_id
```

Injected by [Agent Loop](agent-loop.md) before calling `execute_tool()`.

**Why**: Modules need to associate resources (files, memories, jobs) with the user.

## OpenAI Format Conversion

### Why Convert?

LLM providers (Anthropic, OpenAI, Google) expect tool definitions in different formats. The registry converts to OpenAI format, which providers then adapt to their native format.

### Code: `tools_to_openai_format()`

**File**: `tool_registry.py:86-115`

```python
def tools_to_openai_format(self, tools: list[ToolDefinition]) -> list[dict]:
    """Convert tool definitions to OpenAI function calling format."""
    openai_tools = []
    for tool in tools:
        properties = {}
        required = []

        for param in tool.parameters:
            prop: dict = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum

            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        openai_tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        })

    return openai_tools
```

### Example Conversion

**Input** (`ToolDefinition`):
```python
ToolDefinition(
    name="research.web_search",
    description="Search the web and return results",
    parameters=[
        ToolParameter(name="query", type="string", description="Search query", required=True),
        ToolParameter(name="max_results", type="integer", description="Max results", required=False),
    ],
    required_permission="guest",
)
```

**Output** (OpenAI format):
```json
{
  "type": "function",
  "function": {
    "name": "research.web_search",
    "description": "Search the web and return results",
    "parameters": {
      "type": "object",
      "properties": {
        "query": {
          "type": "string",
          "description": "Search query"
        },
        "max_results": {
          "type": "integer",
          "description": "Max results"
        }
      },
      "required": ["query"]
    }
  }
}
```

## Error Handling

### Discovery Errors

**Module unreachable**:
- Logged as warning
- Module not added to manifests
- System continues working with other modules

**Manifest parse error**:
- Logged as warning
- Module skipped
- Check module's `/manifest` endpoint directly

### Execution Errors

**Invalid tool name format**:
```python
ToolResult(success=False, error="Invalid tool name format: xyz. Expected 'module.tool_name'.")
```

**Unknown module**:
```python
ToolResult(success=False, error="Unknown module: xyz")
```

**HTTP error**:
```python
ToolResult(success=False, error="Module returned status 500: Internal Server Error")
```

**Timeout**:
```python
ToolResult(success=False, error="Tool execution timed out (30s).")
```

**Network error**:
```python
ToolResult(success=False, error="Tool execution error: Connection refused")
```

### Retry Logic

Tool registry **does not retry** on failure — retry is handled by [Agent Loop](agent-loop.md):

```python
# agent_loop.py:252-261
result = await self.tool_registry.execute_tool(tool_call)

# If first attempt fails, retry once
if not result.success:
    logger.warning("tool_call_failed_retrying", tool=tool_call.tool_name, error=result.error)
    result = await self.tool_registry.execute_tool(tool_call)
```

## Configuration

### Module Services

**File**: `shared/config.py`

```python
module_services: dict[str, str] = {
    "research": "http://research:8000",
    "file_manager": "http://file-manager:8000",
    "code_executor": "http://code-executor:8000",
    "knowledge": "http://knowledge:8000",
    "atlassian": "http://atlassian:8000",
    "claude_code": "http://claude-code:8000",
    "deployer": "http://deployer:8000",
    "scheduler": "http://scheduler:8000",
    "garmin": "http://garmin:8000",
    "renpho_biometrics": "http://renpho-biometrics:8000",
    "location": "http://location:8000",
    "git_platform": "http://git-platform:8000",
    "project_planner": "http://project-planner:8000",
    "injective": "http://injective:8000",
}
```

**Adding a Module**:
```python
"my_module": "http://my-module:8000",
```

### Slow Modules

```python
slow_modules: str = "garmin,renpho_biometrics,claude_code,deployer"
tool_execution_timeout: int = 120
```

### Default Guest Modules

```python
default_guest_modules: str = "research,file_manager,code_executor,knowledge"
```

## Troubleshooting

### Tool not available to LLM

**Diagnosis**:
```bash
# Check discovered modules
make list-modules

# Check logs for discovery errors
make logs-core | grep module_discovered
make logs-core | grep module_unreachable

# Verify module is running
docker compose ps | grep my-module

# Check manifest endpoint directly
curl http://localhost:8000/api/modules
```

**Fixes**:
1. Ensure module is in `module_services` (config.py)
2. Verify module is running: `docker compose ps`
3. Rebuild module: `make restart-module M=my-module`
4. Refresh tools: `make refresh-tools`

### Tool execution fails

**Diagnosis**:
```bash
# Check module logs
make logs-module M=research

# Test module directly
curl -X POST http://localhost:8000/api/modules/research/execute \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "research.web_search", "arguments": {"query": "test"}}'
```

**Common Causes**:
- Module crashed or not responding
- Timeout too short (increase for slow modules)
- Invalid arguments (check manifest parameter definitions)
- Missing user_id (some tools require it)

### Permission denied

**Diagnosis**:
```bash
# Check user permission level
make psql
SELECT permission_level FROM users WHERE id = 'uuid';

# Check persona allowed_modules
SELECT allowed_modules FROM personas WHERE id = 'uuid';
```

**Fix**:
- Promote user: `make shell` then `cli.py user promote ...`
- Update persona allowed_modules

## Testing

See [Testing Guide](../development/testing.md) for:
- Mocking module discovery
- Testing permission filtering
- Testing tool execution routing
- Integration testing with real modules

## Related Documentation

- [Core Overview](overview.md) — Component architecture
- [Agent Loop](agent-loop.md) — How tools are executed in the loop
- [Module System](../architecture/module-system.md) — Module architecture
- [Adding Modules](../modules/ADDING_MODULES.md) — Creating new modules
- [Module Contract](../api-reference/module-contract.md) — /manifest and /execute specs
- [Troubleshooting](../troubleshooting/module-issues.md) — Module problems

---

[Back to Core Documentation](README.md) | [Documentation Index](../INDEX.md)
