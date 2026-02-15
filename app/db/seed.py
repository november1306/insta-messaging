"""
Database seed module for test preconditions.

Provides reusable async functions for creating test users, the @el_dmytr
Instagram account, and linking them together. Used by both the CLI
preconditions script and pytest fixtures.

Design:
- Idempotent account: @el_dmytr is created once; subsequent runs skip creation
- Incremental users: Each invocation creates the next testN user (test1, test2, ...)
- Token encryption: Reads plaintext token from env, encrypts at runtime with Fernet
"""
import os
import re
import logging
from datetime import datetime, timezone

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, User, UserAccount
from app.services.user_service import UserService
from app.services.encryption_service import EncryptionService

logger = logging.getLogger(__name__)


# ============================================
# @el_dmytr account constants
# ============================================

EL_DMYTR_ACCOUNT_ID = "acc_25586af607c2"
EL_DMYTR_INSTAGRAM_ACCOUNT_ID = "24370771369265571"
EL_DMYTR_USERNAME = "@el_dmytr"
EL_DMYTR_MESSAGING_CHANNEL_ID = "17841478096518771"
EL_DMYTR_TOKEN_EXPIRES_AT = datetime(2026, 3, 26, 11, 19, 34, 181709, tzinfo=timezone.utc)

# Env var name for the plaintext access token
SEED_TOKEN_ENV_VAR = "SEED_EL_DMYTR_ACCESS_TOKEN"

# Default password for test users
DEFAULT_TEST_PASSWORD = "testpass"


async def find_next_test_username(db: AsyncSession) -> str:
    """
    Find the next available testN username.

    Queries users table for usernames matching 'test%' pattern,
    extracts the numeric suffixes, and returns 'testN+1'.

    Returns:
        Next available username like 'test1', 'test2', etc.
    """
    result = await db.execute(
        select(User.username).where(User.username.like("test%"))
    )
    usernames = [row[0] for row in result.fetchall()]

    # Extract numeric suffixes
    max_num = 0
    for name in usernames:
        match = re.match(r"^test(\d+)$", name)
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num

    return f"test{max_num + 1}"


async def seed_test_user(
    db: AsyncSession,
    username: str | None = None,
    password: str | None = None
) -> User:
    """
    Create a test user. Auto-generates next testN username if not specified.

    Args:
        db: Database session
        username: Explicit username, or None for auto-generated testN
        password: Password for the user (default: 'testpass')

    Returns:
        Created User model instance
    """
    if username is None:
        username = await find_next_test_username(db)
    if password is None:
        password = DEFAULT_TEST_PASSWORD

    user = await UserService.create_user(db=db, username=username, password=password)
    logger.info(f"Created test user: {username}")
    return user


async def seed_el_dmytr_account(
    db: AsyncSession,
    session_secret: str
) -> Account:
    """
    Ensure the @el_dmytr Instagram account exists in the database.

    Reads SEED_EL_DMYTR_ACCESS_TOKEN from environment and encrypts it
    at runtime using the provided session_secret. If the env var is empty,
    uses a placeholder token (suitable for pytest but not real API calls).

    Idempotent: returns existing account if already present.

    Args:
        db: Database session
        session_secret: SESSION_SECRET for Fernet encryption

    Returns:
        Account model instance (created or existing)
    """
    # Check if account already exists
    result = await db.execute(
        select(Account).where(Account.id == EL_DMYTR_ACCOUNT_ID)
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.info(f"Account {EL_DMYTR_USERNAME} already exists")
        return existing

    # Read plaintext token from environment
    plaintext_token = os.getenv(SEED_TOKEN_ENV_VAR, "")
    if not plaintext_token:
        # Placeholder for test environments where real token isn't needed
        plaintext_token = "IGAA_placeholder_test_token"
        logger.warning(
            f"{SEED_TOKEN_ENV_VAR} not set — using placeholder token "
            "(API calls to Instagram will fail)"
        )

    # Encrypt the token using the provided session_secret
    encryption = EncryptionService(session_secret)
    encrypted_token = encryption.encrypt(plaintext_token)

    account = Account(
        id=EL_DMYTR_ACCOUNT_ID,
        instagram_account_id=EL_DMYTR_INSTAGRAM_ACCOUNT_ID,
        username=EL_DMYTR_USERNAME,
        messaging_channel_id=EL_DMYTR_MESSAGING_CHANNEL_ID,
        access_token_encrypted=encrypted_token,
        token_expires_at=EL_DMYTR_TOKEN_EXPIRES_AT,
        account_type="business",
    )

    db.add(account)
    await db.flush()
    logger.info(f"Created account {EL_DMYTR_USERNAME} ({EL_DMYTR_ACCOUNT_ID})")
    return account


async def seed_link_user_account(
    db: AsyncSession,
    user_id: int,
    account_id: str
) -> UserAccount:
    """
    Link a user to an account. Idempotent — skips if link already exists.

    Args:
        db: Database session
        user_id: User.id to link
        account_id: Account.id to link

    Returns:
        UserAccount model instance (created or existing)
    """
    result = await db.execute(
        select(UserAccount).where(
            UserAccount.user_id == user_id,
            UserAccount.account_id == account_id
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        logger.info(f"Link already exists: user {user_id} -> account {account_id}")
        return existing

    link = UserAccount(
        user_id=user_id,
        account_id=account_id,
    )
    db.add(link)
    await db.flush()
    logger.info(f"Linked user {user_id} -> account {account_id}")
    return link


async def seed_preconditions(
    db: AsyncSession,
    session_secret: str
) -> dict:
    """
    Orchestrate full test preconditions:
    1. Create next testN user
    2. Ensure @el_dmytr account exists
    3. Link @el_dmytr to the new test user
    4. Commit all changes

    Args:
        db: Database session
        session_secret: SESSION_SECRET for token encryption

    Returns:
        {"user": User, "account": Account}
    """
    # 1. Create next test user (UserService.create_user commits internally)
    user = await seed_test_user(db)

    # 2. Ensure @el_dmytr account exists
    account = await seed_el_dmytr_account(db, session_secret)

    # 3. Link them
    await seed_link_user_account(db, user.id, account.id)

    # 4. Commit account + link (user was already committed by UserService)
    await db.commit()

    return {"user": user, "account": account}
