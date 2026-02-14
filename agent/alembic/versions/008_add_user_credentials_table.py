"""Add user_credentials table for encrypted per-user service credentials.

Revision ID: 008
Revises: 007
Create Date: 2026-02-14
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "user_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("service", sa.String(), nullable=False),
        sa.Column("credential_key", sa.String(), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint(
        "uq_user_service_key",
        "user_credentials",
        ["user_id", "service", "credential_key"],
    )
    op.create_index(
        "ix_user_credentials_user_service",
        "user_credentials",
        ["user_id", "service"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_credentials_user_service")
    op.drop_constraint("uq_user_service_key", "user_credentials")
    op.drop_table("user_credentials")
