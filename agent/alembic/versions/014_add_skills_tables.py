"""Add user_skills, project_skills, and task_skills tables.

Revision ID: 014
Revises: 013
Create Date: 2026-02-17
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # User skills table
    op.create_table(
        "user_skills",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id", sa.Uuid(),
            sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("tags", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("is_template", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint("uq_user_skill_name", "user_skills", ["user_id", "name"])
    op.create_index("idx_user_skills_user_id", "user_skills", ["user_id"])
    op.create_index("idx_user_skills_category", "user_skills", ["category"])

    # Project skills junction table
    op.create_table(
        "project_skills",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "project_id", sa.Uuid(),
            sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "skill_id", sa.Uuid(),
            sa.ForeignKey("user_skills.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "applied_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint("uq_project_skill", "project_skills", ["project_id", "skill_id"])
    op.create_index("idx_project_skills_project_id", "project_skills", ["project_id"])
    op.create_index("idx_project_skills_skill_id", "project_skills", ["skill_id"])

    # Task skills junction table
    op.create_table(
        "task_skills",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "task_id", sa.Uuid(),
            sa.ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column(
            "skill_id", sa.Uuid(),
            sa.ForeignKey("user_skills.id", ondelete="CASCADE"), nullable=False,
        ),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "applied_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint("uq_task_skill", "task_skills", ["task_id", "skill_id"])
    op.create_index("idx_task_skills_task_id", "task_skills", ["task_id"])
    op.create_index("idx_task_skills_skill_id", "task_skills", ["skill_id"])


def downgrade() -> None:
    # Drop task skills table
    op.drop_index("idx_task_skills_skill_id")
    op.drop_index("idx_task_skills_task_id")
    op.drop_constraint("uq_task_skill", "task_skills")
    op.drop_table("task_skills")

    # Drop project skills table
    op.drop_index("idx_project_skills_skill_id")
    op.drop_index("idx_project_skills_project_id")
    op.drop_constraint("uq_project_skill", "project_skills")
    op.drop_table("project_skills")

    # Drop user skills table
    op.drop_index("idx_user_skills_category")
    op.drop_index("idx_user_skills_user_id")
    op.drop_constraint("uq_user_skill_name", "user_skills")
    op.drop_table("user_skills")
