"""Make message_text nullable in crm_outbound_messages

Revision ID: 3f8c7729902f
Revises: 8f91b94b697c
Create Date: 2025-12-13 14:20:36.329200

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3f8c7729902f'
down_revision: Union[str, None] = '8f91b94b697c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLite doesn't support ALTER COLUMN for NULL/NOT NULL changes
    # Use batch mode to recreate the table with new schema

    with op.batch_alter_table('crm_outbound_messages', schema=None) as batch_op:
        batch_op.alter_column('message_text',
                   existing_type=sa.TEXT(),
                   nullable=True)

    # Add missing index on users table (if not exists)
    # Use raw SQL to check if index exists (inspector doesn't work reliably in migrations)
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_is_active'"))
    index_exists = result.fetchone() is not None

    if not index_exists:
        op.create_index('idx_is_active', 'users', ['is_active'], unique=False)


def downgrade() -> None:
    # Reverse the changes
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT name FROM sqlite_master WHERE type='index' AND name='idx_is_active'"))
    index_exists = result.fetchone() is not None

    if index_exists:
        op.drop_index('idx_is_active', table_name='users')

    with op.batch_alter_table('crm_outbound_messages', schema=None) as batch_op:
        batch_op.alter_column('message_text',
                   existing_type=sa.TEXT(),
                   nullable=False)
