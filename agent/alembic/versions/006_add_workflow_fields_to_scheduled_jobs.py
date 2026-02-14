"""Add on_complete and workflow_id to scheduled_jobs.

Supports workflow chaining (resume_conversation) and workflow grouping.

Revision ID: 006
Revises: 005
Create Date: 2026-02-14
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "scheduled_jobs",
        sa.Column("on_complete", sa.String(), server_default="notify", nullable=False),
    )
    op.add_column(
        "scheduled_jobs",
        sa.Column("workflow_id", sa.Uuid(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scheduled_jobs", "workflow_id")
    op.drop_column("scheduled_jobs", "on_complete")
