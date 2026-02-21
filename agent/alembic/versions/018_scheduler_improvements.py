"""Scheduler improvements: new columns on scheduled_jobs and scheduled_workflows table.

Revision ID: 018
Revises: 017
Create Date: 2026-02-21
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- scheduled_workflows table (new) ---
    op.create_table(
        "scheduled_workflows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("platform_channel_id", sa.String(), nullable=False),
        sa.Column("platform_thread_id", sa.String(), nullable=True),
        sa.Column("platform_server_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    # --- scheduled_jobs: new columns ---
    op.add_column("scheduled_jobs", sa.Column("name", sa.String(), nullable=True))
    op.add_column("scheduled_jobs", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "scheduled_jobs",
        sa.Column(
            "consecutive_failures",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "scheduled_jobs",
        sa.Column("runs_completed", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("scheduled_jobs", sa.Column("max_runs", sa.Integer(), nullable=True))
    op.add_column(
        "scheduled_jobs",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "scheduled_jobs",
        sa.Column("last_result", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scheduled_jobs", "last_result")
    op.drop_column("scheduled_jobs", "expires_at")
    op.drop_column("scheduled_jobs", "max_runs")
    op.drop_column("scheduled_jobs", "runs_completed")
    op.drop_column("scheduled_jobs", "consecutive_failures")
    op.drop_column("scheduled_jobs", "description")
    op.drop_column("scheduled_jobs", "name")
    op.drop_table("scheduled_workflows")
