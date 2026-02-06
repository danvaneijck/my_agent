"""Injective module - FastAPI service (scaffold)."""

from __future__ import annotations

import structlog
from fastapi import FastAPI

from modules.injective.manifest import MANIFEST
from modules.injective.tools import InjectiveTools
from shared.schemas.common import HealthResponse
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()
app = FastAPI(title="Injective Module (Scaffold)", version="1.0.0")

tools = InjectiveTools()


@app.get("/manifest", response_model=ModuleManifest)
async def manifest():
    """Return the module manifest."""
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall):
    """Execute a tool call."""
    try:
        tool_name = call.tool_name.split(".")[-1]

        if tool_name == "get_portfolio":
            result = await tools.get_portfolio()
        elif tool_name == "get_market_price":
            result = await tools.get_market_price(**call.arguments)
        elif tool_name == "place_order":
            result = await tools.place_order(**call.arguments)
        elif tool_name == "cancel_order":
            result = await tools.cancel_order(**call.arguments)
        elif tool_name == "get_positions":
            result = await tools.get_positions()
        else:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        return ToolResult(tool_name=call.tool_name, success=True, result=result)
    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e))
        return ToolResult(tool_name=call.tool_name, success=False, error=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
