"""remove is_primary column from user_accounts

Revision ID: remove_is_primary_001
Revises: 88984064f416
Create Date: 2026-01-24

The "primary account" concept is being replaced by "focused account"
which is managed entirely in frontend session state, not persisted.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'remove_is_primary_001'
down_revision: Union[str, None] = '88984064f416'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop the index first (required before dropping the column)
    op.drop_index('idx_user_accounts_user_primary', table_name='user_accounts')

    # Drop the is_primary column
    op.drop_column('user_accounts', 'is_primary')


def downgrade() -> None:
    # Re-add the is_primary column
    op.add_column(
        'user_accounts',
        sa.Column('is_primary', sa.Boolean(), nullable=False, server_default='0')
    )

    # Re-create the index
    op.create_index(
        'idx_user_accounts_user_primary',
        'user_accounts',
        ['user_id', 'is_primary']
    )
