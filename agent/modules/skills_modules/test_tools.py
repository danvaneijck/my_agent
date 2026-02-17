#!/usr/bin/env python3
"""Comprehensive test suite for the skills_modules module.

Tests cover:
1. End-to-end skill lifecycle (CRUD operations)
2. Template rendering with Jinja2 variables
3. Permission boundaries and user isolation
4. Attachment/detachment to projects and tasks
5. Error handling and edge cases

Usage:
    cd agent
    python -m pytest modules/skills_modules/test_tools.py -v

    Or run with coverage:
    python -m pytest modules/skills_modules/test_tools.py --cov=modules.skills_modules -v
"""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Ensure imports work when running outside Docker
_agent_dir = os.path.dirname(os.path.abspath(__file__))
_agent_dir = os.path.abspath(os.path.join(_agent_dir, "..", ".."))
if _agent_dir not in sys.path:
    sys.path.insert(0, _agent_dir)
_shared_dir = os.path.join(_agent_dir, "shared")
if _shared_dir not in sys.path:
    sys.path.insert(0, _shared_dir)

from modules.skills_modules.tools import SkillsTools
from shared.database import get_session_factory
from shared.models.project import Project
from shared.models.project_phase import ProjectPhase
from shared.models.project_skill import ProjectSkill
from shared.models.project_task import ProjectTask
from shared.models.task_skill import TaskSkill
from shared.models.user import User
from shared.models.user_skill import UserSkill


# Test fixtures
@pytest.fixture
async def db_session():
    """Create a test database session."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        yield session


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        permission_level="user",
        token_budget_monthly=10000,
        tokens_used_this_month=0,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_user_2(db_session: AsyncSession):
    """Create a second test user for isolation tests."""
    user = User(
        id=uuid.uuid4(),
        permission_level="user",
        token_budget_monthly=10000,
        tokens_used_this_month=0,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_project(db_session: AsyncSession, test_user: User):
    """Create a test project."""
    project = Project(
        id=uuid.uuid4(),
        user_id=test_user.id,
        name=f"test_project_{uuid.uuid4().hex[:8]}",
        description="Test project for skills",
        status="active",
    )
    db_session.add(project)
    await db_session.commit()
    await db_session.refresh(project)
    return project


@pytest.fixture
async def test_task(db_session: AsyncSession, test_user: User, test_project: Project):
    """Create a test task."""
    # Create a phase first
    phase = ProjectPhase(
        id=uuid.uuid4(),
        project_id=test_project.id,
        name="Test Phase",
        order_index=0,
        status="in_progress",
    )
    db_session.add(phase)
    await db_session.commit()
    await db_session.refresh(phase)

    # Create task
    task = ProjectTask(
        id=uuid.uuid4(),
        project_id=test_project.id,
        phase_id=phase.id,
        user_id=test_user.id,
        title="Test Task",
        status="todo",
        order_index=0,
    )
    db_session.add(task)
    await db_session.commit()
    await db_session.refresh(task)
    return task


@pytest.fixture
def tools():
    """Create SkillsTools instance."""
    return SkillsTools()


# Test 1: End-to-End Skill Lifecycle
class TestSkillLifecycle:
    """Test complete CRUD workflow for skills."""

    @pytest.mark.asyncio
    async def test_create_skill(self, tools: SkillsTools, test_user: User):
        """Test creating a new skill."""
        result = await tools.create_skill(
            name="test_api_client",
            content="import requests\n\nclass APIClient:\n    pass",
            user_id=str(test_user.id),
            description="Test API client",
            category="code",
            language="python",
            tags=["api", "http"],
            is_template=False,
        )

        assert result["success"] is True
        assert "skill_id" in result
        assert result["name"] == "test_api_client"
        assert result["category"] == "code"
        assert result["tags"] == ["api", "http"]

    @pytest.mark.asyncio
    async def test_list_skills(self, tools: SkillsTools, test_user: User):
        """Test listing all skills for a user."""
        # Create two skills
        await tools.create_skill(
            name="skill_one",
            content="print('one')",
            user_id=str(test_user.id),
            category="code",
        )
        await tools.create_skill(
            name="skill_two",
            content="print('two')",
            user_id=str(test_user.id),
            category="config",
        )

        result = await tools.list_skills(user_id=str(test_user.id))
        assert result["success"] is True
        assert result["count"] >= 2
        assert len(result["skills"]) >= 2

    @pytest.mark.asyncio
    async def test_get_skill(self, tools: SkillsTools, test_user: User):
        """Test getting a single skill by ID."""
        create_result = await tools.create_skill(
            name="test_skill",
            content="# Test content",
            user_id=str(test_user.id),
        )
        skill_id = create_result["skill_id"]

        result = await tools.get_skill(
            skill_id=skill_id,
            user_id=str(test_user.id),
        )

        assert result["success"] is True
        assert result["skill"]["skill_id"] == skill_id
        assert result["skill"]["name"] == "test_skill"
        assert result["skill"]["content"] == "# Test content"

    @pytest.mark.asyncio
    async def test_update_skill(self, tools: SkillsTools, test_user: User):
        """Test updating a skill."""
        create_result = await tools.create_skill(
            name="update_test",
            content="original content",
            user_id=str(test_user.id),
            description="original description",
        )
        skill_id = create_result["skill_id"]

        result = await tools.update_skill(
            skill_id=skill_id,
            user_id=str(test_user.id),
            description="updated description",
            content="updated content",
            tags=["updated"],
        )

        assert result["success"] is True
        assert "updated_at" in result

        # Verify changes
        get_result = await tools.get_skill(skill_id=skill_id, user_id=str(test_user.id))
        assert get_result["skill"]["description"] == "updated description"
        assert get_result["skill"]["content"] == "updated content"
        assert get_result["skill"]["tags"] == ["updated"]

    @pytest.mark.asyncio
    async def test_delete_skill(self, tools: SkillsTools, test_user: User, db_session: AsyncSession):
        """Test deleting a skill."""
        create_result = await tools.create_skill(
            name="delete_test",
            content="to be deleted",
            user_id=str(test_user.id),
        )
        skill_id = create_result["skill_id"]

        result = await tools.delete_skill(
            skill_id=skill_id,
            user_id=str(test_user.id),
        )

        assert result["success"] is True

        # Verify deletion from database
        stmt = select(UserSkill).where(UserSkill.id == uuid.UUID(skill_id))
        result = await db_session.execute(stmt)
        deleted_skill = result.scalar_one_or_none()
        assert deleted_skill is None


# Test 2: Template Rendering
class TestTemplateRendering:
    """Test Jinja2 template rendering functionality."""

    @pytest.mark.asyncio
    async def test_create_template_skill(self, tools: SkillsTools, test_user: User):
        """Test creating a template skill."""
        result = await tools.create_skill(
            name="test_function_template",
            content="def test_{{function_name}}():\n    assert {{expected}} == True",
            user_id=str(test_user.id),
            is_template=True,
            category="template",
        )

        assert result["success"] is True
        assert result["is_template"] is True

    @pytest.mark.asyncio
    async def test_render_template(self, tools: SkillsTools, test_user: User):
        """Test rendering a template with variables."""
        create_result = await tools.create_skill(
            name="render_test_template",
            content="Hello {{name}}, you are {{age}} years old!",
            user_id=str(test_user.id),
            is_template=True,
        )
        skill_id = create_result["skill_id"]

        result = await tools.render_skill(
            skill_id=skill_id,
            user_id=str(test_user.id),
            variables={"name": "Alice", "age": 30},
        )

        assert result["success"] is True
        assert result["rendered"] == "Hello Alice, you are 30 years old!"

    @pytest.mark.asyncio
    async def test_render_complex_template(self, tools: SkillsTools, test_user: User):
        """Test rendering a complex code template."""
        template_content = """def test_{{function_name}}():
    \"\"\"Test {{description}}\"\"\"
    # Arrange
    {{arrange_code}}

    # Act
    result = {{function_call}}

    # Assert
    assert result == {{expected_result}}"""

        create_result = await tools.create_skill(
            name="complex_template",
            content=template_content,
            user_id=str(test_user.id),
            is_template=True,
            language="python",
        )
        skill_id = create_result["skill_id"]

        result = await tools.render_skill(
            skill_id=skill_id,
            user_id=str(test_user.id),
            variables={
                "function_name": "user_login",
                "description": "user login functionality",
                "arrange_code": 'user = User(username="test")',
                "function_call": "user.login()",
                "expected_result": "True",
            },
        )

        assert result["success"] is True
        assert "def test_user_login():" in result["rendered"]
        assert "user login functionality" in result["rendered"]
        assert "user.login()" in result["rendered"]

    @pytest.mark.asyncio
    async def test_render_non_template_skill(self, tools: SkillsTools, test_user: User):
        """Test that non-template skills cannot be rendered."""
        create_result = await tools.create_skill(
            name="non_template",
            content="static content",
            user_id=str(test_user.id),
            is_template=False,
        )
        skill_id = create_result["skill_id"]

        result = await tools.render_skill(
            skill_id=skill_id,
            user_id=str(test_user.id),
            variables={"test": "value"},
        )

        assert result["success"] is False
        assert "not a template" in result.get("error", "").lower()


# Test 3: Permission Boundaries
class TestPermissionBoundaries:
    """Test user isolation and permission enforcement."""

    @pytest.mark.asyncio
    async def test_user_cannot_access_other_users_skill(
        self, tools: SkillsTools, test_user: User, test_user_2: User
    ):
        """Test that users cannot access skills created by other users."""
        # User 1 creates a skill
        create_result = await tools.create_skill(
            name="user1_skill",
            content="private content",
            user_id=str(test_user.id),
        )
        skill_id = create_result["skill_id"]

        # User 2 tries to access it
        result = await tools.get_skill(
            skill_id=skill_id,
            user_id=str(test_user_2.id),
        )

        assert result["success"] is False
        assert "not found" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_user_cannot_update_other_users_skill(
        self, tools: SkillsTools, test_user: User, test_user_2: User
    ):
        """Test that users cannot update skills created by other users."""
        # User 1 creates a skill
        create_result = await tools.create_skill(
            name="user1_update_test",
            content="original",
            user_id=str(test_user.id),
        )
        skill_id = create_result["skill_id"]

        # User 2 tries to update it
        result = await tools.update_skill(
            skill_id=skill_id,
            user_id=str(test_user_2.id),
            content="malicious update",
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_user_cannot_delete_other_users_skill(
        self, tools: SkillsTools, test_user: User, test_user_2: User
    ):
        """Test that users cannot delete skills created by other users."""
        # User 1 creates a skill
        create_result = await tools.create_skill(
            name="user1_delete_test",
            content="protected",
            user_id=str(test_user.id),
        )
        skill_id = create_result["skill_id"]

        # User 2 tries to delete it
        result = await tools.delete_skill(
            skill_id=skill_id,
            user_id=str(test_user_2.id),
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_list_skills_shows_only_user_skills(
        self, tools: SkillsTools, test_user: User, test_user_2: User
    ):
        """Test that list_skills only returns the requesting user's skills."""
        # User 1 creates a skill
        await tools.create_skill(
            name="user1_list_test",
            content="user1 content",
            user_id=str(test_user.id),
        )

        # User 2 creates a skill
        await tools.create_skill(
            name="user2_list_test",
            content="user2 content",
            user_id=str(test_user_2.id),
        )

        # User 1 lists skills
        result1 = await tools.list_skills(user_id=str(test_user.id))
        skill_names_1 = [s["name"] for s in result1["skills"]]

        # User 2 lists skills
        result2 = await tools.list_skills(user_id=str(test_user_2.id))
        skill_names_2 = [s["name"] for s in result2["skills"]]

        # User 1 should see their skill but not User 2's
        assert "user1_list_test" in skill_names_1
        assert "user2_list_test" not in skill_names_1

        # User 2 should see their skill but not User 1's
        assert "user2_list_test" in skill_names_2
        assert "user1_list_test" not in skill_names_2


# Test 4: Project and Task Attachments
class TestAttachments:
    """Test attaching and detaching skills to projects and tasks."""

    @pytest.mark.asyncio
    async def test_attach_skill_to_project(
        self, tools: SkillsTools, test_user: User, test_project: Project
    ):
        """Test attaching a skill to a project."""
        # Create a skill
        create_result = await tools.create_skill(
            name="project_skill",
            content="skill for project",
            user_id=str(test_user.id),
        )
        skill_id = create_result["skill_id"]

        # Attach to project
        result = await tools.attach_skill_to_project(
            project_id=str(test_project.id),
            skill_id=skill_id,
            user_id=str(test_user.id),
        )

        assert result["success"] is True
        assert "applied_at" in result

    @pytest.mark.asyncio
    async def test_get_project_skills(
        self, tools: SkillsTools, test_user: User, test_project: Project
    ):
        """Test retrieving skills attached to a project."""
        # Create and attach a skill
        create_result = await tools.create_skill(
            name="project_skill_get",
            content="test content",
            user_id=str(test_user.id),
        )
        skill_id = create_result["skill_id"]

        await tools.attach_skill_to_project(
            project_id=str(test_project.id),
            skill_id=skill_id,
            user_id=str(test_user.id),
        )

        # Get project skills
        result = await tools.get_project_skills(
            project_id=str(test_project.id),
            user_id=str(test_user.id),
        )

        assert result["success"] is True
        assert result["count"] >= 1
        skill_names = [s["skill"]["name"] for s in result["skills"]]
        assert "project_skill_get" in skill_names

    @pytest.mark.asyncio
    async def test_detach_skill_from_project(
        self, tools: SkillsTools, test_user: User, test_project: Project, db_session: AsyncSession
    ):
        """Test detaching a skill from a project."""
        # Create and attach a skill
        create_result = await tools.create_skill(
            name="project_skill_detach",
            content="test content",
            user_id=str(test_user.id),
        )
        skill_id = create_result["skill_id"]

        await tools.attach_skill_to_project(
            project_id=str(test_project.id),
            skill_id=skill_id,
            user_id=str(test_user.id),
        )

        # Detach
        result = await tools.detach_skill_from_project(
            project_id=str(test_project.id),
            skill_id=skill_id,
            user_id=str(test_user.id),
        )

        assert result["success"] is True

        # Verify removal from database
        stmt = select(ProjectSkill).where(
            ProjectSkill.project_id == test_project.id,
            ProjectSkill.skill_id == uuid.UUID(skill_id),
        )
        result = await db_session.execute(stmt)
        junction = result.scalar_one_or_none()
        assert junction is None

    @pytest.mark.asyncio
    async def test_attach_skill_to_task(
        self, tools: SkillsTools, test_user: User, test_task: ProjectTask
    ):
        """Test attaching a skill to a task."""
        # Create a skill
        create_result = await tools.create_skill(
            name="task_skill",
            content="skill for task",
            user_id=str(test_user.id),
        )
        skill_id = create_result["skill_id"]

        # Attach to task
        result = await tools.attach_skill_to_task(
            task_id=str(test_task.id),
            skill_id=skill_id,
            user_id=str(test_user.id),
        )

        assert result["success"] is True
        assert "applied_at" in result

    @pytest.mark.asyncio
    async def test_get_task_skills(
        self, tools: SkillsTools, test_user: User, test_task: ProjectTask
    ):
        """Test retrieving skills attached to a task."""
        # Create and attach a skill
        create_result = await tools.create_skill(
            name="task_skill_get",
            content="test content",
            user_id=str(test_user.id),
        )
        skill_id = create_result["skill_id"]

        await tools.attach_skill_to_task(
            task_id=str(test_task.id),
            skill_id=skill_id,
            user_id=str(test_user.id),
        )

        # Get task skills
        result = await tools.get_task_skills(
            task_id=str(test_task.id),
            user_id=str(test_user.id),
        )

        assert result["success"] is True
        assert result["count"] >= 1
        skill_names = [s["skill"]["name"] for s in result["skills"]]
        assert "task_skill_get" in skill_names

    @pytest.mark.asyncio
    async def test_detach_skill_from_task(
        self, tools: SkillsTools, test_user: User, test_task: ProjectTask, db_session: AsyncSession
    ):
        """Test detaching a skill from a task."""
        # Create and attach a skill
        create_result = await tools.create_skill(
            name="task_skill_detach",
            content="test content",
            user_id=str(test_user.id),
        )
        skill_id = create_result["skill_id"]

        await tools.attach_skill_to_task(
            task_id=str(test_task.id),
            skill_id=skill_id,
            user_id=str(test_user.id),
        )

        # Detach
        result = await tools.detach_skill_from_task(
            task_id=str(test_task.id),
            skill_id=skill_id,
            user_id=str(test_user.id),
        )

        assert result["success"] is True

        # Verify removal from database
        stmt = select(TaskSkill).where(
            TaskSkill.task_id == test_task.id,
            TaskSkill.skill_id == uuid.UUID(skill_id),
        )
        result = await db_session.execute(stmt)
        junction = result.scalar_one_or_none()
        assert junction is None


# Test 5: Error Handling and Edge Cases
class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_create_duplicate_skill_name(self, tools: SkillsTools, test_user: User):
        """Test that duplicate skill names are rejected."""
        name = f"duplicate_skill_{uuid.uuid4().hex[:8]}"

        # Create first skill
        result1 = await tools.create_skill(
            name=name,
            content="first",
            user_id=str(test_user.id),
        )
        assert result1["success"] is True

        # Try to create duplicate
        result2 = await tools.create_skill(
            name=name,
            content="second",
            user_id=str(test_user.id),
        )
        assert result2["success"] is False
        assert "already exists" in result2.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_get_nonexistent_skill(self, tools: SkillsTools, test_user: User):
        """Test getting a skill that doesn't exist."""
        fake_id = str(uuid.uuid4())
        result = await tools.get_skill(
            skill_id=fake_id,
            user_id=str(test_user.id),
        )

        assert result["success"] is False
        assert "not found" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_update_nonexistent_skill(self, tools: SkillsTools, test_user: User):
        """Test updating a skill that doesn't exist."""
        fake_id = str(uuid.uuid4())
        result = await tools.update_skill(
            skill_id=fake_id,
            user_id=str(test_user.id),
            content="updated",
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent_skill(self, tools: SkillsTools, test_user: User):
        """Test deleting a skill that doesn't exist."""
        fake_id = str(uuid.uuid4())
        result = await tools.delete_skill(
            skill_id=fake_id,
            user_id=str(test_user.id),
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_attach_nonexistent_skill_to_project(
        self, tools: SkillsTools, test_user: User, test_project: Project
    ):
        """Test attaching a non-existent skill to a project."""
        fake_id = str(uuid.uuid4())
        result = await tools.attach_skill_to_project(
            project_id=str(test_project.id),
            skill_id=fake_id,
            user_id=str(test_user.id),
        )

        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_delete_skill_cascades_to_attachments(
        self, tools: SkillsTools, test_user: User, test_project: Project, db_session: AsyncSession
    ):
        """Test that deleting a skill removes all attachments via CASCADE."""
        # Create skill and attach to project
        create_result = await tools.create_skill(
            name="cascade_test",
            content="will be deleted",
            user_id=str(test_user.id),
        )
        skill_id = create_result["skill_id"]

        await tools.attach_skill_to_project(
            project_id=str(test_project.id),
            skill_id=skill_id,
            user_id=str(test_user.id),
        )

        # Delete skill
        await tools.delete_skill(
            skill_id=skill_id,
            user_id=str(test_user.id),
        )

        # Verify attachment is also deleted (CASCADE)
        stmt = select(ProjectSkill).where(ProjectSkill.skill_id == uuid.UUID(skill_id))
        result = await db_session.execute(stmt)
        attachments = result.scalars().all()
        assert len(attachments) == 0

    @pytest.mark.asyncio
    async def test_filter_by_category(self, tools: SkillsTools, test_user: User):
        """Test filtering skills by category."""
        # Create skills in different categories
        await tools.create_skill(
            name="code_skill",
            content="code",
            user_id=str(test_user.id),
            category="code",
        )
        await tools.create_skill(
            name="config_skill",
            content="config",
            user_id=str(test_user.id),
            category="config",
        )

        # Filter by category
        result = await tools.list_skills(
            user_id=str(test_user.id),
            category_filter="code",
        )

        assert result["success"] is True
        categories = [s["category"] for s in result["skills"]]
        assert all(cat == "code" for cat in categories)

    @pytest.mark.asyncio
    async def test_search_skills(self, tools: SkillsTools, test_user: User):
        """Test searching skills by name/description."""
        # Create skills with distinct names
        await tools.create_skill(
            name="unique_searchable_skill",
            content="test",
            user_id=str(test_user.id),
            description="This is searchable",
        )
        await tools.create_skill(
            name="other_skill",
            content="test",
            user_id=str(test_user.id),
            description="Different content",
        )

        # Search
        result = await tools.list_skills(
            user_id=str(test_user.id),
            search_query="searchable",
        )

        assert result["success"] is True
        assert result["count"] >= 1
        names = [s["name"] for s in result["skills"]]
        assert "unique_searchable_skill" in names


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
