"""add_users_table_for_ui_authentication

Revision ID: 871d0225be49
Revises: 7fabcd2fc75f
Create Date: 2025-11-28 22:35:32.196585

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '871d0225be49'
down_revision: Union[str, None] = '7fabcd2fc75f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create users table for UI authentication (idempotent - safe to run multiple times)
    from sqlalchemy import inspect
    from sqlalchemy.engine import reflection

    bind = op.get_bind()
    inspector = inspect(bind)

    # Check if users table exists
    if 'users' not in inspector.get_table_names():
        op.create_table('users',
            sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
            sa.Column('username', sa.String(length=50), nullable=False),
            sa.Column('password_hash', sa.String(length=255), nullable=False),
            sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('username')
        )

    # Check if indexes exist before creating them (must be outside table creation block)
    # Refresh inspector after potential table creation
    inspector = inspect(bind)

    # Only check indexes if table exists
    if 'users' in inspector.get_table_names():
        existing_indexes = [idx['name'] for idx in inspector.get_indexes('users')]

        if 'idx_username' not in existing_indexes:
            op.create_index('idx_username', 'users', ['username'], unique=False)

        if 'idx_is_active' not in existing_indexes:
            op.create_index('idx_is_active', 'users', ['is_active'], unique=False)


def downgrade() -> None:
    # Drop users table
    op.drop_index('idx_is_active', table_name='users')
    op.drop_index('idx_username', table_name='users')
    op.drop_table('users')
