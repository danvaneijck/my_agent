"""Tests for skills router endpoints."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException

from portal.routers.skills import (
    router,
    CreateSkillRequest,
    UpdateSkillRequest,
    RenderSkillRequest,
)


class TestSkillsRouterStructure:
    """Test cases for skills router structure and route definitions."""

    def test_router_prefix(self):
        """Test that router has correct prefix."""
        assert router.prefix == "/api/skills"

    def test_router_tags(self):
        """Test that router has correct tags."""
        assert "skills" in router.tags

    def test_route_count(self):
        """Test that all expected routes are defined."""
        routes = [route.path for route in router.routes]

        # CRUD routes
        assert "" in routes  # POST /api/skills (create)
        assert "" in routes  # GET /api/skills (list)
        assert "/{skill_id}" in routes  # GET /api/skills/{skill_id} (get)
        assert "/{skill_id}" in routes  # PUT /api/skills/{skill_id} (update)
        assert "/{skill_id}" in routes  # DELETE /api/skills/{skill_id} (delete)

        # Project skills routes
        assert "/projects/{project_id}/skills/{skill_id}" in routes  # POST (attach)
        assert "/projects/{project_id}/skills/{skill_id}" in routes  # DELETE (detach)
        assert "/projects/{project_id}" in routes  # GET (list project skills)

        # Task skills routes
        assert "/tasks/{task_id}/skills/{skill_id}" in routes  # POST (attach)
        assert "/tasks/{task_id}/skills/{skill_id}" in routes  # DELETE (detach)
        assert "/tasks/{task_id}" in routes  # GET (list task skills)

        # Template rendering
        assert "/{skill_id}/render" in routes  # POST (render template)

    def test_route_methods(self):
        """Test that routes have correct HTTP methods."""
        routes_by_method = {}
        for route in router.routes:
            for method in route.methods:
                routes_by_method.setdefault(method, []).append(route.path)

        # POST routes
        assert "" in routes_by_method.get("POST", [])
        assert "/projects/{project_id}/skills/{skill_id}" in routes_by_method.get("POST", [])
        assert "/tasks/{task_id}/skills/{skill_id}" in routes_by_method.get("POST", [])
        assert "/{skill_id}/render" in routes_by_method.get("POST", [])

        # GET routes
        assert "" in routes_by_method.get("GET", [])
        assert "/{skill_id}" in routes_by_method.get("GET", [])
        assert "/projects/{project_id}" in routes_by_method.get("GET", [])
        assert "/tasks/{task_id}" in routes_by_method.get("GET", [])

        # PUT routes
        assert "/{skill_id}" in routes_by_method.get("PUT", [])

        # DELETE routes
        assert "/{skill_id}" in routes_by_method.get("DELETE", [])
        assert "/projects/{project_id}/skills/{skill_id}" in routes_by_method.get("DELETE", [])
        assert "/tasks/{task_id}/skills/{skill_id}" in routes_by_method.get("DELETE", [])


class TestRequestModels:
    """Test request/response models."""

    def test_create_skill_request_required_fields(self):
        """Test CreateSkillRequest with required fields only."""
        request = CreateSkillRequest(
            name="test_skill",
            content="print('hello')",
        )
        assert request.name == "test_skill"
        assert request.content == "print('hello')"
        assert request.description is None
        assert request.category is None
        assert request.language is None
        assert request.tags is None
        assert request.is_template is False

    def test_create_skill_request_all_fields(self):
        """Test CreateSkillRequest with all fields."""
        request = CreateSkillRequest(
            name="test_skill",
            content="def {{func}}(): pass",
            description="A test skill",
            category="code",
            language="python",
            tags=["test", "example"],
            is_template=True,
        )
        assert request.name == "test_skill"
        assert request.content == "def {{func}}(): pass"
        assert request.description == "A test skill"
        assert request.category == "code"
        assert request.language == "python"
        assert request.tags == ["test", "example"]
        assert request.is_template is True

    def test_update_skill_request_all_optional(self):
        """Test UpdateSkillRequest with all fields optional."""
        request = UpdateSkillRequest()
        assert request.name is None
        assert request.content is None
        assert request.description is None
        assert request.category is None
        assert request.language is None
        assert request.tags is None
        assert request.is_template is None

    def test_update_skill_request_partial(self):
        """Test UpdateSkillRequest with partial updates."""
        request = UpdateSkillRequest(
            name="new_name",
            content="new content",
        )
        assert request.name == "new_name"
        assert request.content == "new content"
        assert request.description is None

    def test_render_skill_request(self):
        """Test RenderSkillRequest."""
        request = RenderSkillRequest(
            variables={"func": "hello_world"}
        )
        assert request.variables == {"func": "hello_world"}

    def test_render_skill_request_empty(self):
        """Test RenderSkillRequest with no variables."""
        request = RenderSkillRequest()
        assert request.variables is None


class TestRouteEndpointNames:
    """Test that endpoint functions have correct names and are importable."""

    def test_all_endpoints_defined(self):
        """Test that all expected endpoint functions exist."""
        from portal.routers import skills

        # CRUD endpoints
        assert hasattr(skills, "create_skill")
        assert hasattr(skills, "list_skills")
        assert hasattr(skills, "get_skill")
        assert hasattr(skills, "update_skill")
        assert hasattr(skills, "delete_skill")

        # Project skills endpoints
        assert hasattr(skills, "attach_skill_to_project")
        assert hasattr(skills, "detach_skill_from_project")
        assert hasattr(skills, "get_project_skills")

        # Task skills endpoints
        assert hasattr(skills, "attach_skill_to_task")
        assert hasattr(skills, "detach_skill_from_task")
        assert hasattr(skills, "get_task_skills")

        # Template rendering
        assert hasattr(skills, "render_skill")


class TestRouteParameterTypes:
    """Test route parameter types and validation."""

    def test_list_skills_query_params(self):
        """Test list_skills accepts optional query parameters."""
        from portal.routers.skills import list_skills
        import inspect

        sig = inspect.signature(list_skills)
        params = sig.parameters

        assert "category_filter" in params
        assert "tag_filter" in params
        assert "search_query" in params
        assert "user" in params

    def test_skill_id_path_params(self):
        """Test skill detail routes accept skill_id path parameter."""
        from portal.routers.skills import get_skill, update_skill, delete_skill
        import inspect

        for func in [get_skill, update_skill, delete_skill]:
            sig = inspect.signature(func)
            assert "skill_id" in sig.parameters

    def test_project_skill_path_params(self):
        """Test project skill routes accept both project_id and skill_id."""
        from portal.routers.skills import attach_skill_to_project, detach_skill_from_project
        import inspect

        for func in [attach_skill_to_project, detach_skill_from_project]:
            sig = inspect.signature(func)
            assert "project_id" in sig.parameters
            assert "skill_id" in sig.parameters

    def test_task_skill_path_params(self):
        """Test task skill routes accept both task_id and skill_id."""
        from portal.routers.skills import attach_skill_to_task, detach_skill_from_task
        import inspect

        for func in [attach_skill_to_task, detach_skill_from_task]:
            sig = inspect.signature(func)
            assert "task_id" in sig.parameters
            assert "skill_id" in sig.parameters


@pytest.mark.asyncio
class TestEndpointBehavior:
    """Test endpoint behavior with mocked dependencies."""

    async def test_create_skill_success(self):
        """Test successful skill creation."""
        from portal.routers.skills import create_skill
        from portal.auth import PortalUser
        import uuid

        mock_user = PortalUser(user_id=uuid.uuid4())
        request = CreateSkillRequest(
            name="test_skill",
            content="print('hello')",
        )

        with patch("portal.routers.skills.call_tool") as mock_call_tool:
            mock_call_tool.return_value = {
                "result": {
                    "skill_id": str(uuid.uuid4()),
                    "created_at": "2024-01-01T00:00:00Z"
                }
            }

            result = await create_skill(request, mock_user)

            assert "skill_id" in result
            assert "created_at" in result
            mock_call_tool.assert_called_once()
            call_args = mock_call_tool.call_args
            assert call_args[1]["module"] == "skills_modules"
            assert call_args[1]["tool_name"] == "skills_modules.create_skill"

    async def test_list_skills_success(self):
        """Test successful skill listing."""
        from portal.routers.skills import list_skills
        from portal.auth import PortalUser
        import uuid

        mock_user = PortalUser(user_id=uuid.uuid4())

        with patch("portal.routers.skills.call_tool") as mock_call_tool:
            mock_call_tool.return_value = {
                "result": {
                    "skills": [
                        {"id": "1", "name": "skill1"},
                        {"id": "2", "name": "skill2"},
                    ]
                }
            }

            result = await list_skills(None, None, None, mock_user)

            assert "skills" in result
            assert len(result["skills"]) == 2
            mock_call_tool.assert_called_once()

    async def test_get_skill_not_found(self):
        """Test getting a non-existent skill raises 404."""
        from portal.routers.skills import get_skill
        from portal.auth import PortalUser
        import uuid

        mock_user = PortalUser(user_id=uuid.uuid4())

        with patch("portal.routers.skills.call_tool") as mock_call_tool:
            mock_call_tool.side_effect = RuntimeError("Skill not found")

            with pytest.raises(HTTPException) as exc_info:
                await get_skill("nonexistent-id", mock_user)

            assert exc_info.value.status_code == 404

    async def test_update_skill_partial(self):
        """Test updating skill with partial data."""
        from portal.routers.skills import update_skill
        from portal.auth import PortalUser
        import uuid

        mock_user = PortalUser(user_id=uuid.uuid4())
        request = UpdateSkillRequest(name="new_name")

        with patch("portal.routers.skills.call_tool") as mock_call_tool:
            mock_call_tool.return_value = {
                "result": {
                    "success": True,
                    "updated_at": "2024-01-01T00:00:00Z"
                }
            }

            result = await update_skill("skill-id", request, mock_user)

            assert result["success"] is True
            call_args = mock_call_tool.call_args
            args = call_args[1]["arguments"]
            assert "name" in args
            assert "content" not in args  # Not provided in request

    async def test_attach_skill_to_project(self):
        """Test attaching skill to project."""
        from portal.routers.skills import attach_skill_to_project
        from portal.auth import PortalUser
        import uuid

        mock_user = PortalUser(user_id=uuid.uuid4())

        with patch("portal.routers.skills.call_tool") as mock_call_tool:
            mock_call_tool.return_value = {
                "result": {
                    "success": True,
                    "applied_at": "2024-01-01T00:00:00Z"
                }
            }

            result = await attach_skill_to_project("project-id", "skill-id", mock_user)

            assert result["success"] is True
            call_args = mock_call_tool.call_args
            args = call_args[1]["arguments"]
            assert args["project_id"] == "project-id"
            assert args["skill_id"] == "skill-id"


def test_router_importable_from_portal():
    """Test that router can be imported through portal package."""
    from portal.routers import skills
    assert skills.router is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
