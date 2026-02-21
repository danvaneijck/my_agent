"""Knowledge module proxy endpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from portal.auth import PortalUser, require_auth
from portal.services.module_client import call_tool

logger = structlog.get_logger()

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


# ── Request Models ────────────────────────────────────────────────


class CreateMemoryRequest(BaseModel):
    content: str


class RecallRequest(BaseModel):
    query: str
    max_results: int = 5


# ── Endpoints ─────────────────────────────────────────────────────


@router.get("")
async def list_memories(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List all stored memories for the authenticated user, most recent first."""
    try:
        result = await call_tool(
            module="knowledge",
            tool_name="knowledge.list_memories",
            arguments={"limit": limit, "offset": offset},
            user_id=str(user.user_id),
        )
        memories = result.get("result", [])
        return {"memories": memories, "count": len(memories)}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("list_memories_failed", error=str(e), user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to list memories")


@router.post("")
async def remember(
    request: CreateMemoryRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Store a new memory/fact for the authenticated user."""
    try:
        result = await call_tool(
            module="knowledge",
            tool_name="knowledge.remember",
            arguments={"content": request.content},
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("remember_failed", error=str(e), user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to store memory")


@router.post("/recall")
async def recall(
    request: RecallRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Semantic search over the user's stored memories."""
    try:
        result = await call_tool(
            module="knowledge",
            tool_name="knowledge.recall",
            arguments={"query": request.query, "max_results": request.max_results},
            user_id=str(user.user_id),
        )
        memories = result.get("result", [])
        return {"memories": memories, "count": len(memories)}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("recall_failed", error=str(e), user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to recall memories")


@router.delete("/{memory_id}")
async def forget(
    memory_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Delete a specific memory by ID. Only deletes memories owned by the authenticated user."""
    try:
        result = await call_tool(
            module="knowledge",
            tool_name="knowledge.forget",
            arguments={"memory_id": memory_id},
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("forget_failed", error=str(e), memory_id=memory_id, user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to delete memory")
