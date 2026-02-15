"""Add workflow_id to projects.

Revision ID: 012
Revises: 011
Create Date: 2026-02-15
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("workflow_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("projects", "workflow_id")
