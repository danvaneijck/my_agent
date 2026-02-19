"""Add slack_installations table and platform_server_id to scheduled_jobs.

Revision ID: 015
Revises: 014
Create Date: 2026-02-19
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Slack installations table for multi-workspace OAuth
    op.create_table(
        "slack_installations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("client_id", sa.String(64), nullable=False),
        sa.Column("app_id", sa.String(64), nullable=False),
        sa.Column("enterprise_id", sa.String(64), nullable=True),
        sa.Column("enterprise_name", sa.String(200), nullable=True),
        sa.Column("team_id", sa.String(64), nullable=False),
        sa.Column("team_name", sa.String(200), nullable=True),
        sa.Column("bot_token", sa.Text(), nullable=False),
        sa.Column("bot_id", sa.String(64), nullable=True),
        sa.Column("bot_user_id", sa.String(64), nullable=True),
        sa.Column("bot_scopes", sa.Text(), nullable=True),
        sa.Column("installed_by_user_id", sa.String(64), nullable=True),
        sa.Column("is_enterprise_install", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "installed_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_unique_constraint(
        "uq_slack_installation_client_team", "slack_installations", ["client_id", "team_id"]
    )
    op.create_index("ix_slack_installations_team_id", "slack_installations", ["team_id"])

    # Add platform_server_id to scheduled_jobs for workspace-aware notifications
    op.add_column("scheduled_jobs", sa.Column("platform_server_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("scheduled_jobs", "platform_server_id")
    op.drop_index("ix_slack_installations_team_id")
    op.drop_constraint("uq_slack_installation_client_team", "slack_installations")
    op.drop_table("slack_installations")
