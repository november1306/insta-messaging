"""
User Service - Handles user authentication and management.

This service provides user management with bcrypt password hashing
for UI authentication via JWT sessions.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import bcrypt
import logging

from app.db.models import User

logger = logging.getLogger(__name__)


class UserService:
    """Service for managing users and authentication"""

    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            bcrypt hash as string
        """
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        """
        Verify a password against a stored hash.

        Args:
            password: Plain text password to verify
            password_hash: Stored bcrypt hash

        Returns:
            True if password matches hash
        """
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error verifying password: {e}")
            return False

    @staticmethod
    async def create_user(
        db: AsyncSession,
        username: str,
        password: str
    ) -> User:
        """
        Create a new user in the database.

        Args:
            db: Database session
            username: Username for login
            password: Plain text password (will be hashed)

        Returns:
            User model

        Raises:
            ValueError: If username already exists
        """
        # Check if username already exists
        existing_user = await UserService.get_user_by_username(db, username)
        if existing_user:
            raise ValueError(f"Username '{username}' already exists")

        # Hash the password
        password_hash = UserService.hash_password(password)

        # Create the user
        user = User(
            username=username,
            password_hash=password_hash,
            is_active=True,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        db.add(user)
        await db.commit()
        await db.refresh(user)

        logger.info(f"Created user: {user.id} (username: {username})")
        return user

    @staticmethod
    async def get_user_by_username(
        db: AsyncSession,
        username: str
    ) -> Optional[User]:
        """
        Get user by username.

        Args:
            db: Database session
            username: Username to lookup

        Returns:
            User object if found, None otherwise
        """
        result = await db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def validate_credentials(
        db: AsyncSession,
        username: str,
        password: str
    ) -> Optional[User]:
        """
        Validate username and password credentials.

        Args:
            db: Database session
            username: Username
            password: Plain text password

        Returns:
            User object if credentials are valid and user is active, None otherwise
        """
        # Get user by username
        user = await UserService.get_user_by_username(db, username)

        if not user:
            logger.warning(f"Login attempt failed: User '{username}' not found")
            return None

        # Check if user is active
        if not user.is_active:
            logger.warning(f"Login attempt failed: User '{username}' is deactivated")
            return None

        # Verify password
        if not UserService.verify_password(password, user.password_hash):
            logger.warning(f"Login attempt failed: Invalid password for user '{username}'")
            return None

        logger.info(f"User authenticated successfully: {user.id} (username: {username})")
        return user

    @staticmethod
    async def update_password(
        db: AsyncSession,
        user_id: int,
        new_password: str
    ) -> bool:
        """
        Update user password.

        Args:
            db: Database session
            user_id: User ID
            new_password: New plain text password (will be hashed)

        Returns:
            True if updated successfully, False if user not found
        """
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"Password update failed: User {user_id} not found")
            return False

        # Hash new password
        user.password_hash = UserService.hash_password(new_password)
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()

        logger.info(f"Password updated for user: {user.id} (username: {user.username})")
        return True

    @staticmethod
    async def deactivate_user(
        db: AsyncSession,
        user_id: int
    ) -> bool:
        """
        Deactivate a user (soft delete).

        Args:
            db: Database session
            user_id: User ID to deactivate

        Returns:
            True if deactivated, False if not found
        """
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"Deactivation failed: User {user_id} not found")
            return False

        user.is_active = False
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()

        logger.info(f"Deactivated user: {user.id} (username: {user.username})")
        return True

    @staticmethod
    async def activate_user(
        db: AsyncSession,
        user_id: int
    ) -> bool:
        """
        Activate a previously deactivated user.

        Args:
            db: Database session
            user_id: User ID to activate

        Returns:
            True if activated, False if not found
        """
        result = await db.execute(
            select(User).where(User.id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"Activation failed: User {user_id} not found")
            return False

        user.is_active = True
        user.updated_at = datetime.now(timezone.utc)

        await db.commit()

        logger.info(f"Activated user: {user.id} (username: {user.username})")
        return True
