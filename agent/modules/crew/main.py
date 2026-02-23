"""Crew module — multi-agent collaboration via coordinated Claude Code sessions."""

from fastapi import FastAPI
from modules.crew.manifest import MANIFEST
from modules.crew.tools import CrewTools
from shared.schemas.tools import ModuleManifest, ToolCall, ToolResult
from shared.schemas.common import HealthResponse

app = FastAPI(title="Crew Module")
tools: CrewTools | None = None


@app.on_event("startup")
async def startup():
    global tools
    tools = CrewTools()


@app.get("/manifest", response_model=ModuleManifest)
async def manifest():
    return MANIFEST


@app.post("/execute", response_model=ToolResult)
async def execute(call: ToolCall):
    if tools is None:
        return ToolResult(
            tool_name=call.tool_name, success=False, error="Module not ready"
        )
    try:
        tool_name = call.tool_name.split(".")[-1]
        args = dict(call.arguments)
        if call.user_id:
            args["user_id"] = call.user_id

        # Inject platform context if provided (scheduler integration)
        platform = args.pop("platform", "web")
        platform_channel_id = args.pop("platform_channel_id", None)
        platform_thread_id = args.pop("platform_thread_id", None)
        platform_server_id = args.pop("platform_server_id", None)
        conversation_id = args.pop("conversation_id", None)

        # Tools that need platform context for scheduler job creation
        if tool_name in ("start_session", "resume_session", "advance_session"):
            args["platform"] = platform
            args["platform_channel_id"] = platform_channel_id

        if tool_name == "create_session":
            result = await tools.create_session(**args)
        elif tool_name == "start_session":
            result = await tools.start_session(**args)
        elif tool_name == "get_session":
            result = await tools.get_session(**args)
        elif tool_name == "list_sessions":
            result = await tools.list_sessions(**args)
        elif tool_name == "pause_session":
            result = await tools.pause_session(**args)
        elif tool_name == "resume_session":
            result = await tools.resume_session(**args)
        elif tool_name == "cancel_session":
            result = await tools.cancel_session(**args)
        elif tool_name == "post_context":
            result = await tools.post_context(**args)
        elif tool_name == "get_context_board":
            result = await tools.get_context_board(**args)
        elif tool_name == "advance_session":
            result = await tools.advance_session(**args)
        else:
            return ToolResult(
                tool_name=call.tool_name,
                success=False,
                error=f"Unknown tool: {call.tool_name}",
            )

        return ToolResult(tool_name=call.tool_name, success=True, result=result)
    except Exception as e:
        return ToolResult(tool_name=call.tool_name, success=False, error=str(e))


@app.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="ok")
