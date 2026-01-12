"""
API Key Service - Handles generation, validation, and permission management.

This service provides secure API key management with bcrypt hashing,
prefix-based fast lookup, and permission scoping.
"""
from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import secrets
import string
import uuid
import logging

from app.db.models import APIKey, UserAccount
from app.utils.password_hash import hash_password, verify_password

logger = logging.getLogger(__name__)


class APIKeyService:
    """Service for managing API keys"""

    # API key format: sk_{env}_{32_random_chars}
    # Example: sk_test_AbCdEf1234567890GhIjKlMnOpQr
    KEY_PREFIX_LENGTH = 10  # "sk_test_Ab"
    KEY_RANDOM_LENGTH = 32

    @staticmethod
    def generate_api_key(environment: str = "test") -> str:
        """
        Generate a new API key.

        Args:
            environment: "test" or "live"

        Returns:
            Full API key (e.g., "sk_test_AbCdEf1234567890GhIjKlMnOpQr")
        """
        # Generate random string (letters + digits)
        alphabet = string.ascii_letters + string.digits
        random_part = ''.join(secrets.choice(alphabet) for _ in range(APIKeyService.KEY_RANDOM_LENGTH))

        # Format: sk_{env}_{random}
        return f"sk_{environment}_{random_part}"

    @staticmethod
    def get_key_prefix(api_key: str) -> str:
        """
        Extract the key prefix for database lookup.

        Args:
            api_key: Full API key

        Returns:
            First 10 characters (e.g., "sk_test_Ab")
        """
        return api_key[:APIKeyService.KEY_PREFIX_LENGTH]

    @staticmethod
    async def create_api_key(
        db: AsyncSession,
        name: str,
        user_id: int,
        environment: str = "user",
        expires_at: Optional[datetime] = None
    ) -> tuple[str, APIKey]:
        """
        Create a new user-scoped API key.

        Args:
            db: Database session
            name: Descriptive name for the key
            user_id: User ID who owns this key
            environment: "user" for user-generated tokens (default)
            expires_at: Required expiration datetime (30 days for user tokens)

        Returns:
            Tuple of (full_api_key, APIKey_model)

        Note: The full API key is only returned once during creation.
              It cannot be retrieved later, so caller must save it.

              Permissions are dynamic - derived from UserAccount table at request time.
              No static permissions are stored during creation.
        """
        # Generate the API key
        api_key = APIKeyService.generate_api_key(environment)
        key_prefix = APIKeyService.get_key_prefix(api_key)
        key_hash = hash_password(api_key)

        # Create the database record
        db_key = APIKey(
            id=f"key_{uuid.uuid4().hex[:16]}",
            key_prefix=key_prefix,
            key_hash=key_hash,
            name=name,
            user_id=user_id,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at
        )

        db.add(db_key)
        await db.commit()
        await db.refresh(db_key)

        logger.info(f"Created API key: {db_key.id} (name: {name}, user_id: {user_id})")

        return api_key, db_key

    @staticmethod
    async def validate_api_key(
        db: AsyncSession,
        api_key: str
    ) -> Optional[APIKey]:
        """
        Validate an API key and return the APIKey object if valid.

        Args:
            db: Database session
            api_key: Full API key to validate

        Returns:
            APIKey object if valid, None if invalid
        """
        # Extract prefix for fast lookup
        key_prefix = APIKeyService.get_key_prefix(api_key)

        # Find keys with matching prefix
        result = await db.execute(
            select(APIKey).where(
                APIKey.key_prefix == key_prefix,
                APIKey.is_active == True
            )
        )
        db_key = result.scalar_one_or_none()

        if not db_key:
            logger.warning(f"API key validation failed: No active key found with prefix {key_prefix}")
            return None

        # Verify the full key hash
        if not verify_password(api_key, db_key.key_hash):
            logger.warning(f"API key validation failed: Hash mismatch for key {db_key.id}")
            return None

        # Check expiration
        if db_key.expires_at and db_key.expires_at < datetime.now(timezone.utc):
            logger.warning(f"API key validation failed: Key {db_key.id} has expired")
            return None

        # Update last_used_at (fire and forget - don't wait for commit)
        db_key.last_used_at = datetime.now(timezone.utc)
        await db.commit()

        logger.debug(f"API key validated successfully: {db_key.id}")
        return db_key

    @staticmethod
    async def check_user_account_permission(
        db: AsyncSession,
        user_id: int,
        account_id: str
    ) -> bool:
        """
        Check if user has permission to access an account (dynamic check).

        Queries UserAccount table in real-time to ensure permissions reflect
        current state, even if accounts were linked/unlinked after token creation.

        Args:
            db: Database session
            user_id: User ID from API key
            account_id: Account ID to check

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

        has_permission = link is not None

        if not has_permission:
            logger.warning(
                f"Permission denied: User {user_id} attempted to access account {account_id}"
            )

        return has_permission

    @staticmethod
    async def get_user_account_ids(
        db: AsyncSession,
        user_id: int
    ) -> List[str]:
        """
        Get list of account IDs the user has access to (dynamic query).

        Used for listing accounts or filtering conversations. Permissions reflect
        current UserAccount links, not static permissions stored at token creation.

        Args:
            db: Database session
            user_id: User ID

        Returns:
            List of account IDs
        """
        result = await db.execute(
            select(UserAccount.account_id).where(
                UserAccount.user_id == user_id
            )
        )
        account_ids = [row[0] for row in result.fetchall()]

        return account_ids

    @staticmethod
    async def revoke_api_key(
        db: AsyncSession,
        key_id: str
    ) -> bool:
        """
        Revoke an API key (set is_active = False).

        Args:
            db: Database session
            key_id: API key ID to revoke

        Returns:
            True if revoked, False if not found
        """
        result = await db.execute(
            select(APIKey).where(APIKey.id == key_id)
        )
        db_key = result.scalar_one_or_none()

        if not db_key:
            return False

        db_key.is_active = False
        await db.commit()

        logger.info(f"Revoked API key: {key_id}")
        return True
