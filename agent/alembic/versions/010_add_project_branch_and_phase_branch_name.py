"""Add project_branch to projects and branch_name to project_phases.

Revision ID: 010
Revises: 009
Create Date: 2026-02-15
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("projects", sa.Column("project_branch", sa.String(), nullable=True))
    op.add_column("project_phases", sa.Column("branch_name", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("project_phases", "branch_name")
    op.drop_column("projects", "project_branch")
