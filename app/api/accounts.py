"""
CRM Integration API - Account Management Endpoints

Implements account configuration for Instagram business accounts.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from datetime import datetime  # Used in AccountResponse type hint
from typing import Optional
import uuid
import logging
import base64

from app.api.auth import verify_api_key, verify_ui_session
from app.db.connection import get_db_session
from app.db.models import Account, APIKey, UserAccount
from app.services.api_key_service import APIKeyService

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# Pydantic Models (from OpenAPI spec)
# ============================================

class CreateAccountRequest(BaseModel):
    """Request to create a new Instagram account configuration"""
    instagram_account_id: str = Field(..., description="Instagram business account ID")
    username: str = Field(..., description="Instagram username")
    access_token: str = Field(..., description="Instagram Page Access Token")
    crm_webhook_url: str = Field(..., description="CRM endpoint for webhooks")
    webhook_secret: str = Field(..., description="Shared secret for webhook signatures")


class AccountResponse(BaseModel):
    """Account details response (credentials excluded)"""
    account_id: str
    instagram_account_id: str
    username: str
    crm_webhook_url: str
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================
# Simple Encryption (MVP - replace later)
# ============================================
# WARNING: This is NOT real encryption - just base64 encoding!
# Anyone with database access can decode these credentials.
# TODO: Replace with cryptography.fernet in Priority 2 (Task 10)

def encrypt_credential(credential: str) -> str:
    """
    Simple encoding for MVP - just base64 for now.

    WARNING: This is NOT secure encryption. Do not use in production.
    TODO: Replace with real encryption (Fernet) in Priority 2.
    """
    return base64.b64encode(credential.encode()).decode()


def decrypt_credential(encoded_credential: str) -> str:
    """
    Decode base64-encoded credential.

    Mirrors the encrypt_credential function above.
    MVP uses base64 encoding (NOT secure encryption).

    Args:
        encoded_credential: Base64-encoded credential string

    Returns:
        Decoded credential string

    WARNING: This is NOT secure decryption. Do not use in production.
    TODO: Replace with real decryption (Fernet) in Priority 2.
    """
    return base64.b64decode(encoded_credential.encode()).decode()


# ============================================
# Endpoints
# ============================================

@router.post("/accounts", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    request: CreateAccountRequest,
    api_key: APIKey = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a new Instagram account configuration.

    Requires admin API key - account-scoped keys cannot create new accounts.

    Minimal implementation for MVP:
    - Store account with encoded credentials (NOT secure - see warning)
    - Skip Instagram token validation (will add in Priority 2)
    - Return 201 with account_id

    WARNING: Credentials are base64-encoded, NOT encrypted.
    Do not use in production without implementing real encryption (Task 10).
    """
    # Only admin keys can create new accounts
    from app.db.models import APIKeyType
    if api_key.type != APIKeyType.ADMIN:
        logger.warning(f"Permission denied: Non-admin key {api_key.id} attempted to create account")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin API keys can create new accounts"
        )

    logger.info(f"Creating account for Instagram user: {request.username}")
    
    # Check if account already exists
    result = await db.execute(
        select(Account).where(Account.instagram_account_id == request.instagram_account_id)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        logger.warning(f"Account already exists: {request.instagram_account_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Account with instagram_account_id '{request.instagram_account_id}' already exists"
        )
    
    # Generate account ID
    account_id = f"acc_{uuid.uuid4().hex[:12]}"
    
    # Encode credentials (NOT secure - just base64 for MVP)
    encoded_token = encrypt_credential(request.access_token)
    encoded_webhook_secret = encrypt_credential(request.webhook_secret)
    
    # Create account record
    account = Account(
        id=account_id,
        instagram_account_id=request.instagram_account_id,
        username=request.username,
        access_token_encrypted=encoded_token,
        crm_webhook_url=request.crm_webhook_url,
        webhook_secret=encoded_webhook_secret
        # created_at handled by database default (func.now())
    )
    
    db.add(account)
    await db.commit()  # Explicitly commit to ensure account is persisted

    logger.info(f"✅ Account created: {account_id} (@{request.username})")
    
    return AccountResponse(
        account_id=account.id,
        instagram_account_id=account.instagram_account_id,
        username=account.username,
        crm_webhook_url=account.crm_webhook_url,
        created_at=account.created_at
    )


# ============================================
# User Account Management Endpoints (JWT Protected)
# ============================================

class UserAccountInfo(BaseModel):
    """Information about an Instagram account linked to a user"""
    account_id: str
    instagram_account_id: str
    messaging_channel_id: Optional[str]  # Unique channel ID for message routing
    username: str
    profile_picture_url: Optional[str]
    is_primary: bool
    token_expires_at: Optional[datetime]
    linked_at: datetime

    class Config:
        from_attributes = True


class UserAccountsListResponse(BaseModel):
    """Response for listing user's linked accounts"""
    accounts: list[UserAccountInfo]


@router.get("/accounts/me", response_model=UserAccountsListResponse)
async def list_user_accounts(
    session: dict = Depends(verify_ui_session),
    db: AsyncSession = Depends(get_db_session)
):
    """
    List all Instagram accounts linked to the authenticated user.

    Returns account details including primary status and token expiration.
    Requires JWT session authentication.

    Returns:
        UserAccountsListResponse: List of linked Instagram accounts
    """
    user_id = session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session: missing user_id"
        )

    # Query all accounts linked to this user
    result = await db.execute(
        select(UserAccount, Account)
        .join(Account, UserAccount.account_id == Account.id)
        .where(UserAccount.user_id == user_id)
        .order_by(UserAccount.is_primary.desc(), UserAccount.linked_at.desc())
    )
    links = result.all()

    accounts_list = []
    for user_account, account in links:
        accounts_list.append(UserAccountInfo(
            account_id=account.id,
            instagram_account_id=account.instagram_account_id,
            messaging_channel_id=account.messaging_channel_id,
            username=account.username,
            profile_picture_url=account.profile_picture_url,
            is_primary=user_account.is_primary,
            token_expires_at=account.token_expires_at,
            linked_at=user_account.linked_at
        ))

    logger.info(f"Listing {len(accounts_list)} accounts for user {user_id}")

    return UserAccountsListResponse(accounts=accounts_list)


@router.post("/accounts/{account_id}/set-primary")
async def set_primary_account(
    account_id: str,
    session: dict = Depends(verify_ui_session),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Set an account as the user's primary account.

    The primary account is used as the default for sending messages and
    is included in the JWT token.

    Args:
        account_id: Account ID to set as primary

    Returns:
        Success message with updated account list

    Raises:
        HTTPException: 403 if user doesn't own this account
        HTTPException: 404 if account not found
    """
    user_id = session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session: missing user_id"
        )

    # Verify user owns this account
    result = await db.execute(
        select(UserAccount).where(
            UserAccount.user_id == user_id,
            UserAccount.account_id == account_id
        )
    )
    link = result.scalar_one_or_none()

    if not link:
        logger.warning(f"User {user_id} attempted to set primary for account {account_id} they don't own")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this account"
        )

    # Set all user's accounts to non-primary
    result = await db.execute(
        select(UserAccount).where(UserAccount.user_id == user_id)
    )
    all_links = result.scalars().all()

    for user_account in all_links:
        user_account.is_primary = (user_account.account_id == account_id)

    await db.commit()

    logger.info(f"User {user_id} set account {account_id} as primary")

    return {
        "message": "Primary account updated successfully",
        "primary_account_id": account_id
    }


@router.delete("/accounts/{account_id}")
async def unlink_account(
    account_id: str,
    session: dict = Depends(verify_ui_session),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Unlink an Instagram account from the authenticated user.

    If this was the primary account, another account will be automatically
    set as primary (if any remaining accounts exist).

    Args:
        account_id: Account ID to unlink

    Returns:
        Success message

    Raises:
        HTTPException: 403 if user doesn't own this account
        HTTPException: 404 if account link not found
    """
    user_id = session.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session: missing user_id"
        )

    # Verify user owns this account
    result = await db.execute(
        select(UserAccount).where(
            UserAccount.user_id == user_id,
            UserAccount.account_id == account_id
        )
    )
    link = result.scalar_one_or_none()

    if not link:
        logger.warning(f"User {user_id} attempted to unlink account {account_id} they don't own")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this account"
        )

    was_primary = link.is_primary

    # Delete the link
    await db.delete(link)
    await db.commit()

    # If this was primary, set another account as primary
    if was_primary:
        result = await db.execute(
            select(UserAccount)
            .where(UserAccount.user_id == user_id)
            .limit(1)
        )
        next_account = result.scalar_one_or_none()

        if next_account:
            next_account.is_primary = True
            await db.commit()
            logger.info(f"Set account {next_account.account_id} as new primary for user {user_id}")

    logger.info(f"User {user_id} unlinked account {account_id}")

    return {
        "message": "Account unlinked successfully",
        "unlinked_account_id": account_id
    }
