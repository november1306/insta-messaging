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
import bcrypt
import uuid
import logging

from app.db.models import APIKey, APIKeyPermission, APIKeyType

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
    def hash_api_key(api_key: str) -> str:
        """
        Hash an API key using bcrypt.

        Args:
            api_key: Full API key

        Returns:
            bcrypt hash as string
        """
        return bcrypt.hashpw(api_key.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_api_key_hash(api_key: str, key_hash: str) -> bool:
        """
        Verify an API key against a stored hash.

        Args:
            api_key: Full API key to verify
            key_hash: Stored bcrypt hash

        Returns:
            True if key matches hash
        """
        try:
            return bcrypt.checkpw(api_key.encode('utf-8'), key_hash.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error verifying API key hash: {e}")
            return False

    @staticmethod
    async def create_api_key(
        db: AsyncSession,
        name: str,
        key_type: APIKeyType,
        environment: str = "test",
        account_ids: Optional[List[str]] = None,
        expires_at: Optional[datetime] = None
    ) -> tuple[str, APIKey]:
        """
        Create a new API key in the database.

        Args:
            db: Database session
            name: Descriptive name for the key
            key_type: APIKeyType.ADMIN or APIKeyType.ACCOUNT
            environment: "test" or "live"
            account_ids: List of account IDs for account-scoped keys (ignored for admin keys)
            expires_at: Optional expiration datetime

        Returns:
            Tuple of (full_api_key, APIKey_model)

        Note: The full API key is only returned once during creation.
              It cannot be retrieved later, so caller must save it.
        """
        # Generate the API key
        api_key = APIKeyService.generate_api_key(environment)
        key_prefix = APIKeyService.get_key_prefix(api_key)
        key_hash = APIKeyService.hash_api_key(api_key)

        # Create the database record
        db_key = APIKey(
            id=f"key_{uuid.uuid4().hex[:16]}",
            key_prefix=key_prefix,
            key_hash=key_hash,
            name=name,
            type=key_type,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            expires_at=expires_at
        )

        db.add(db_key)
        await db.flush()  # Get the ID without committing

        # Add permissions for account-scoped keys
        if key_type == APIKeyType.ACCOUNT and account_ids:
            for account_id in account_ids:
                permission = APIKeyPermission(
                    api_key_id=db_key.id,
                    account_id=account_id
                )
                db.add(permission)

        await db.commit()
        await db.refresh(db_key)

        logger.info(f"Created API key: {db_key.id} (name: {name}, type: {key_type.value})")

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
        if not APIKeyService.verify_api_key_hash(api_key, db_key.key_hash):
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
    async def check_account_permission(
        db: AsyncSession,
        api_key: APIKey,
        account_id: str
    ) -> bool:
        """
        Check if an API key has permission to access an account.

        Args:
            db: Database session
            api_key: APIKey object
            account_id: Account ID to check

        Returns:
            True if permitted, False otherwise
        """
        # Admin keys have access to all accounts
        if api_key.type == APIKeyType.ADMIN:
            return True

        # Account-scoped keys must be in permissions table
        result = await db.execute(
            select(APIKeyPermission).where(
                APIKeyPermission.api_key_id == api_key.id,
                APIKeyPermission.account_id == account_id
            )
        )
        permission = result.scalar_one_or_none()

        has_permission = permission is not None

        if not has_permission:
            logger.warning(
                f"Permission denied: API key {api_key.id} attempted to access account {account_id}"
            )

        return has_permission

    @staticmethod
    async def get_permitted_account_ids(
        db: AsyncSession,
        api_key: APIKey
    ) -> Optional[List[str]]:
        """
        Get list of account IDs the API key has access to.

        Args:
            db: Database session
            api_key: APIKey object

        Returns:
            List of account IDs, or None if admin (has access to all)
        """
        # Admin keys have access to all accounts
        if api_key.type == APIKeyType.ADMIN:
            return None  # None means "all accounts"

        # Get permitted accounts
        result = await db.execute(
            select(APIKeyPermission.account_id).where(
                APIKeyPermission.api_key_id == api_key.id
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
