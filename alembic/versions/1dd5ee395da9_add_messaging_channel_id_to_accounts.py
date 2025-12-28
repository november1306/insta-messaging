"""Add messaging_channel_id to accounts

Revision ID: 1dd5ee395da9
Revises: 6b5301eac9d1
Create Date: 2025-12-21 18:15:15.010551

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1dd5ee395da9'
down_revision: Union[str, None] = '6b5301eac9d1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite batch mode for adding column with unique constraint
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('messaging_channel_id', sa.String(length=50), nullable=True))
        batch_op.create_index('idx_messaging_channel_id', ['messaging_channel_id'], unique=False)
        batch_op.create_unique_constraint('uq_accounts_messaging_channel_id', ['messaging_channel_id'])


def downgrade() -> None:
    # SQLite batch mode for dropping column with unique constraint
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_constraint('uq_accounts_messaging_channel_id', type_='unique')
        batch_op.drop_index('idx_messaging_channel_id')
        batch_op.drop_column('messaging_channel_id')
