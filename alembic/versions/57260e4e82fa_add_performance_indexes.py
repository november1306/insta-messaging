"""add_performance_indexes

Revision ID: 57260e4e82fa
Revises: 45df0a00a945
Create Date: 2025-12-29 16:29:58.702351

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '57260e4e82fa'
down_revision: Union[str, None] = '45df0a00a945'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add performance indexes for message queries."""
    # CRITICAL: recipient_id is queried frequently in conversation filtering
    # This index significantly improves conversation list performance
    op.create_index(
        'idx_messages_recipient_id',
        'messages',
        ['recipient_id']
    )

    # Composite index for conversation filtering by account
    # Used in: get_conversations_for_account(), get_messages()
    # Covers queries filtering by account_id, recipient_id, and ordering by timestamp
    op.create_index(
        'idx_messages_account_recipient',
        'messages',
        ['account_id', 'recipient_id', 'timestamp']
    )

    # Index for response window queries (24-hour window checks)
    # Used for filtering messages by time and direction
    op.create_index(
        'idx_messages_timestamp_direction',
        'messages',
        ['timestamp', 'direction']
    )


def downgrade() -> None:
    """Remove performance indexes."""
    op.drop_index('idx_messages_timestamp_direction', table_name='messages')
    op.drop_index('idx_messages_account_recipient', table_name='messages')
    op.drop_index('idx_messages_recipient_id', table_name='messages')
