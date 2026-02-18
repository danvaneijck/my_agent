"""FastAPI application for the core orchestrator service."""

from __future__ import annotations

import asyncio
import json

import structlog
from fastapi import Depends, FastAPI, HTTPException

from shared.auth import require_service_auth

from sqlalchemy import select

from core.llm_router.router import LLMRouter
from core.memory.summarizer import ConversationSummarizer
from core.orchestrator.agent_loop import AgentLoop
from core.orchestrator.context_builder import ContextBuilder
from core.orchestrator.tool_registry import ToolRegistry
from shared.config import get_settings
from shared.database import get_engine, get_session_factory
from shared.models.persona import Persona
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


async def _delayed_discovery(registry: ToolRegistry, expected_modules: set[str]):
    """Retry module discovery until all configured modules are found."""
    for delay in (5, 10, 20, 30):
        missing = expected_modules - set(registry.manifests.keys())
        if not missing:
            logger.info("all_modules_discovered", modules=list(registry.manifests.keys()))
            return
        logger.info("waiting_for_modules", missing=list(missing), delay=delay)
        await asyncio.sleep(delay)
        try:
            await registry.discover_all()
        except Exception as e:
            logger.warning("delayed_discovery_attempt_failed", error=str(e))

    missing = expected_modules - set(registry.manifests.keys())
    if missing:
        logger.warning(
            "delayed_discovery_exhausted",
            missing=list(missing),
            msg="Use POST /refresh-tools to retry manually",
        )
    else:
        logger.info("all_modules_discovered", modules=list(registry.manifests.keys()))


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

    # If any configured modules are missing, schedule background retry
    expected_modules = set(settings.module_services.keys())
    discovered = set(tool_registry.manifests.keys())
    if discovered < expected_modules:
        logger.info(
            "scheduling_module_discovery_retry",
            discovered=list(discovered),
            missing=list(expected_modules - discovered),
        )
        asyncio.create_task(_delayed_discovery(tool_registry, expected_modules))

    # Ensure a default persona exists
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(select(Persona).where(Persona.is_default.is_(True)))
        default_persona = result.scalar_one_or_none()
        if not default_persona:
            modules = list(settings.module_services.keys())
            default_persona = Persona(
                name="Default Assistant",
                system_prompt=(
                    "You are a helpful AI assistant. Be concise, accurate, and helpful. "
                    "Use your tools when they can help accomplish the user's task."
                ),
                allowed_modules=json.dumps(modules),
                is_default=True,
            )
            session.add(default_persona)
            await session.commit()
            logger.info("created_default_persona", modules=modules)
        else:
            # Update allowed_modules on existing default persona to include any new modules
            current_modules = json.loads(default_persona.allowed_modules)
            all_modules = list(settings.module_services.keys())
            if set(current_modules) != set(all_modules):
                default_persona.allowed_modules = json.dumps(all_modules)
                await session.commit()
                logger.info("updated_default_persona_modules", modules=all_modules)

    # Initialize context builder and agent loop
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
async def handle_message(incoming: IncomingMessage, _=Depends(require_service_auth)) -> AgentResponse:
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
async def refresh_tools(_=Depends(require_service_auth)):
    """Re-discover all module manifests."""
    if tool_registry is None:
        raise HTTPException(status_code=503, detail="Orchestrator not ready")

    await tool_registry.discover_all()
    return {"status": "ok", "modules": list(tool_registry.manifests.keys())}


from pydantic import BaseModel


class EmbedRequest(BaseModel):
    text: str


class ContinueRequest(BaseModel):
    """Request from scheduler to resume a conversation after a background job completes."""
    platform: str
    platform_channel_id: str
    platform_thread_id: str | None = None
    user_id: str  # internal UUID (not platform ID)
    content: str  # completion context message for the LLM
    job_id: str | None = None
    workflow_id: str | None = None
    result_data: dict | None = None


@app.post("/continue", response_model=AgentResponse)
async def continue_conversation(req: ContinueRequest, _=Depends(require_service_auth)) -> AgentResponse:
    """Resume a conversation after a scheduler job completes.

    This is called by the scheduler worker when a job with
    on_complete='resume_conversation' finishes. It re-enters the agent loop
    with the completion context, allowing the LLM to continue with follow-up
    actions (e.g. deploy after a build).
    """
    if agent_loop is None:
        raise HTTPException(status_code=503, detail="Orchestrator not ready")

    logger.info(
        "continue_conversation",
        platform=req.platform,
        user_id=req.user_id,
        channel=req.platform_channel_id,
        job_id=req.job_id,
    )

    # Look up the platform_user_id for this internal user_id so the agent loop
    # can resolve the user properly via its normal path.
    from sqlalchemy import select as sa_select
    from shared.models.user import UserPlatformLink

    session_factory = get_session_factory()
    platform_user_id = req.user_id  # fallback to internal ID

    async with session_factory() as session:
        result = await session.execute(
            sa_select(UserPlatformLink).where(
                UserPlatformLink.user_id == req.user_id,
                UserPlatformLink.platform == req.platform,
            )
        )
        link = result.scalar_one_or_none()
        if link:
            platform_user_id = link.platform_user_id

    # Build a system-initiated message that the agent loop processes normally
    context_parts = [f"[Automated workflow continuation — job {req.job_id or 'unknown'}]"]
    context_parts.append(req.content)
    if req.result_data:
        # Only include essential fields — full json_output can be enormous
        summary_keys = [
            "task_id", "status", "workspace", "mode", "error",
            "elapsed_seconds", "exit_code",
        ]
        summary = {
            k: v for k, v in req.result_data.items()
            if k in summary_keys and v is not None
        }
        if summary:
            context_parts.append(
                f"\nTask result summary: {json.dumps(summary, default=str)}"
            )
    guidance = ""
    if req.result_data and isinstance(req.result_data, dict):
        task_status = req.result_data.get("status")
        if task_status == "completed":
            guidance = (
                "\nThe claude_code task completed successfully. Next steps: "
                "1) Update the project task status to 'in_review'. "
                "2) Create a PR from the phase branch into the project branch "
                "using git_platform.create_pull_request. Store pr_number on the task. "
                "3) If auto_merge is enabled on the project, merge the PR immediately "
                "with git_platform.merge_pull_request and update status to 'done'. "
                "Otherwise, notify the user the PR is ready for review. "
                "4) Use get_next_task for the next todo task in the phase. "
                "For subsequent tasks in the same phase, prefer continue_task on the "
                "completed workspace (with auto_push=true) to keep file context. "
                "5) If no more tasks, update the phase status."
            )
        elif task_status == "awaiting_input":
            guidance = (
                "\nThe claude_code task finished in plan mode. Present "
                "the plan to the user. When approved, use continue_task "
                "with mode='execute' and auto_push=true."
            )
        elif task_status in ("failed", "timed_out"):
            guidance = (
                "\nThe task failed. Update the project task status to "
                "'failed' with the error message and notify the user."
            )
    if not guidance:
        guidance = (
            "\nContinue with the next steps. If the task succeeded, "
            "proceed with follow-up actions. If it failed, explain "
            "what went wrong."
        )
    context_parts.append(guidance)

    incoming = IncomingMessage(
        platform=req.platform,
        platform_user_id=platform_user_id,
        platform_channel_id=req.platform_channel_id,
        platform_thread_id=req.platform_thread_id,
        content="\n".join(context_parts),
    )

    response = await agent_loop.run(incoming)

    logger.info(
        "continue_conversation_complete",
        platform=req.platform,
        job_id=req.job_id,
        has_error=response.error is not None,
    )

    return response


@app.post("/embed")
async def embed(req: EmbedRequest, _=Depends(require_service_auth)):
    """Generate an embedding for a given text. Used by modules like knowledge."""
    if llm_router is None:
        raise HTTPException(status_code=503, detail="LLM router not ready")

    try:
        embedding = await llm_router.embed(req.text)
        return {"embedding": embedding}
    except Exception as e:
        logger.error("embed_error", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error processing request")
