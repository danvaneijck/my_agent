"""Skills module proxy endpoints."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from portal.auth import PortalUser, require_auth
from portal.services.module_client import call_tool

logger = structlog.get_logger()

router = APIRouter(prefix="/api/skills", tags=["skills"])


# ── Request/Response Models ────────────────────────────────────────


class CreateSkillRequest(BaseModel):
    name: str
    content: str
    description: str | None = None
    category: str | None = None
    language: str | None = None
    tags: list[str] | None = None
    is_template: bool = False


class UpdateSkillRequest(BaseModel):
    name: str | None = None
    content: str | None = None
    description: str | None = None
    category: str | None = None
    language: str | None = None
    tags: list[str] | None = None
    is_template: bool | None = None


class RenderSkillRequest(BaseModel):
    variables: dict[str, str] | None = None


# ── Skill CRUD Endpoints ───────────────────────────────────────────


@router.post("")
async def create_skill(
    request: CreateSkillRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Create a new skill."""
    try:
        result = await call_tool(
            module="skills_modules",
            tool_name="skills_modules.create_skill",
            arguments={
                "name": request.name,
                "content": request.content,
                "description": request.description,
                "category": request.category,
                "language": request.language,
                "tags": request.tags or [],
                "is_template": request.is_template,
            },
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("create_skill_failed", error=str(e), user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to create skill")


@router.get("")
async def list_skills(
    category_filter: str | None = Query(None),
    tag_filter: str | None = Query(None),
    search_query: str | None = Query(None),
    user: PortalUser = Depends(require_auth),
) -> dict:
    """List all skills for the user with optional filters."""
    try:
        result = await call_tool(
            module="skills_modules",
            tool_name="skills_modules.list_skills",
            arguments={
                "category_filter": category_filter,
                "tag_filter": tag_filter,
                "search_query": search_query,
            },
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("list_skills_failed", error=str(e), user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to list skills")


@router.get("/{skill_id}")
async def get_skill(
    skill_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get full details for a single skill."""
    try:
        result = await call_tool(
            module="skills_modules",
            tool_name="skills_modules.get_skill",
            arguments={"skill_id": skill_id},
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("get_skill_failed", error=str(e), skill_id=skill_id, user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to get skill")


@router.put("/{skill_id}")
async def update_skill(
    skill_id: str,
    request: UpdateSkillRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Update skill fields."""
    try:
        # Build arguments dict with only provided fields
        arguments = {"skill_id": skill_id}
        if request.name is not None:
            arguments["name"] = request.name
        if request.content is not None:
            arguments["content"] = request.content
        if request.description is not None:
            arguments["description"] = request.description
        if request.category is not None:
            arguments["category"] = request.category
        if request.language is not None:
            arguments["language"] = request.language
        if request.tags is not None:
            arguments["tags"] = request.tags
        if request.is_template is not None:
            arguments["is_template"] = request.is_template

        result = await call_tool(
            module="skills_modules",
            tool_name="skills_modules.update_skill",
            arguments=arguments,
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("update_skill_failed", error=str(e), skill_id=skill_id, user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to update skill")


@router.delete("/{skill_id}")
async def delete_skill(
    skill_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Delete a skill."""
    try:
        result = await call_tool(
            module="skills_modules",
            tool_name="skills_modules.delete_skill",
            arguments={"skill_id": skill_id},
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("delete_skill_failed", error=str(e), skill_id=skill_id, user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to delete skill")


# ── Project Skill Endpoints ────────────────────────────────────────


@router.post("/projects/{project_id}/skills/{skill_id}")
async def attach_skill_to_project(
    project_id: str,
    skill_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Attach a skill to a project."""
    try:
        result = await call_tool(
            module="skills_modules",
            tool_name="skills_modules.attach_skill_to_project",
            arguments={
                "project_id": project_id,
                "skill_id": skill_id,
            },
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("attach_skill_to_project_failed", error=str(e),
                    project_id=project_id, skill_id=skill_id, user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to attach skill to project")


@router.delete("/projects/{project_id}/skills/{skill_id}")
async def detach_skill_from_project(
    project_id: str,
    skill_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Detach a skill from a project."""
    try:
        result = await call_tool(
            module="skills_modules",
            tool_name="skills_modules.detach_skill_from_project",
            arguments={
                "project_id": project_id,
                "skill_id": skill_id,
            },
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("detach_skill_from_project_failed", error=str(e),
                    project_id=project_id, skill_id=skill_id, user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to detach skill from project")


@router.get("/projects/{project_id}")
async def get_project_skills(
    project_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get all skills attached to a project."""
    try:
        result = await call_tool(
            module="skills_modules",
            tool_name="skills_modules.get_project_skills",
            arguments={"project_id": project_id},
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("get_project_skills_failed", error=str(e),
                    project_id=project_id, user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to get project skills")


# ── Task Skill Endpoints ───────────────────────────────────────────


@router.post("/tasks/{task_id}/skills/{skill_id}")
async def attach_skill_to_task(
    task_id: str,
    skill_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Attach a skill to a task."""
    try:
        result = await call_tool(
            module="skills_modules",
            tool_name="skills_modules.attach_skill_to_task",
            arguments={
                "task_id": task_id,
                "skill_id": skill_id,
            },
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("attach_skill_to_task_failed", error=str(e),
                    task_id=task_id, skill_id=skill_id, user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to attach skill to task")


@router.delete("/tasks/{task_id}/skills/{skill_id}")
async def detach_skill_from_task(
    task_id: str,
    skill_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Detach a skill from a task."""
    try:
        result = await call_tool(
            module="skills_modules",
            tool_name="skills_modules.detach_skill_from_task",
            arguments={
                "task_id": task_id,
                "skill_id": skill_id,
            },
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("detach_skill_from_task_failed", error=str(e),
                    task_id=task_id, skill_id=skill_id, user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to detach skill from task")


@router.get("/tasks/{task_id}")
async def get_task_skills(
    task_id: str,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Get all skills attached to a task."""
    try:
        result = await call_tool(
            module="skills_modules",
            tool_name="skills_modules.get_task_skills",
            arguments={"task_id": task_id},
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("get_task_skills_failed", error=str(e),
                    task_id=task_id, user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to get task skills")


# ── Template Rendering Endpoint ────────────────────────────────────


@router.post("/{skill_id}/render")
async def render_skill(
    skill_id: str,
    request: RenderSkillRequest,
    user: PortalUser = Depends(require_auth),
) -> dict:
    """Render a template skill with variable substitution."""
    try:
        result = await call_tool(
            module="skills_modules",
            tool_name="skills_modules.render_skill",
            arguments={
                "skill_id": skill_id,
                "variables": request.variables or {},
            },
            user_id=str(user.user_id),
        )
        return result.get("result", {})
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("render_skill_failed", error=str(e), skill_id=skill_id, user_id=str(user.user_id))
        raise HTTPException(status_code=500, detail="Failed to render skill")
