"""add_unique_constraint_user_account

Adds unique constraint on (user_id, account_id) to prevent users from
linking the same Instagram account multiple times.

This fixes a bug where OAuth callback could create duplicate links,
causing the same account to appear twice in the account selector.

Revision ID: e23697405e64
Revises: d7a8a61ece21
Create Date: 2025-12-21 23:44:33.482334

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e23697405e64'
down_revision: Union[str, None] = 'd7a8a61ece21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unique constraint to prevent duplicate user-account links
    with op.batch_alter_table('user_accounts', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_user_account', ['user_id', 'account_id'])


def downgrade() -> None:
    # Remove unique constraint
    with op.batch_alter_table('user_accounts', schema=None) as batch_op:
        batch_op.drop_constraint('uq_user_account', type_='unique')
