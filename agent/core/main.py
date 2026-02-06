"""FastAPI application for the core orchestrator service."""

from __future__ import annotations

import asyncio

import structlog
from fastapi import FastAPI, HTTPException

from core.llm_router.router import LLMRouter
from core.memory.summarizer import ConversationSummarizer
from core.orchestrator.agent_loop import AgentLoop
from core.orchestrator.context_builder import ContextBuilder
from core.orchestrator.tool_registry import ToolRegistry
from shared.config import get_settings
from shared.database import get_engine, get_session_factory
from shared.redis import close_redis
from shared.schemas.common import HealthResponse
from shared.schemas.messages import AgentResponse, IncomingMessage

structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
)

logger = structlog.get_logger()

app = FastAPI(title="AI Agent Orchestrator", version="1.0.0")

# Global instances (initialized on startup)
settings = get_settings()
llm_router: LLMRouter | None = None
tool_registry: ToolRegistry | None = None
agent_loop: AgentLoop | None = None
summarizer: ConversationSummarizer | None = None
_summarizer_task: asyncio.Task | None = None


async def _summarization_loop():
    """Background task that periodically summarizes old conversations."""
    while True:
        try:
            await asyncio.sleep(300)  # Run every 5 minutes
            if summarizer:
                count = await summarizer.summarize_old_conversations()
                if count > 0:
                    logger.info("summarization_complete", conversations=count)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("summarization_loop_error", error=str(e))
            await asyncio.sleep(60)


@app.on_event("startup")
async def startup():
    """Initialize all services on startup."""
    global llm_router, tool_registry, agent_loop, summarizer, _summarizer_task

    logger.info("starting_orchestrator")

    # Initialize LLM router
    llm_router = LLMRouter(settings)

    # Initialize tool registry and discover modules
    tool_registry = ToolRegistry(settings)
    await tool_registry.load_from_cache()
    # Try to discover modules (some may not be ready yet)
    try:
        await tool_registry.discover_all()
    except Exception as e:
        logger.warning("initial_discovery_failed", error=str(e))

    # Initialize context builder and agent loop
    session_factory = get_session_factory()
    context_builder = ContextBuilder(settings, llm_router)
    agent_loop = AgentLoop(
        settings=settings,
        llm_router=llm_router,
        tool_registry=tool_registry,
        context_builder=context_builder,
        session_factory=session_factory,
    )

    # Initialize memory summarizer
    summarizer = ConversationSummarizer(settings, llm_router, session_factory)
    _summarizer_task = asyncio.create_task(_summarization_loop())

    logger.info("orchestrator_ready")


@app.on_event("shutdown")
async def shutdown():
    """Clean up on shutdown."""
    global _summarizer_task
    if _summarizer_task:
        _summarizer_task.cancel()
        try:
            await _summarizer_task
        except asyncio.CancelledError:
            pass

    await close_redis()
    engine = get_engine()
    await engine.dispose()
    logger.info("orchestrator_shutdown")


@app.post("/message", response_model=AgentResponse)
async def handle_message(incoming: IncomingMessage) -> AgentResponse:
    """Receive a normalized message and return the agent's response."""
    if agent_loop is None:
        raise HTTPException(status_code=503, detail="Orchestrator not ready")

    logger.info(
        "incoming_message",
        platform=incoming.platform,
        user=incoming.platform_user_id,
        channel=incoming.platform_channel_id,
    )

    response = await agent_loop.run(incoming)

    logger.info(
        "outgoing_response",
        platform=incoming.platform,
        user=incoming.platform_user_id,
        has_error=response.error is not None,
    )

    return response


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(status="ok")


@app.post("/refresh-tools")
async def refresh_tools():
    """Re-discover all module manifests."""
    if tool_registry is None:
        raise HTTPException(status_code=503, detail="Orchestrator not ready")

    await tool_registry.discover_all()
    return {"status": "ok", "modules": list(tool_registry.manifests.keys())}
