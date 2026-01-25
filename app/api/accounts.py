"""
CRM Integration API - Account Management Endpoints

Implements account configuration for Instagram business accounts.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel, Field
from datetime import datetime  # Used in AccountResponse type hint
from typing import Optional
import uuid
import logging

from app.api.auth import verify_api_key, verify_ui_session, verify_user_account_access, verify_jwt_or_api_key
from app.services.encryption_service import encrypt_credential, decrypt_credential
from app.db.connection import get_db_session
from app.db.models import Account, APIKey, UserAccount, MessageModel, MessageAttachment, CRMOutboundMessage, InstagramProfile
from app.services.api_key_service import APIKeyService
from app.services.account_media_cleanup import AccountMediaCleanup
from app.config import settings

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


class DeleteAccountStatistics(BaseModel):
    """Statistics from account deletion"""
    messages_deleted: int = Field(..., example=1543, description="Number of conversation messages deleted (inbound + outbound)")
    attachments_deleted: int = Field(..., example=87, description="Number of message attachments deleted (database records)")
    inbound_files_deleted: int = Field(..., example=42, description="Number of inbound media files deleted from disk")
    outbound_files_deleted: int = Field(..., example=9, description="Number of outbound media files deleted from disk")
    bytes_freed: int = Field(..., example=157286400, description="Total disk space freed in bytes (~150MB in this example)")


class DeleteAccountResponse(BaseModel):
    """Response from permanent account deletion"""
    message: str = Field(..., description="Success message")
    deleted_account_id: str = Field(..., description="ID of the deleted account")
    statistics: DeleteAccountStatistics = Field(..., description="Deletion statistics")


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

    # Encrypt credentials using Fernet (AES-128 + HMAC-SHA256)
    encoded_token = encrypt_credential(request.access_token, settings.session_secret)
    encoded_webhook_secret = encrypt_credential(request.webhook_secret, settings.session_secret)
    
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
    account_id: str = Field(..., example="acc_a3f7e8b2c1d4")
    instagram_account_id: str = Field(..., example="17841478096518771")
    messaging_channel_id: Optional[str] = Field(None, example="17841478096518771", description="Unique channel ID for message routing")
    username: str = Field(..., example="myshop_official")
    profile_picture_url: Optional[str] = Field(None, example="https://scontent.cdninstagram.com/v/...")
    token_expires_at: Optional[datetime] = Field(None, example="2026-03-06T14:32:00.123Z", description="When OAuth token expires (60 days)")
    linked_at: datetime = Field(..., example="2026-01-06T14:32:00.123Z", description="When account was linked via OAuth")

    class Config:
        from_attributes = True


class UserAccountsListResponse(BaseModel):
    """Response for listing user's linked accounts"""
    accounts: list[UserAccountInfo]


@router.get(
    "/accounts/me",
    response_model=UserAccountsListResponse,
    summary="List user's linked Instagram accounts"
)
async def list_user_accounts(
    auth: dict = Depends(verify_jwt_or_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    List all Instagram accounts linked to the authenticated user.

    Returns account details including:
    - OAuth token expiration (60 days from linking)
    - Instagram username and profile picture
    - Messaging channel ID for webhook routing

    **Accepts both JWT session tokens and API keys.**

    Accounts are sorted by most recently linked first.
    """
    user_id = auth.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session: missing user_id"
        )

    # Query all accounts linked to this user (sorted by most recently linked)
    result = await db.execute(
        select(UserAccount, Account)
        .join(Account, UserAccount.account_id == Account.id)
        .where(UserAccount.user_id == user_id)
        .order_by(UserAccount.linked_at.desc())
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
            token_expires_at=account.token_expires_at,
            linked_at=user_account.linked_at
        ))

    logger.info(f"Listing {len(accounts_list)} accounts for user {user_id}")

    return UserAccountsListResponse(accounts=accounts_list)


@router.delete(
    "/accounts/{account_id}",
    summary="Unlink Instagram account (keeps data)"
)
async def unlink_account(
    account_id: str,
    auth: dict = Depends(verify_jwt_or_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Unlink an Instagram account from the authenticated user.

    **What This Does**:
    - Removes your access to this account
    - Account and all its data remain in the system
    - Other users can still access the account
    - You can re-link the same account later via OAuth

    **What This Does NOT Do**:
    - Does NOT delete the account
    - Does NOT delete messages or media files
    - Does NOT remove the account from other users

    **To permanently delete the account and all data**, use:
    `DELETE /accounts/{account_id}/delete-permanently`

    **Accepts both JWT session tokens and API keys.**
    """
    user_id = auth.get("user_id")

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

    # Delete the link
    await db.delete(link)
    await db.commit()

    logger.info(f"User {user_id} unlinked account {account_id}")

    return {
        "message": "Account unlinked successfully",
        "unlinked_account_id": account_id
    }


@router.delete(
    "/accounts/{account_id}/delete-permanently",
    response_model=DeleteAccountResponse,
    summary="⚠️ Permanently delete account and ALL data",
    responses={
        200: {"description": "Account deleted successfully with statistics"},
        401: {"description": "Not authenticated"},
        403: {"description": "User doesn't have access to this account"},
        404: {"description": "Account not found"},
        500: {"description": "Server error during deletion"}
    }
)
async def delete_account_permanently(
    account_id: str,
    auth: dict = Depends(verify_jwt_or_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Permanently delete an Instagram account and ALL associated data.

    ## ⚠️ WARNING: This action is irreversible!

    ## What Gets Deleted

    This operation removes ALL data associated with the account:
    - ✅ Account record and encrypted OAuth token
    - ✅ All conversation messages (inbound/outbound)
    - ✅ All message attachments (database + files)
    - ✅ All media files (inbound attachments + outbound uploads)
    - ✅ CRM outbound tracking records
    - ✅ API key permissions for this account
    - ✅ User-account links
    - ✅ Instagram profile cache (only profiles unique to this account)

    ## Multi-User Behavior

    - **If other users have this account linked**: Your access is removed (unlink),
      but data is preserved for other users. Returns success with zero statistics.
    - **If you're the only user**: Account and all data are permanently deleted.

    ## Unlink vs Delete Permanently

    | Action | Data Kept? | Account Remains? | Can Re-link? |
    |--------|-----------|------------------|--------------|
    | **Unlink** (`DELETE /accounts/{id}`) | ✅ Yes | ✅ Yes | ✅ Yes |
    | **Delete Permanently** (`DELETE /accounts/{id}/delete-permanently`) | ❌ No | ❌ No | ❌ No |

    **When to use Unlink**:
    - You want to stop accessing this account temporarily
    - Other users still need access
    - You might want to re-link it later

    **When to use Delete Permanently**:
    - You're switching to a different account permanently
    - You want to remove all data for privacy/GDPR compliance
    - No other users need this account

    ## Example Response

    ```json
    {
      "message": "Account deleted successfully",
      "deleted_account_id": "acc_a3f7e8b2c1d4",
      "statistics": {
        "messages_deleted": 1543,
        "attachments_deleted": 87,
        "inbound_files_deleted": 42,
        "outbound_files_deleted": 9,
        "bytes_freed": 157286400
      }
    }
    ```

    ## Example Request

    ```bash
    curl -X DELETE "https://api.example.com/api/v1/accounts/acc_a3f7e8b2c1d4/delete-permanently" \\
      -H "Authorization: Bearer eyJ..."
    ```

    **Accepts both JWT session tokens and API keys.**
    """
    user_id = auth.get("user_id")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid session: missing user_id"
        )

    # Step 1: Verify user owns this account
    result = await db.execute(
        select(UserAccount).where(
            UserAccount.user_id == user_id,
            UserAccount.account_id == account_id
        )
    )
    link = result.scalar_one_or_none()

    if not link:
        logger.warning(
            f"User {user_id} attempted to delete account {account_id} they don't own"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this account"
        )

    # Step 2: Load account to verify it exists
    result = await db.execute(
        select(Account).where(Account.id == account_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Account {account_id} not found"
        )

    # Step 3: Multi-user safety check
    result = await db.execute(
        select(func.count(UserAccount.user_id))
        .where(UserAccount.account_id == account_id)
    )
    user_count = result.scalar()

    if user_count > 1:
        # Multiple users have this account - unlink current user instead of blocking
        logger.info(
            f"User {user_id} requested delete of multi-user account {account_id} "
            f"({user_count} users linked) - unlinking instead"
        )

        # Delete the user's link to this account
        await db.delete(link)
        await db.commit()

        return DeleteAccountResponse(
            message="Account unlinked (other users have access, data preserved)",
            deleted_account_id=account_id,
            statistics=DeleteAccountStatistics(
                messages_deleted=0,
                attachments_deleted=0,
                inbound_files_deleted=0,
                outbound_files_deleted=0,
                bytes_freed=0
            )
        )

    # Step 4: Gather statistics BEFORE deletion
    # Count messages
    result = await db.execute(
        select(func.count(MessageModel.id))
        .where(MessageModel.account_id == account_id)
    )
    messages_count = result.scalar() or 0

    # Count attachments
    result = await db.execute(
        select(func.count(MessageAttachment.id))
        .select_from(MessageAttachment)
        .join(MessageModel, MessageAttachment.message_id == MessageModel.id)
        .where(MessageModel.account_id == account_id)
    )
    attachments_count = result.scalar() or 0

    # Step 5: Begin transaction for deletion
    try:
        # Clean up media files BEFORE deleting database records
        # (we need the DB records to know which files to delete)
        media_cleanup = AccountMediaCleanup(settings.MEDIA_DIR)
        media_stats = await media_cleanup.cleanup_account_media(account_id, db)

        # Clean up Instagram profile cache for this account
        # Delete cached profiles that only appear in this account's messages
        # (keep profiles that are referenced by other accounts)
        result = await db.execute(
            select(MessageModel.sender_id, MessageModel.recipient_id)
            .where(MessageModel.account_id == account_id)
            .distinct()
        )
        account_user_ids = set()
        for row in result:
            account_user_ids.add(row.sender_id)
            account_user_ids.add(row.recipient_id)

        # For each user_id from this account's messages, check if it appears
        # in OTHER accounts' messages. Only delete if it doesn't.
        profiles_to_delete = []
        for user_id in account_user_ids:
            result = await db.execute(
                select(func.count(MessageModel.id))
                .where(
                    MessageModel.account_id != account_id,
                    (MessageModel.sender_id == user_id) | (MessageModel.recipient_id == user_id)
                )
            )
            count_in_other_accounts = result.scalar() or 0

            if count_in_other_accounts == 0:
                # This user_id only appears in this account's messages
                profiles_to_delete.append(user_id)

        # Delete the orphaned profiles
        if profiles_to_delete:
            result = await db.execute(
                select(InstagramProfile)
                .where(InstagramProfile.sender_id.in_(profiles_to_delete))
            )
            profiles = result.scalars().all()
            for profile in profiles:
                await db.delete(profile)
            logger.info(
                f"Deleting {len(profiles)} Instagram profile cache entries for account {account_id}"
            )

        # Step 6: Delete account record
        # Database CASCADE constraints will handle deletion of:
        # - CRMOutboundMessage records
        # - MessageModel records (which cascades to MessageAttachment)
        # - APIKeyPermission records
        # - UserAccount records
        await db.delete(account)
        await db.commit()

        # Step 7: Log successful deletion
        logger.warning(
            f"Account {account_id} (@{account.username}) permanently deleted by user {user_id}",
            extra={
                "account_id": account_id,
                "username": account.username,
                "user_id": user_id,
                "messages_deleted": messages_count,
                "attachments_deleted": attachments_count,
                "profiles_deleted": len(profiles_to_delete),
                "inbound_files_deleted": media_stats["inbound_files_deleted"],
                "outbound_files_deleted": media_stats["outbound_files_deleted"],
                "bytes_freed": media_stats["total_bytes_freed"],
                "action": "account_deletion"
            }
        )

        # Step 8: Return success with statistics
        return DeleteAccountResponse(
            message="Account deleted successfully",
            deleted_account_id=account_id,
            statistics=DeleteAccountStatistics(
                messages_deleted=messages_count,
                attachments_deleted=attachments_count,
                inbound_files_deleted=media_stats["inbound_files_deleted"],
                outbound_files_deleted=media_stats["outbound_files_deleted"],
                bytes_freed=media_stats["total_bytes_freed"]
            )
        )

    except HTTPException:
        # Re-raise HTTP exceptions (auth errors, etc.)
        await db.rollback()
        raise
    except Exception as e:
        # Rollback transaction on any error
        await db.rollback()
        logger.error(
            f"Failed to delete account {account_id}: {e}",
            exc_info=True,
            extra={
                "account_id": account_id,
                "user_id": user_id,
                "error": str(e)
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account. Please try again or contact support."
        )
