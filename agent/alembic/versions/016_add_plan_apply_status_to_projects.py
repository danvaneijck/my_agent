"""Add plan_apply_status and plan_apply_error to projects table.

Revision ID: 016
Revises: 015
Create Date: 2026-02-20
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column(
            "plan_apply_status",
            sa.String(),
            nullable=False,
            server_default="idle",
        ),
    )
    op.add_column(
        "projects",
        sa.Column("plan_apply_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "plan_apply_error")
    op.drop_column("projects", "plan_apply_status")
