"""Add projects, project_phases, and project_tasks tables.

Revision ID: 009
Revises: 008
Create Date: 2026-02-15
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Projects table
    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("design_document", sa.Text(), nullable=True),
        sa.Column("repo_owner", sa.String(), nullable=True),
        sa.Column("repo_name", sa.String(), nullable=True),
        sa.Column("default_branch", sa.String(), nullable=False, server_default="main"),
        sa.Column("auto_merge", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(), nullable=False, server_default="planning"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint("uq_user_project_name", "projects", ["user_id", "name"])
    op.create_index("ix_projects_user_status", "projects", ["user_id", "status"])

    # Project phases table
    op.create_table(
        "project_phases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id", sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="planned"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_project_phases_project", "project_phases", ["project_id", "order_index"])

    # Project tasks table
    op.create_table(
        "project_tasks",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "phase_id", sa.Uuid(),
            sa.ForeignKey("project_phases.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "project_id", sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("acceptance_criteria", sa.Text(), nullable=True),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="todo"),
        sa.Column("branch_name", sa.String(), nullable=True),
        sa.Column("pr_number", sa.Integer(), nullable=True),
        sa.Column("issue_number", sa.Integer(), nullable=True),
        sa.Column("claude_task_id", sa.String(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_project_tasks_phase", "project_tasks", ["phase_id", "order_index"])
    op.create_index("ix_project_tasks_project_status", "project_tasks", ["project_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_project_tasks_project_status")
    op.drop_index("ix_project_tasks_phase")
    op.drop_table("project_tasks")

    op.drop_index("ix_project_phases_project")
    op.drop_table("project_phases")

    op.drop_index("ix_projects_user_status")
    op.drop_constraint("uq_user_project_name", "projects")
    op.drop_table("projects")
