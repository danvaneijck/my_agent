"""Add title and last_read_at to conversations.

Supports conversation naming and unread tracking for the web portal.

Revision ID: 007
Revises: 006
Create Date: 2026-02-14
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("conversations", sa.Column("title", sa.String(), nullable=True))
    op.add_column(
        "conversations",
        sa.Column("last_read_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "last_read_at")
    op.drop_column("conversations", "title")
