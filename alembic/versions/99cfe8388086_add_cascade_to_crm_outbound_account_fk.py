"""add_cascade_to_crm_outbound_account_fk

Revision ID: 99cfe8388086
Revises: 8346ede5c486
Create Date: 2025-12-31 16:12:26.650065

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '99cfe8388086'
down_revision: Union[str, None] = '8346ede5c486'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite: batch_alter_table recreates the table, so we can just
    # add the foreign key constraint with CASCADE directly
    # The old unnamed FK constraint will be replaced
    with op.batch_alter_table('crm_outbound_messages', schema=None, recreate='always') as batch_op:
        batch_op.create_foreign_key(
            'fk_crm_outbound_messages_account_id',
            'accounts',
            ['account_id'],
            ['id'],
            ondelete='CASCADE'
        )


def downgrade() -> None:
    # Revert to FK constraint without CASCADE
    with op.batch_alter_table('crm_outbound_messages', schema=None, recreate='always') as batch_op:
        batch_op.create_foreign_key(
            None,  # Unnamed constraint like the original
            'accounts',
            ['account_id'],
            ['id']
        )
