"""Tool registry - discovers and caches module manifests."""

from __future__ import annotations

import json

import httpx
import structlog

from shared.config import Settings
from shared.redis import get_redis
from shared.schemas.tools import ModuleManifest, ToolCall, ToolDefinition, ToolResult

logger = structlog.get_logger()

# Permission hierarchy (higher index = more privileged)
PERMISSION_LEVELS = ["guest", "user", "admin", "owner"]


class ToolRegistry:
    """Discovers, caches, and routes tool calls to modules."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.manifests: dict[str, ModuleManifest] = {}

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

    async def load_from_cache(self) -> None:
        """Load manifests from Redis cache."""
        redis = await get_redis()
        for module_name in self.settings.module_services:
            cached = await redis.get(f"module_manifest:{module_name}")
            if cached:
                self.manifests[module_name] = ModuleManifest(**json.loads(cached))

    def get_tools_for_user(
        self,
        user_permission: str,
        allowed_modules: list[str],
    ) -> list[ToolDefinition]:
        """Filter tools based on user permission and persona's allowed modules."""
        user_level = PERMISSION_LEVELS.index(user_permission) if user_permission in PERMISSION_LEVELS else 0
        tools = []
        for module_name, manifest in self.manifests.items():
            if module_name not in allowed_modules:
                continue
            for tool in manifest.tools:
                required_level = PERMISSION_LEVELS.index(tool.required_permission) if tool.required_permission in PERMISSION_LEVELS else 0
                if user_level >= required_level:
                    tools.append(tool)
        return tools

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

    async def execute_tool(self, tool_call: ToolCall) -> ToolResult:
        """Route a tool call to the correct module service."""
        # Extract module name from tool name (e.g. "file_manager.create_document" -> "file_manager")
        parts = tool_call.tool_name.split(".", 1)
        if len(parts) != 2:
            return ToolResult(
                tool_name=tool_call.tool_name,
                success=False,
                error=f"Invalid tool name format: {tool_call.tool_name}. Expected 'module.tool_name'.",
            )

        module_name = parts[0]
        if module_name not in self.settings.module_services:
            return ToolResult(
                tool_name=tool_call.tool_name,
                success=False,
                error=f"Unknown module: {module_name}",
            )

        url = self.settings.module_services[module_name]
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.post(
                    f"{url}/execute",
                    json={
                        "tool_name": tool_call.tool_name,
                        "arguments": tool_call.arguments,
                    },
                )
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
                    error="Tool execution timed out (30s).",
                )
            except Exception as e:
                return ToolResult(
                    tool_name=tool_call.tool_name,
                    success=False,
                    error=f"Tool execution error: {str(e)}",
                )
