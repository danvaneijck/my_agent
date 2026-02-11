"""Add trigger_on column to location_reminders.

Revision ID: 004
Revises: 003
Create Date: 2026-02-11
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "location_reminders",
        sa.Column("trigger_on", sa.String(), nullable=False, server_default="enter"),
    )


def downgrade() -> None:
    op.drop_column("location_reminders", "trigger_on")
