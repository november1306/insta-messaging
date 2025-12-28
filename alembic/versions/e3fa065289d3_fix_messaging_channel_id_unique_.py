"""Fix messaging_channel_id unique constraint

Revision ID: e3fa065289d3
Revises: 1dd5ee395da9
Create Date: 2025-12-21 18:17:17.214873

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3fa065289d3'
down_revision: Union[str, None] = '1dd5ee395da9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the existing non-unique index
    op.drop_index('idx_messaging_channel_id', table_name='accounts')
    # Create a unique index instead (serves same purpose as unique constraint in SQLite)
    op.create_index('idx_messaging_channel_id', 'accounts', ['messaging_channel_id'], unique=True)


def downgrade() -> None:
    # Drop unique index
    op.drop_index('idx_messaging_channel_id', table_name='accounts')
    # Recreate as non-unique
    op.create_index('idx_messaging_channel_id', 'accounts', ['messaging_channel_id'], unique=False)
