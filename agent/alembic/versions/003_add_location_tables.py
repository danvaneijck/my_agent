"""Add location tables (user_locations, location_reminders, user_named_places, owntracks_credentials).

Revision ID: 003
Revises: 002
Create Date: 2026-02-11
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # user_locations — latest known position per user
    op.create_table(
        "user_locations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("accuracy_m", sa.Float(), nullable=True),
        sa.Column("speed_mps", sa.Float(), nullable=True),
        sa.Column("heading", sa.Float(), nullable=True),
        sa.Column("source", sa.String(), nullable=False, server_default="owntracks"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # location_reminders — geofence-based reminders
    op.create_table(
        "location_reminders",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column("place_name", sa.String(), nullable=False),
        sa.Column("place_lat", sa.Float(), nullable=False),
        sa.Column("place_lng", sa.Float(), nullable=False),
        sa.Column("radius_m", sa.Integer(), nullable=False, server_default="150"),
        sa.Column("platform", sa.String(), nullable=True),
        sa.Column("platform_channel_id", sa.String(), nullable=True),
        sa.Column("platform_thread_id", sa.String(), nullable=True),
        sa.Column("owntracks_rid", sa.String(), nullable=False),
        sa.Column("synced_to_device", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_location_reminders_user_status", "location_reminders", ["user_id", "status"])
    op.create_index("ix_location_reminders_rid", "location_reminders", ["owntracks_rid"])

    # user_named_places — saved locations per user
    op.create_table(
        "user_named_places",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("address", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_user_named_place"),
    )

    # owntracks_credentials — maps OwnTracks auth to internal users
    op.create_table(
        "owntracks_credentials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("username", sa.String(), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("device_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("owntracks_credentials")
    op.drop_table("user_named_places")
    op.drop_index("ix_location_reminders_rid", table_name="location_reminders")
    op.drop_index("ix_location_reminders_user_status", table_name="location_reminders")
    op.drop_table("location_reminders")
    op.drop_table("user_locations")
