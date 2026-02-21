"""Add index on memory_summaries.user_id for per-user query performance.

Revision ID: 017
Revises: 016
Create Date: 2026-02-21
"""

from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_index(
        "ix_memory_summaries_user_id",
        "memory_summaries",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_memory_summaries_user_id", table_name="memory_summaries")
