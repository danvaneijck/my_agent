"""Add crew_sessions, crew_members, crew_context_entries tables and
depends_on column to project_tasks.

Revision ID: 021
Revises: 020
Create Date: 2026-02-23
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- crew_sessions ---
    op.create_table(
        "crew_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="configuring"),
        sa.Column("max_agents", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("repo_url", sa.String(), nullable=True),
        sa.Column("integration_branch", sa.String(), nullable=False, server_default="crew/integration"),
        sa.Column("source_branch", sa.String(), nullable=False, server_default="main"),
        sa.Column("current_wave", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_waves", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("workflow_id", sa.Uuid(), nullable=True),
        sa.Column("config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crew_sessions_user_status", "crew_sessions", ["user_id", "status"])

    # --- crew_members ---
    op.create_table(
        "crew_members",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(), nullable=True),
        sa.Column("branch_name", sa.String(), nullable=False),
        sa.Column("claude_task_id", sa.String(), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("task_title", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="idle"),
        sa.Column("wave_number", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["session_id"], ["crew_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["task_id"], ["project_tasks.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crew_members_session", "crew_members", ["session_id"])

    # --- crew_context_entries ---
    op.create_table(
        "crew_context_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=True),
        sa.Column("entry_type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.ForeignKeyConstraint(["session_id"], ["crew_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["member_id"], ["crew_members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_crew_context_entries_session", "crew_context_entries", ["session_id"])

    # --- Add depends_on to project_tasks ---
    op.add_column("project_tasks", sa.Column("depends_on", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("project_tasks", "depends_on")
    op.drop_index("ix_crew_context_entries_session", table_name="crew_context_entries")
    op.drop_table("crew_context_entries")
    op.drop_index("ix_crew_members_session", table_name="crew_members")
    op.drop_table("crew_members")
    op.drop_index("ix_crew_sessions_user_status", table_name="crew_sessions")
    op.drop_table("crew_sessions")
