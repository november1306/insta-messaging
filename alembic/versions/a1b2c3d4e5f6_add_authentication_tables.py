"""add authentication tables (api_keys and api_key_permissions)

Revision ID: a1b2c3d4e5f6
Revises: e75f64bf2da2
Create Date: 2025-11-17 20:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e75f64bf2da2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create api_keys table
    op.create_table('api_keys',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('key_prefix', sa.String(length=20), nullable=False),
        sa.Column('key_hash', sa.String(length=100), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('type', sa.Enum('ADMIN', 'ACCOUNT', name='apikeytype'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.Column('expires_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_key_prefix', 'api_keys', ['key_prefix'], unique=False)
    op.create_index('idx_is_active', 'api_keys', ['is_active'], unique=False)

    # Create api_key_permissions table
    op.create_table('api_key_permissions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('api_key_id', sa.String(length=50), nullable=False),
        sa.Column('account_id', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['api_key_id'], ['api_keys.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_api_key_id', 'api_key_permissions', ['api_key_id'], unique=False)
    op.create_index('idx_account_id', 'api_key_permissions', ['account_id'], unique=False)


def downgrade() -> None:
    # Drop api_key_permissions table
    op.drop_index('idx_account_id', table_name='api_key_permissions')
    op.drop_index('idx_api_key_id', table_name='api_key_permissions')
    op.drop_table('api_key_permissions')

    # Drop api_keys table
    op.drop_index('idx_is_active', table_name='api_keys')
    op.drop_index('idx_key_prefix', table_name='api_keys')
    op.drop_table('api_keys')

    # Drop enum type
    op.execute('DROP TYPE apikeytype')
