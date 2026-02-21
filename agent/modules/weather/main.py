"""Weather module — FastAPI service."""

from __future__ import annotations

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from modules.weather.cache import CacheManager
from modules.weather.manifest import MANIFEST
from modules.weather.tools import WeatherTools
from shared.config import get_settings
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
app = FastAPI(title="Weather Module", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

tools: WeatherTools | None = None


@app.on_event("startup")
async def startup():
    global tools
    settings = get_settings()

    # Connect to Redis (graceful fallback if unavailable)
    redis_client = None
    try:
        import redis.asyncio as aioredis

        redis_client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await redis_client.ping()
        logger.info("weather_redis_connected")
    except Exception as e:
        logger.warning("weather_redis_unavailable", error=str(e))
        redis_client = None

    cache = CacheManager(redis_client)
    tools = WeatherTools(cache)
    logger.info("weather_module_ready")


@app.get("/manifest", response_model=ModuleManifest)
async def manifest(_=Depends(require_service_auth)):
    """Return the module manifest."""
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall, _=Depends(require_service_auth)):
    """Execute a tool call."""
    if tools is None:
        return ToolResult(tool_name=call.tool_name, success=False, error="Module not ready")

    try:
        tool_name = call.tool_name.split(".")[-1]
        args = dict(call.arguments)

        if tool_name == "weather_current":
            result = await tools.weather_current(**args)
        elif tool_name == "weather_forecast":
            result = await tools.weather_forecast(**args)
        elif tool_name == "weather_hourly":
            result = await tools.weather_hourly(**args)
        elif tool_name == "weather_alerts":
            result = await tools.weather_alerts(**args)
        else:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        return ToolResult(tool_name=call.tool_name, success=True, result=result)
    except Exception as e:
        logger.error("tool_execution_error", tool=call.tool_name, error=str(e), exc_info=True)
        return ToolResult(tool_name=call.tool_name, success=False, error=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
