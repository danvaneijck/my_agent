"""Injective module — FastAPI service for spot and derivative trading."""

from __future__ import annotations

import structlog
from fastapi import Depends, FastAPI

from modules.injective.manifest import MANIFEST
from modules.injective.tools import InjectiveTools
from shared.schemas.common import HealthResponse
from shared.auth import require_service_auth
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()
app = FastAPI(title="Injective Module", version="2.0.0")

tools: InjectiveTools | None = None

# All tool method names that match manifest definitions
TOOL_MAP = {
    "search_markets",
    "get_price",
    "get_orderbook",
    "get_balances",
    "get_portfolio",
    "get_subaccounts",
    "subaccount_transfer",
    "place_spot_order",
    "cancel_spot_order",
    "get_spot_orders",
    "place_derivative_order",
    "cancel_derivative_order",
    "get_derivative_orders",
    "get_positions",
    "close_position",
}


@app.on_event("startup")
async def startup():
    global tools
    tools = InjectiveTools()
    try:
        await tools.init()
        logger.info("injective_module_ready")
    except Exception as e:
        logger.error("injective_init_failed", error=str(e))
        # Keep tools object so health check works and read-only tools
        # can still report a meaningful error


@app.get("/manifest", response_model=ModuleManifest)
async def manifest(_=Depends(require_service_auth)):
    """Return the module manifest."""
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall, _=Depends(require_service_auth)):
    """Execute a tool call."""
    if tools is None:
        return ToolResult(tool_name=call.tool_name, success=False, error="Module not ready")

    tool_name = call.tool_name.split(".")[-1]

    if tool_name not in TOOL_MAP:
        return ToolResult(
            tool_name=call.tool_name,
            success=False,
            error=f"Unknown tool: {call.tool_name}",
        )

    try:
        method = getattr(tools, tool_name)
        result = await method(**call.arguments)
        return ToolResult(tool_name=call.tool_name, success=True, result=result)
    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e), exc_info=True)
        return ToolResult(tool_name=call.tool_name, success=False, error="Internal error processing request")


@app.get("/health", response_model=HealthResponse)
async def health():
    status = "ok" if tools and tools._initialized else "degraded"
    return HealthResponse(status=status)
