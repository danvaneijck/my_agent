"""Add planning_task_id to projects.

Revision ID: 011
Revises: 010
Create Date: 2026-02-15
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("planning_task_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "planning_task_id")
