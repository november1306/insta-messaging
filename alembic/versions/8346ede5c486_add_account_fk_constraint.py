"""add_account_fk_constraint

Revision ID: 8346ede5c486
Revises: e25e5867c88f
Create Date: 2025-12-29 17:00:59.275597

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8346ede5c486'
down_revision: Union[str, None] = 'e25e5867c88f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add foreign key constraint from messages to accounts.

    Steps:
    1. Make account_id NOT NULL (all messages should have account_id by now)
    2. Add FK constraint with CASCADE DELETE (when account is deleted, delete all its messages)

    Prerequisites:
    - All messages must have account_id populated (run backfill_account_ids.py first)
    - All account_ids must reference valid accounts

    Impact:
    - Deleting an account will automatically delete all its messages
    - Ensures referential integrity at database level
    """
    # Step 1: Make account_id NOT NULL
    # SQLite doesn't support ALTER COLUMN directly, but we can use batch mode
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.alter_column('account_id',
                              existing_type=sa.String(50),
                              nullable=False)

    # Step 2: Add foreign key constraint with CASCADE DELETE
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_messages_account_id',  # Constraint name
            'accounts',  # Referenced table
            ['account_id'],  # Local column
            ['id'],  # Referenced column
            ondelete='CASCADE'  # Delete messages when account is deleted
        )


def downgrade() -> None:
    """Remove foreign key constraint and make account_id nullable again."""
    # Remove FK constraint
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.drop_constraint('fk_messages_account_id', type_='foreignkey')

    # Make account_id nullable again
    with op.batch_alter_table('messages', schema=None) as batch_op:
        batch_op.alter_column('account_id',
                              existing_type=sa.String(50),
                              nullable=True)
