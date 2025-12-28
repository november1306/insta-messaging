"""remove_unused_oauth_fields

Removes database fields that were never used or are redundant:
- Account.refresh_token_encrypted (Instagram doesn't use refresh tokens)
- Account.last_synced_at (no sync task implemented)
- Account.oauth_user_id (redundant with instagram_account_id)
- User.oauth_provider, oauth_provider_id, oauth_email (never implemented)
- UserAccount.role (not enforced anywhere)

Kept for debugging:
- Account.account_type (useful for support)

Revision ID: d7a8a61ece21
Revises: e3fa065289d3
Create Date: 2025-12-21 23:43:12.562178

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7a8a61ece21'
down_revision: Union[str, None] = 'e3fa065289d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import inspect
    from sqlalchemy.exc import OperationalError

    bind = op.get_bind()
    inspector = inspect(bind)

    # Remove unused fields from accounts table if they exist
    accounts_columns = [col['name'] for col in inspector.get_columns('accounts')]
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        if 'refresh_token_encrypted' in accounts_columns:
            batch_op.drop_column('refresh_token_encrypted')
        if 'last_synced_at' in accounts_columns:
            batch_op.drop_column('last_synced_at')
        if 'oauth_user_id' in accounts_columns:
            batch_op.drop_column('oauth_user_id')

    # Remove unused OAuth fields from users table if they exist
    users_columns = [col['name'] for col in inspector.get_columns('users')]
    users_indexes = [idx['name'] for idx in inspector.get_indexes('users')]

    with op.batch_alter_table('users', schema=None) as batch_op:
        # Drop index idx_oauth_provider (not idx_users_oauth_provider!)
        if 'idx_oauth_provider' in users_indexes:
            try:
                batch_op.drop_index('idx_oauth_provider')
            except (OperationalError, KeyError, ValueError):
                pass  # Index doesn't exist or already dropped

        if 'oauth_provider' in users_columns:
            batch_op.drop_column('oauth_provider')
        if 'oauth_provider_id' in users_columns:
            batch_op.drop_column('oauth_provider_id')
        if 'oauth_email' in users_columns:
            batch_op.drop_column('oauth_email')

    # Remove role field from user_accounts table if it exists
    user_accounts_columns = [col['name'] for col in inspector.get_columns('user_accounts')]
    with op.batch_alter_table('user_accounts', schema=None) as batch_op:
        if 'role' in user_accounts_columns:
            batch_op.drop_column('role')


def downgrade() -> None:
    # Re-add role field to user_accounts
    with op.batch_alter_table('user_accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(20), nullable=False, server_default='owner'))

    # Re-add User OAuth fields
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('oauth_provider', sa.String(50), nullable=True))
        batch_op.add_column(sa.Column('oauth_provider_id', sa.String(100), nullable=True))
        batch_op.add_column(sa.Column('oauth_email', sa.String(255), nullable=True))
        # Use correct index name: idx_oauth_provider (not idx_users_oauth_provider)
        batch_op.create_index('idx_oauth_provider', ['oauth_provider', 'oauth_provider_id'])

    # Re-add Account unused fields
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('refresh_token_encrypted', sa.Text, nullable=True))
        batch_op.add_column(sa.Column('last_synced_at', sa.DateTime, nullable=True))
        batch_op.add_column(sa.Column('oauth_user_id', sa.String(50), nullable=True))
