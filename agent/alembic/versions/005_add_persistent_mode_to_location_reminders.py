"""Add mode, trigger_count, cooldown_seconds to location_reminders.

Supports persistent (recurring) events alongside one-off reminders.

Revision ID: 005
Revises: 004
Create Date: 2026-02-11
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "location_reminders",
        sa.Column("mode", sa.String(), nullable=False, server_default="once"),
    )
    op.add_column(
        "location_reminders",
        sa.Column("cooldown_seconds", sa.Integer(), nullable=False, server_default="3600"),
    )
    op.add_column(
        "location_reminders",
        sa.Column("trigger_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("location_reminders", "trigger_count")
    op.drop_column("location_reminders", "cooldown_seconds")
    op.drop_column("location_reminders", "mode")
