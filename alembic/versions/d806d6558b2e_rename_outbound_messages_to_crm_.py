"""rename_outbound_messages_to_crm_outbound_messages

Revision ID: d806d6558b2e
Revises: 871d0225be49
Create Date: 2025-11-29 12:56:56.529409

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd806d6558b2e'
down_revision: Union[str, None] = '871d0225be49'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename table
    op.rename_table('outbound_messages', 'crm_outbound_messages')


def downgrade() -> None:
    # Revert table rename
    op.rename_table('crm_outbound_messages', 'outbound_messages')
