"""Make token_logs.conversation_id nullable.

Portal makes direct Anthropic API calls (plan parsing, title generation)
that may not be tied to a conversation.

Revision ID: 013
Revises: 012
Create Date: 2026-02-16
"""

from typing import Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.alter_column("token_logs", "conversation_id", nullable=True)


def downgrade() -> None:
    op.alter_column("token_logs", "conversation_id", nullable=False)
