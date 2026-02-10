"""Add scheduled_jobs table.

Revision ID: 002
Revises: 001
Create Date: 2026-02-10
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("platform_channel_id", sa.String(), nullable=False),
        sa.Column("platform_thread_id", sa.String(), nullable=True),
        sa.Column("job_type", sa.String(), nullable=False),
        sa.Column("check_config", sa.JSON(), nullable=False),
        sa.Column("interval_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("on_success_message", sa.Text(), nullable=False),
        sa.Column("on_failure_message", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_scheduled_jobs_status_next_run", "scheduled_jobs", ["status", "next_run_at"])


def downgrade() -> None:
    op.drop_index("ix_scheduled_jobs_status_next_run", table_name="scheduled_jobs")
    op.drop_table("scheduled_jobs")
