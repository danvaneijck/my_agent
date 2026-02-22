"""Add cache token columns to token_logs.

Anthropic bills for cache_creation_input_tokens (at 1.25x input rate) and
cache_read_input_tokens (at 0.1x input rate) separately from regular
input_tokens.  Track these so the token log matches the actual API bill.

Revision ID: 020
Revises: 019
Create Date: 2026-02-22
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "token_logs",
        sa.Column(
            "cache_creation_input_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "token_logs",
        sa.Column(
            "cache_read_input_tokens",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("token_logs", "cache_read_input_tokens")
    op.drop_column("token_logs", "cache_creation_input_tokens")
