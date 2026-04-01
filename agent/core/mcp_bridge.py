"""MCP bridge server — exposes the agent's tool registry as MCP tools.

Runs as a stdio-based MCP server that the Claude Code CLI spawns.
On startup it fetches tool definitions from the core orchestrator's
``/tools`` endpoint, registers them as MCP tools, and proxies calls
to the ``/execute`` endpoint.

Usage (via Claude CLI --mcp-config):
    {"mcpServers":{"agent":{"type":"stdio","command":"python",
     "args":["/app/core/mcp_bridge.py"]}}}
"""

from __future__ import annotations

import json
import logging
import os
import sys
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

# Logging must go to stderr — stdout is reserved for MCP protocol
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [mcp_bridge] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("mcp_bridge")

# Core orchestrator URL (inside Docker network)
CORE_URL = os.environ.get("CORE_URL", "http://localhost:8000")
SERVICE_AUTH_TOKEN = os.environ.get("SERVICE_AUTH_TOKEN", "")
MCP_USER_ID = os.environ.get("MCP_USER_ID", "")
MCP_USER_PERMISSION = os.environ.get("MCP_USER_PERMISSION", "owner")
MCP_CONVERSATION_ID = os.environ.get("MCP_CONVERSATION_ID", "")

# Platform context — injected into scheduler/location/crew tool calls
# so they can send notifications back to the right channel.
MCP_PLATFORM = os.environ.get("MCP_PLATFORM", "")
MCP_PLATFORM_CHANNEL_ID = os.environ.get("MCP_PLATFORM_CHANNEL_ID", "")
MCP_PLATFORM_THREAD_ID = os.environ.get("MCP_PLATFORM_THREAD_ID", "")
MCP_PLATFORM_SERVER_ID = os.environ.get("MCP_PLATFORM_SERVER_ID", "")

# Optional module filter — only register tools from these modules.
# Comma-separated list of module names (e.g. "research,benchmarker,knowledge").
# If empty, all tools are registered.
_allowed_modules_str = os.environ.get("MCP_ALLOWED_MODULES", "")
MCP_ALLOWED_MODULES = set(_allowed_modules_str.split(",")) if _allowed_modules_str else set()

# Type mapping from our tool schemas to Python types
_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "object": dict,
    "array": list,
}


def _auth_headers() -> dict[str, str]:
    if SERVICE_AUTH_TOKEN:
        return {"Authorization": f"Bearer {SERVICE_AUTH_TOKEN}"}
    return {}


def _fetch_tools() -> list[dict]:
    """Fetch tool definitions from core (synchronous — runs at startup)."""
    url = f"{CORE_URL}/tools?permission={MCP_USER_PERMISSION}"
    try:
        resp = httpx.get(url, headers=_auth_headers(), timeout=10)
        resp.raise_for_status()
        tools = resp.json().get("tools", [])
        log.info("Fetched %d tools from core", len(tools))
        return tools
    except Exception as e:
        log.error("Failed to fetch tools from core: %s", e)
        return []


def _call_tool(tool_name: str, arguments: dict) -> str:
    """Execute a tool via core's /execute endpoint (synchronous)."""
    # Inject platform context for scheduler/location/crew tools
    # (these need to know where to send notifications)
    if tool_name.startswith(("scheduler.", "location.", "crew.")):
        if MCP_PLATFORM and "platform" not in arguments:
            arguments["platform"] = MCP_PLATFORM
        if MCP_PLATFORM_CHANNEL_ID and "platform_channel_id" not in arguments:
            arguments["platform_channel_id"] = MCP_PLATFORM_CHANNEL_ID
        if MCP_PLATFORM_THREAD_ID and "platform_thread_id" not in arguments:
            arguments["platform_thread_id"] = MCP_PLATFORM_THREAD_ID
        if MCP_PLATFORM_SERVER_ID and "platform_server_id" not in arguments:
            arguments["platform_server_id"] = MCP_PLATFORM_SERVER_ID
        if tool_name == "scheduler.add_job" and MCP_CONVERSATION_ID:
            if "conversation_id" not in arguments:
                arguments["conversation_id"] = MCP_CONVERSATION_ID

    payload = {"tool_name": tool_name, "arguments": arguments}
    if MCP_USER_ID:
        payload["user_id"] = MCP_USER_ID
    if MCP_USER_PERMISSION:
        payload["user_permission"] = MCP_USER_PERMISSION
    if MCP_CONVERSATION_ID:
        payload["conversation_id"] = MCP_CONVERSATION_ID
    try:
        resp = httpx.post(
            f"{CORE_URL}/execute",
            json=payload,
            headers=_auth_headers(),
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("success"):
            result = data.get("result", "")
            return json.dumps(result, default=str) if not isinstance(result, str) else result
        else:
            return f"Error: {data.get('error', 'Unknown error')}"
    except Exception as e:
        return f"Error executing {tool_name}: {e}"


def _make_handler(original_name: str, params: list[dict]):
    """Dynamically create an async handler with proper type annotations.

    FastMCP infers the MCP tool schema from the function's type hints,
    so we must generate a function whose signature matches the tool's
    parameter definitions.
    """
    required_params = [p for p in params if p.get("required", True)]
    optional_params = [p for p in params if not p.get("required", True)]

    # Build function parameter strings
    req_strs = [p["name"] for p in required_params]
    opt_strs = [f"{p['name']}=None" for p in optional_params]
    all_param_strs = req_strs + opt_strs
    params_code = ", ".join(all_param_strs) if all_param_strs else ""

    # Collect all param names for the body
    all_names = [p["name"] for p in params]
    names_list = ", ".join(f'"{n}"' for n in all_names)

    func_name = original_name.replace(".", "_")

    func_code = f"""
async def {func_name}({params_code}) -> str:
    _args = {{}}
    _locals = locals()
    for _k in [{names_list}]:
        _v = _locals.get(_k)
        if _v is not None:
            _args[_k] = _v
    return _call_tool("{original_name}", _args)
"""
    # Execute in a namespace that has _call_tool available
    ns = {"_call_tool": _call_tool}
    exec(func_code, ns)
    fn = ns[func_name]

    # Set type annotations so FastMCP generates the right schema
    annotations = {"return": str}
    for p in required_params:
        annotations[p["name"]] = _TYPE_MAP.get(p.get("type", "string"), str)
    for p in optional_params:
        annotations[p["name"]] = Optional[_TYPE_MAP.get(p.get("type", "string"), str)]

    fn.__annotations__ = annotations
    return fn


# ---- Build MCP server ----

mcp = FastMCP("agent-tools")

_tools = _fetch_tools()

# Filter to allowed modules if specified
if MCP_ALLOWED_MODULES:
    _tools = [t for t in _tools if t["name"].split(".")[0] in MCP_ALLOWED_MODULES]
    log.info("Filtered to %d tools for modules: %s", len(_tools), MCP_ALLOWED_MODULES)

_registered = 0

for _tool_def in _tools:
    _name = _tool_def["name"]
    _desc = _tool_def.get("description", "")
    _params = _tool_def.get("parameters", [])
    _mcp_name = _name.replace(".", "_")

    try:
        _handler = _make_handler(_name, _params)
        mcp.add_tool(_handler, name=_mcp_name, description=_desc)
        _registered += 1
    except Exception as _exc:
        log.warning("Failed to register tool %s: %s", _name, _exc)

log.info("Registered %d/%d MCP tools", _registered, len(_tools))


def main():
    log.info("Starting MCP bridge server (stdio)")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
