"""add_unique_constraint_user_accounts

Revision ID: 054b11c44775
Revises: 4708f20f955c
Create Date: 2025-12-20 14:44:20.559482

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '054b11c44775'
down_revision: Union[str, None] = '4708f20f955c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add unique constraint to prevent duplicate user-account links
    # SQLite requires batch mode for adding constraints
    with op.batch_alter_table('user_accounts', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_user_account', ['user_id', 'account_id'])


def downgrade() -> None:
    # Remove unique constraint
    with op.batch_alter_table('user_accounts', schema=None) as batch_op:
        batch_op.drop_constraint('uq_user_account', type_='unique')
