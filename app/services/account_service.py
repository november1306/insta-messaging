"""
Account Service - Centralized account and token management

Provides utilities for:
- Fetching and decrypting account tokens
- Getting user's primary account
- Account access validation
"""
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models import Account, UserAccount
from app.services.encryption_service import decrypt_credential
from app.config import settings

logger = logging.getLogger(__name__)


class AccountService:
    """Service for managing Instagram business accounts and access tokens"""

    @staticmethod
    async def get_account_token(db: AsyncSession, account_id: str) -> str:
        """
        Get decrypted access token for an Instagram account.

        Args:
            db: Database session
            account_id: Account ID to fetch token for

        Returns:
            Decrypted access token string

        Raises:
            ValueError: If account not found, token is missing, or token has expired
        """
        # Fetch account from database
        result = await db.execute(
            select(Account).where(Account.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            logger.error(f"Account not found: {account_id}")
            raise ValueError(f"Account not found: {account_id}")

        if not account.access_token_encrypted:
            logger.error(f"Account {account_id} has no access token")
            raise ValueError(f"Account {account_id} has no access token")

        # Check if token has expired (60-day expiration for long-lived tokens)
        if account.token_expires_at:
            from datetime import datetime
            if account.token_expires_at < datetime.utcnow():
                logger.error(
                    f"Token expired for account {account_id} (@{account.username}) "
                    f"on {account.token_expires_at.isoformat()}"
                )
                raise ValueError(
                    f"Instagram access token for @{account.username} expired on "
                    f"{account.token_expires_at.strftime('%Y-%m-%d')}. "
                    f"Please re-authenticate this account via the Account Selector in the UI."
                )

        # Decrypt token using encryption service
        try:
            decrypted_token = decrypt_credential(
                account.access_token_encrypted,
                settings.session_secret
            )
            logger.debug(f"Retrieved access token for account {account_id} (@{account.username})")
            return decrypted_token
        except Exception as e:
            logger.error(f"Failed to decrypt token for account {account_id}: {e}")
            raise ValueError(f"Failed to decrypt account token: {e}")

    @staticmethod
    async def get_primary_account(db: AsyncSession, user_id: int) -> Optional[Account]:
        """
        Get user's primary Instagram account.

        Returns the account marked as primary for this user.
        If no primary account, returns the first linked account.
        If no accounts linked, returns None.

        Args:
            db: Database session
            user_id: User ID to fetch primary account for

        Returns:
            Account object or None if user has no linked accounts
        """
        # Try to get primary account
        result = await db.execute(
            select(Account)
            .join(UserAccount, UserAccount.account_id == Account.id)
            .where(
                UserAccount.user_id == user_id,
                UserAccount.is_primary == True
            )
        )
        primary_account = result.scalar_one_or_none()

        if primary_account:
            logger.debug(f"Found primary account for user {user_id}: {primary_account.id} (@{primary_account.username})")
            return primary_account

        # Fallback: Get first linked account
        result = await db.execute(
            select(Account)
            .join(UserAccount, UserAccount.account_id == Account.id)
            .where(UserAccount.user_id == user_id)
            .limit(1)
        )
        first_account = result.scalar_one_or_none()

        if first_account:
            logger.debug(f"No primary account for user {user_id}, using first account: {first_account.id} (@{first_account.username})")
            return first_account

        logger.debug(f"User {user_id} has no linked Instagram accounts")
        return None

    @staticmethod
    async def get_account_by_instagram_id(
        db: AsyncSession,
        instagram_account_id: str
    ) -> Optional[Account]:
        """
        Get account by Instagram account ID.

        Args:
            db: Database session
            instagram_account_id: Instagram's business account ID

        Returns:
            Account object or None if not found
        """
        result = await db.execute(
            select(Account).where(Account.instagram_account_id == instagram_account_id)
        )
        account = result.scalar_one_or_none()

        if account:
            logger.debug(f"Found account by Instagram ID {instagram_account_id}: {account.id} (@{account.username})")
        else:
            logger.debug(f"No account found with Instagram ID {instagram_account_id}")

        return account

    @staticmethod
    async def verify_user_has_access(
        db: AsyncSession,
        user_id: int,
        account_id: str
    ) -> bool:
        """
        Verify that a user has access to a specific account.

        Args:
            db: Database session
            user_id: User ID to check
            account_id: Account ID to check access for

        Returns:
            True if user has access, False otherwise
        """
        result = await db.execute(
            select(UserAccount).where(
                UserAccount.user_id == user_id,
                UserAccount.account_id == account_id
            )
        )
        link = result.scalar_one_or_none()

        has_access = link is not None
        logger.debug(f"User {user_id} access to account {account_id}: {has_access}")
        return has_access

    @staticmethod
    async def get_account_with_token(
        db: AsyncSession,
        account_id: str
    ) -> tuple[Account, str]:
        """
        Get account object and decrypted token together.

        Convenience method that combines get_account and get_account_token.

        Args:
            db: Database session
            account_id: Account ID to fetch

        Returns:
            Tuple of (Account, decrypted_token)

        Raises:
            ValueError: If account not found or token decryption fails
        """
        # Fetch account
        result = await db.execute(
            select(Account).where(Account.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            raise ValueError(f"Account not found: {account_id}")

        # Decrypt token
        decrypted_token = decrypt_credential(
            account.access_token_encrypted,
            settings.session_secret
        )

        return account, decrypted_token
