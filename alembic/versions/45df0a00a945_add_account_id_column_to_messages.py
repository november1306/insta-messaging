"""add_account_id_column_to_messages

Revision ID: 45df0a00a945
Revises: e23697405e64
Create Date: 2025-12-29 15:52:29.351358

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '45df0a00a945'
down_revision: Union[str, None] = 'e23697405e64'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add account_id column to messages table with index.

    This establishes explicit foreign key relationship (added in later migration).
    Column is nullable initially to allow backfilling existing messages.
    """
    # Add account_id column (nullable for now)
    op.add_column(
        'messages',
        sa.Column('account_id', sa.String(50), nullable=True)
    )

    # Create index for query performance
    op.create_index(
        'idx_messages_account_id',
        'messages',
        ['account_id']
    )


def downgrade() -> None:
    """Remove account_id column and index"""
    # Drop index first
    op.drop_index('idx_messages_account_id', table_name='messages')

    # Drop column
    op.drop_column('messages', 'account_id')
