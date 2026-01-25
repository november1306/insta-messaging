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
    # Get connection to check if index exists
    conn = op.get_bind()

    # Check if index exists before trying to drop it
    # (VPS database may not have had this index created)
    result = conn.execute(sa.text(
        "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_user_accounts_user_primary'"
    ))
    if result.fetchone():
        op.drop_index('idx_user_accounts_user_primary', table_name='user_accounts')

    # Check if column exists before trying to drop it
    result = conn.execute(sa.text("PRAGMA table_info(user_accounts)"))
    columns = [row[1] for row in result.fetchall()]
    if 'is_primary' in columns:
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
