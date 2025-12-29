"""
Account repository for data access.

Simple repository for account lookups.
Most account operations are handled directly in API endpoints currently.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account
from app.core.interfaces import IAccountRepository


class AccountRepository(IAccountRepository):
    """Repository for Account entity"""

    def __init__(self, session: AsyncSession):
        self._db = session

    async def get_by_id(self, account_id: str) -> Optional[Account]:
        """Get account by database ID"""
        result = await self._db.execute(
            select(Account).where(Account.id == account_id)
        )
        return result.scalar_one_or_none()

    async def get_by_instagram_id(self, instagram_id: str) -> Optional[Account]:
        """Get account by Instagram account ID"""
        result = await self._db.execute(
            select(Account).where(Account.instagram_account_id == instagram_id)
        )
        return result.scalar_one_or_none()

    async def get_by_messaging_channel_id(self, channel_id: str) -> Optional[Account]:
        """Get account by messaging channel ID"""
        result = await self._db.execute(
            select(Account).where(Account.messaging_channel_id == channel_id)
        )
        return result.scalar_one_or_none()
