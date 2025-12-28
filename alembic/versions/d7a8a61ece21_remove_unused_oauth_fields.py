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
    # Remove unused fields from accounts table
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('refresh_token_encrypted')
        batch_op.drop_column('last_synced_at')
        batch_op.drop_column('oauth_user_id')

    # Remove unused OAuth fields from users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index('idx_users_oauth_provider')
        batch_op.drop_column('oauth_provider')
        batch_op.drop_column('oauth_provider_id')
        batch_op.drop_column('oauth_email')

    # Remove role field from user_accounts table
    with op.batch_alter_table('user_accounts', schema=None) as batch_op:
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
        batch_op.create_index('idx_users_oauth_provider', ['oauth_provider', 'oauth_provider_id'])

    # Re-add Account unused fields
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('refresh_token_encrypted', sa.Text, nullable=True))
        batch_op.add_column(sa.Column('last_synced_at', sa.DateTime, nullable=True))
        batch_op.add_column(sa.Column('oauth_user_id', sa.String(50), nullable=True))
