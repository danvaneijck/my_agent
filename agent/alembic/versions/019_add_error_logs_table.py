"""Add error_logs table for centralized error capturing.

Revision ID: 019
Revises: 018
Create Date: 2026-02-21
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "error_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("service", sa.String(), nullable=False),
        sa.Column("error_type", sa.String(), nullable=False),
        sa.Column("tool_name", sa.String(), nullable=True),
        sa.Column("tool_arguments", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("stack_trace", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("conversation_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_error_logs_status", "error_logs", ["status"])
    op.create_index("ix_error_logs_service", "error_logs", ["service"])
    op.create_index("ix_error_logs_created_at", "error_logs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_error_logs_created_at", table_name="error_logs")
    op.drop_index("ix_error_logs_service", table_name="error_logs")
    op.drop_index("ix_error_logs_status", table_name="error_logs")
    op.drop_table("error_logs")
