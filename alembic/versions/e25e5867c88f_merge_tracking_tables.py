"""merge_tracking_tables

Revision ID: e25e5867c88f
Revises: 57260e4e82fa
Create Date: 2025-12-29 16:30:23.987029

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e25e5867c88f'
down_revision: Union[str, None] = '57260e4e82fa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge CRM tracking fields into messages table.

    This migration adds tracking fields (idempotency_key, delivery_status, error tracking)
    to the messages table, enabling us to eventually consolidate crm_outbound_messages
    into the main messages table.

    Note: This migration only adds columns. Data migration from crm_outbound_messages
    can be done separately if needed, but new code uses messages table directly.
    """
    # Add CRM tracking fields to messages table
    op.add_column('messages', sa.Column('idempotency_key', sa.String(100), nullable=True))
    op.add_column('messages', sa.Column('delivery_status', sa.String(20), nullable=True))
    op.add_column('messages', sa.Column('error_code', sa.String(50), nullable=True))
    op.add_column('messages', sa.Column('error_message', sa.Text, nullable=True))

    # Create unique index on idempotency_key for duplicate detection
    # Partial index: only index non-null values (SQLite supports partial indexes)
    op.create_index(
        'idx_messages_idempotency_key',
        'messages',
        ['idempotency_key'],
        unique=True,
        sqlite_where=sa.text('idempotency_key IS NOT NULL')  # Partial index for SQLite
    )

    # Note: crm_outbound_messages table can remain for now as a legacy tracking table
    # New code uses MessageService which stores tracking data in messages table
    # The CRMOutboundMessage table can be dropped in a future migration after data migration


def downgrade() -> None:
    """Remove CRM tracking fields from messages table."""
    op.drop_index('idx_messages_idempotency_key', table_name='messages')
    op.drop_column('messages', 'error_message')
    op.drop_column('messages', 'error_code')
    op.drop_column('messages', 'delivery_status')
    op.drop_column('messages', 'idempotency_key')
