"""
UI API endpoints for the web frontend
Provides conversation lists and message retrieval for the Vue chat interface

Authentication:
- POST /ui/session: Validates Basic Auth credentials, returns JWT token
- All other /ui/* endpoints: Protected by JWT token validation

Refactored to use centralized cache service.
"""
import logging
import httpx
import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, and_, case
from sqlalchemy.orm import selectinload
from pydantic import BaseModel, Field
from app.db.connection import get_db_session
from app.db.models import MessageModel, APIKey, UserAccount, Account
from app.clients.instagram_client import InstagramClient
from app.config import settings
from app.api.auth import verify_api_key, verify_ui_session, verify_jwt_or_api_key, LoginRequest
from app.services.user_service import UserService
from app.infrastructure.cache_service import get_cached_username
from app.api.events import sse_manager
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# Background Tasks
# ============================================

async def refresh_user_profile_pictures(user_id: int):
    """
    Background task to refresh profile pictures for all user's Instagram accounts.

    Fetches fresh profile picture URLs from Instagram API and broadcasts updates via SSE.
    Called asynchronously after successful login to ensure profile pics are current.
    """
    from app.db.connection import get_db_session_context
    from app.services.encryption_service import decrypt_credential

    async with get_db_session_context() as db:
        # Get all accounts linked to this user
        result = await db.execute(
            select(UserAccount, Account).join(
                Account, UserAccount.account_id == Account.id
            ).where(UserAccount.user_id == user_id)
        )
        user_accounts = result.all()

        if not user_accounts:
            logger.debug(f"No accounts to refresh for user {user_id}")
            return

        logger.info(f"Refreshing profile pictures for {len(user_accounts)} accounts (user_id={user_id})")

        for user_account, account in user_accounts:
            try:
                # Skip if no access token
                if not account.access_token_encrypted:
                    logger.debug(f"Account {account.id} has no access token, skipping profile refresh")
                    continue

                # Decrypt access token
                access_token = decrypt_credential(
                    account.access_token_encrypted,
                    settings.session_secret
                )

                # Create Instagram client and fetch fresh profile
                async with httpx.AsyncClient() as http_client:
                    instagram_client = InstagramClient(http_client, access_token)
                    fresh_profile = await instagram_client.get_business_account_profile(
                        account.instagram_account_id
                    )

                if fresh_profile and fresh_profile.get("profile_picture_url"):
                    old_url = account.profile_picture_url
                    new_url = fresh_profile["profile_picture_url"]

                    # Only update if URL changed
                    if old_url != new_url:
                        account.profile_picture_url = new_url
                        await db.commit()

                        logger.info(f"Updated profile picture for account {account.id} (@{account.username})")

                        # Broadcast update via SSE
                        await sse_manager.broadcast("account_updated", {
                            "account_id": account.id,
                            "profile_picture_url": new_url,
                            "username": account.username
                        })
                    else:
                        logger.debug(f"Profile picture unchanged for account {account.id}")
                else:
                    logger.debug(f"No profile picture in API response for account {account.id}")

            except Exception as e:
                logger.warning(f"Failed to refresh profile for account {account.id}: {e}")
                # Continue with other accounts


# ============================================
# Response Models
# ============================================

class SessionResponse(BaseModel):
    """UI session creation response"""
    token: str = Field(..., example="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...", description="JWT token for subsequent requests")
    user_id: int = Field(..., example=1, description="User ID")
    username: str = Field(..., example="admin", description="Username")
    expires_in: int = Field(..., example=86400, description="Token expiration time in seconds (24 hours)")

    class Config:
        from_attributes = True


class CurrentAccountResponse(BaseModel):
    """Current account information"""
    account_id: Optional[str] = Field(None, example="acc_a3f7e8b2c1d4")
    instagram_account_id: str = Field(..., example="17841478096518771")
    username: str = Field(..., example="@myshop_official", description="Instagram username with @ prefix")
    instagram_handle: Optional[str] = Field(None, example="myshop_official", description="Raw username without @ prefix")
    profile_picture_url: Optional[str] = Field(None, example="https://scontent.cdninstagram.com/v/...")

    class Config:
        from_attributes = True


class ConversationItem(BaseModel):
    """Single conversation in list"""
    sender_id: str = Field(..., example="25964748486442669", description="Customer's Instagram user ID")
    sender_name: str = Field(..., example="@johndoe", description="Customer's Instagram username")
    profile_picture_url: Optional[str] = Field(None, example="https://scontent.cdninstagram.com/v/...")
    last_message: str = Field(..., example="Hello, I have a question about my order", description="Most recent message text")
    last_message_time: str = Field(..., example="2026-01-06T14:32:00.123Z", description="ISO 8601 timestamp")
    unread_count: int = Field(..., example=0, description="Number of unread messages (always 0 in MVP)")
    messaging_channel_id: str = Field(..., example="17841478096518771", description="Messaging channel ID for this conversation")
    account_id: str = Field(..., example="acc_a3f7e8b2c1d4", description="Account ID this conversation belongs to")

    class Config:
        from_attributes = True


class ConversationsResponse(BaseModel):
    """List of conversations"""
    conversations: List[ConversationItem] = Field(..., description="Conversations sorted by most recent first")

    class Config:
        from_attributes = True


class MessageAttachmentInfo(BaseModel):
    """Message attachment information"""
    id: str = Field(..., example="mid_abc123_0", description="Unique attachment ID")
    media_type: str = Field(..., example="image", description="Attachment type: image | video | audio")
    media_url: Optional[str] = Field(None, example="https://scontent.cdninstagram.com/v/...", description="Instagram CDN URL (expires in 7 days)")
    media_url_local: Optional[str] = Field(None, example="media/inbound/acc_123/sender_456/mid_abc123_0.jpg", description="Local file path (authenticated)")
    media_mime_type: Optional[str] = Field(None, example="image/jpeg", description="MIME type of downloaded file")

    class Config:
        from_attributes = True


class MessageInfo(BaseModel):
    """Single message information"""
    id: str = Field(..., example="mid_abc123", description="Instagram message ID")
    text: str = Field(..., example="Hello! I have a question.", description="Message text (empty string for media-only messages)")
    direction: str = Field(..., example="inbound", description="Message direction: inbound (from customer) | outbound (from you)")
    timestamp: str = Field(..., example="2026-01-06T14:32:00.123Z", description="ISO 8601 timestamp")
    status: Optional[str] = Field(None, example="sent", description="Delivery status for outbound messages")
    attachments: List[MessageAttachmentInfo] = Field(default_factory=list, description="Media attachments")

    class Config:
        from_attributes = True


class SenderInfo(BaseModel):
    """Conversation sender information"""
    id: str = Field(..., example="25964748486442669", description="Instagram user ID")
    name: str = Field(..., example="@johndoe", description="Instagram username")

    class Config:
        from_attributes = True


class MessagesResponse(BaseModel):
    """Conversation messages with sender info"""
    messages: List[MessageInfo] = Field(..., description="Messages in chronological order (oldest first)")
    sender_info: SenderInfo = Field(..., description="Information about the conversation partner")

    class Config:
        from_attributes = True


# ============================================
# Session Authentication Endpoint
# ============================================


@router.post(
    "/ui/session",
    response_model=SessionResponse,
    summary="Create UI session token (login)",
    responses={
        200: {"description": "Login successful, JWT token returned"},
        401: {
            "description": "Authentication failed",
            "content": {
                "application/json": {
                    "examples": {
                        "missing_auth": {
                            "summary": "Missing Authorization header",
                            "value": {"detail": "Missing Basic Auth credentials"}
                        },
                        "invalid_credentials": {
                            "summary": "Wrong username or password",
                            "value": {"detail": "Invalid username or password"}
                        },
                        "malformed_auth": {
                            "summary": "Invalid Base64 encoding",
                            "value": {"detail": "Invalid Basic Auth format"}
                        }
                    }
                }
            }
        }
    }
)
async def create_session(
    request: LoginRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a UI session token (JWT) by validating username and password.

    **How to Login**:

    1. Send username and password in JSON body
    2. Receive JWT token in response
    3. Use JWT token for subsequent requests: `Bearer <jwt-token>`

    **Example (curl)**:
    ```bash
    curl -X POST "https://api.example.com/api/v1/ui/session" \\
      -H "Content-Type: application/json" \\
      -d '{"username": "admin", "password": "mypassword"}'
    ```

    **Example (JavaScript)**:
    ```javascript
    const response = await fetch('/api/v1/ui/session', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({username: 'admin', password: 'mypassword'})
    });
    const { token, account_id } = await response.json();
    ```

    **Example (Python)**:
    ```python
    import requests

    response = requests.post(
        'https://api.example.com/api/v1/ui/session',
        json={'username': 'admin', 'password': 'mypassword'}
    )
    token = response.json()['token']
    ```

    **Token Usage**:
    Store the returned JWT token and use it in subsequent requests:
    ```
    Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
    ```

    **Token Expiration**:
    - Default: 24 hours (86400 seconds)
    - Check `expires_in` field for exact duration
    - Login again when token expires (401 error)
    """
    # Extract credentials from JSON body
    username = request.username
    password = request.password

    # Validate credentials against database
    user = await UserService.validate_credentials(db, username, password)

    if not user:
        logger.warning(f"Session creation failed: Invalid credentials for username '{username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
            # NOTE: No WWW-Authenticate header to avoid browser/nginx auth popup
        )

    # Create JWT with user context only (no account_id - frontend manages selection)
    expiration_time = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiration_hours)
    payload = {
        "user_id": user.id,
        "username": user.username,
        "exp": expiration_time,
        "type": "ui_session"
    }

    # Generate JWT token
    token = jwt.encode(
        payload,
        settings.session_secret,
        algorithm=settings.jwt_algorithm
    )

    logger.info(f"Created UI session for user '{user.username}' (id={user.id})")

    # Trigger async profile picture refresh in background
    # This ensures profile pics are fresh without delaying login response
    background_tasks.add_task(refresh_user_profile_pictures, user.id)

    return SessionResponse(
        token=token,
        user_id=user.id,
        username=user.username,
        expires_in=settings.jwt_expiration_hours * 3600  # Convert hours to seconds
    )


# ============================================
# UI Data Endpoints (JWT Protected)
# ============================================


@router.get(
    "/ui/account/me",
    response_model=CurrentAccountResponse,
    summary="Get current user's account info"
)
async def get_current_account(
    account_id: Optional[str] = Query(None, description="Instagram account ID. If not provided, uses user's primary account."),
    auth: dict = Depends(verify_jwt_or_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get current user's Instagram account information.

    Returns account details including username, profile picture, and messaging channel ID.

    **Query Parameters**:
    - `account_id` (optional): Specific account to fetch. If not provided, uses first linked account.

    **Response Fields**:
    - `account_id`: Your account ID (e.g., acc_a3f7e8b2c1d4)
    - `instagram_account_id`: Instagram's business account ID
    - `username`: Instagram username with @ prefix
    - `instagram_handle`: Raw username without @ prefix
    - `profile_picture_url`: Profile picture URL from Instagram CDN

    **Accepts both JWT session tokens and API keys.**
    """
    try:
        user_id = auth.get("user_id")

        # If no account_id provided, use first linked account as fallback
        if not account_id:
            # Query database for user's first account (most recently linked)
            result = await db.execute(
                select(UserAccount).where(
                    UserAccount.user_id == user_id
                ).order_by(UserAccount.linked_at.desc()).limit(1)
            )
            first_link = result.scalar_one_or_none()

            if first_link:
                account_id = first_link.account_id
                logger.info(f"User {user_id} - no account_id provided, using first account: {account_id}")
            else:
                # User truly has no linked accounts yet
                logger.info(f"User {user_id} has no linked accounts")
                return CurrentAccountResponse(
                    account_id=None,
                    instagram_account_id="",
                    username="No account linked",
                    instagram_handle=None,
                    profile_picture_url=None
                )

        # Verify user has access to this account
        result = await db.execute(
            select(UserAccount).where(
                UserAccount.user_id == user_id,
                UserAccount.account_id == account_id
            )
        )
        user_account_link = result.scalar_one_or_none()

        if not user_account_link:
            logger.warning(f"User {user_id} attempted to access account info for {account_id} without permission")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this account"
            )

        # Get account from database
        result = await db.execute(
            select(Account).where(Account.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            logger.error(f"Account {account_id} not found in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )

        business_account_id = account.instagram_account_id

        # Use cached profile data from database (fetched during OAuth)
        # This works for both Instagram Business and Basic Display accounts
        # We already fetch and store this data during the OAuth callback
        username = account.username or business_account_id
        profile_pic_url = account.profile_picture_url

        logger.info(f"✅ Account info: @{username}, has_pic={bool(profile_pic_url)}")

        return CurrentAccountResponse(
            account_id=account_id,
            instagram_account_id=business_account_id,
            username=f"@{username}" if username else f"@{business_account_id}",
            instagram_handle=username or business_account_id,
            profile_picture_url=profile_pic_url
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch current account info: {e}", exc_info=True)
        return CurrentAccountResponse(
            account_id=None,
            instagram_account_id="",
            username="Error loading account",
            instagram_handle=None,
            profile_picture_url=None
        )


async def _get_instagram_username(sender_id: str, access_token: str = None, is_business_account: bool = False) -> str:
    """
    Get Instagram username for a sender ID.
    Uses centralized TTL cache to avoid repeated API calls.

    Args:
        sender_id: Instagram user ID
        access_token: Instagram access token for API calls. If not provided, returns sender_id.
        is_business_account: If True, always fetch (business accounts change less frequently but need fresh data)

    Returns:
        Username in @username format, or user_id if fetch fails
    """
    # If no access token provided, return sender_id (can't fetch from API)
    if not access_token:
        return sender_id

    # Define async fetch function for cache
    async def fetch_from_api(user_id: str) -> str:
        """Fetch username from Instagram API"""
        try:
            async with httpx.AsyncClient() as http_client:
                instagram_client = InstagramClient(
                    http_client=http_client,
                    access_token=access_token,
                    logger_instance=logger
                )
                profile = await instagram_client.get_user_profile(user_id)

                if profile and "username" in profile:
                    return f"@{profile['username']}"
        except Exception as e:
            logger.warning(f"Failed to fetch username for {user_id}: {e}")
        return None

    # Use centralized cache service
    username = await get_cached_username(sender_id, fetch_func=fetch_from_api)
    return username or sender_id  # Fallback to sender_id if fetch fails


async def _get_instagram_profile(sender_id: str, access_token: str = None) -> dict:
    """
    Get Instagram profile data for a sender ID.

    Args:
        sender_id: Instagram user ID (IGID scoped to messaging channel)
        access_token: Optional account-specific access token. If not provided, uses global settings token (legacy).

    Returns:
        Dictionary with username and profile_picture_url, or default values if fetch fails
    """
    # Fetch from Instagram API
    try:
        async with httpx.AsyncClient() as http_client:
            # Use account-specific token if provided (multi-account), otherwise fallback to global settings
            if access_token:
                instagram_client = InstagramClient(
                    http_client=http_client,
                    access_token=access_token,
                    logger_instance=logger
                )
            else:
                instagram_client = InstagramClient(
                    http_client=http_client,
                    settings=settings,
                    logger_instance=logger
                )

            profile = await instagram_client.get_user_profile(sender_id)

            if profile and "username" in profile:
                return {
                    "username": f"@{profile['username']}",
                    # Note: Field name is 'profile_pic' for ISGIDs, 'profile_picture_url' for business accounts
                    "profile_picture_url": profile.get("profile_pic") or profile.get("profile_picture_url")
                }
    except Exception as e:
        logger.warning(f"Failed to fetch profile for {sender_id}: {e}")

    # Fallback
    return {
        "username": sender_id,
        "profile_picture_url": None
    }


@router.get(
    "/ui/conversations",
    response_model=ConversationsResponse,
    summary="Get conversation list",
    responses={
        200: {"description": "Conversations retrieved successfully"},
        400: {"description": "Account has no messaging channel bound yet"},
        403: {"description": "No permission to access this account"},
        404: {"description": "Account not found"}
    }
)
async def get_conversations(
    account_id: Optional[str] = Query(None, description="Instagram account ID to filter by"),
    auth: dict = Depends(verify_jwt_or_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get list of all conversations.

    **Authentication:** API key or JWT token

    **Request:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/ui/conversations?account_id=acc_a3f7e8b2c1d4" \\
      -H "Authorization: Bearer YOUR_API_KEY"
    ```

    **Response:**
    ```json
    {
      "conversations": [
        {
          "sender_id": "17841478096518771",
          "sender_name": "@johndoe",
          "profile_picture_url": "https://...",
          "last_message": "Hello!",
          "last_message_time": "2026-01-12T10:00:00Z",
          "unread_count": 0
        }
      ]
    }
    ```
    """
    try:
        user_id = auth.get("user_id")

        # If no account_id provided, use primary account from auth
        if not account_id:
            account_id = auth.get("account_id")  # From query param or API key context
            if not account_id:
                # User has no linked accounts yet
                logger.info(f"User {user_id} has no linked accounts, returning empty conversations")
                return ConversationsResponse(conversations=[])

        # Verify user has access to this account
        result = await db.execute(
            select(UserAccount).where(
                UserAccount.user_id == user_id,
                UserAccount.account_id == account_id
            )
        )
        user_account_link = result.scalar_one_or_none()

        if not user_account_link:
            logger.warning(f"User {user_id} attempted to access conversations for account {account_id} without permission")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this account"
            )

        # Get the messaging_channel_id from Account table
        result = await db.execute(
            select(Account).where(Account.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            logger.error(f"Account {account_id} not found in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )

        messaging_channel_id = account.messaging_channel_id

        if not messaging_channel_id:
            logger.warning(f"Account {account_id} has no messaging_channel_id bound yet")
            # Return empty conversations if channel not bound yet
            return ConversationsResponse(conversations=[])

        # Subquery to get the latest message for each contact (customer)
        # A conversation is identified by the contact's Instagram ID
        # Latest message can be either inbound (from contact) or outbound (to contact)
        # Contact ID is:
        #   - sender_id if direction='inbound'
        #   - recipient_id if direction='outbound'
        subq = (
            select(
                case(
                    (MessageModel.direction == 'inbound', MessageModel.sender_id),
                    else_=MessageModel.recipient_id
                ).label('contact_id'),
                func.max(MessageModel.id).label('latest_message_id')
            )
            .where(
                or_(
                    # Inbound to this channel
                    and_(
                        MessageModel.direction == 'inbound',
                        MessageModel.recipient_id == messaging_channel_id
                    ),
                    # Outbound from this channel
                    and_(
                        MessageModel.direction == 'outbound',
                        MessageModel.sender_id == messaging_channel_id
                    )
                )
            )
            .group_by('contact_id')
            .subquery()
        )

        # Join to get full message details
        # Match on contact_id AND message ID to get the actual latest message
        stmt = (
            select(MessageModel)
            .join(
                subq,
                and_(
                    or_(
                        and_(MessageModel.direction == 'inbound', MessageModel.sender_id == subq.c.contact_id),
                        and_(MessageModel.direction == 'outbound', MessageModel.recipient_id == subq.c.contact_id)
                    ),
                    MessageModel.id == subq.c.latest_message_id
                )
            )
            .where(subq.c.contact_id != messaging_channel_id)  # Exclude self-messages
            .order_by(desc(MessageModel.timestamp))
        )

        result = await db.execute(stmt)
        messages = result.scalars().all()

        # Debug logging to understand what conversations are found
        contact_ids_found = [
            msg.sender_id if msg.direction == 'inbound' else msg.recipient_id
            for msg in messages
        ]
        logger.info(f"🔍 Conversations query for account {account_id} (channel:{messaging_channel_id}): Found {len(messages)} conversations with contact_ids: {contact_ids_found}")

        # Decrypt account access token for profile fetching
        from app.services.encryption_service import decrypt_credential
        try:
            access_token = decrypt_credential(account.access_token_encrypted, settings.session_secret) if account.access_token_encrypted else None
        except Exception as e:
            logger.warning(f"Failed to decrypt access token for account {account_id}: {e}")
            access_token = None

        # Batch fetch profiles in parallel to avoid N+1 query problem
        # Collect unique contact IDs (sender for inbound, recipient for outbound)
        unique_contact_ids = list(set(
            msg.sender_id if msg.direction == 'inbound' else msg.recipient_id
            for msg in messages
        ))

        # Fetch all profiles concurrently using account-specific token
        import asyncio
        profile_tasks = [_get_instagram_profile(contact_id, access_token) for contact_id in unique_contact_ids]
        profiles = await asyncio.gather(*profile_tasks)

        # Create contact_id -> profile mapping
        profile_map = dict(zip(unique_contact_ids, profiles))

        conversations = []
        for msg in messages:
            # Determine contact ID based on message direction
            # For inbound: contact is the sender
            # For outbound: contact is the recipient
            contact_id = msg.sender_id if msg.direction == 'inbound' else msg.recipient_id
            channel_id = msg.recipient_id if msg.direction == 'inbound' else msg.sender_id

            # Get profile from pre-fetched map
            profile = profile_map.get(contact_id, {"username": contact_id, "profile_picture_url": None})

            # Ensure msg.timestamp is timezone-aware (assume UTC if naive)
            msg_timestamp = msg.timestamp
            if msg_timestamp.tzinfo is None:
                msg_timestamp = msg_timestamp.replace(tzinfo=timezone.utc)

            conversations.append({
                "sender_id": contact_id,  # The contact (customer) ID
                "sender_name": profile["username"],
                "profile_picture_url": profile["profile_picture_url"],
                "last_message": msg.message_text or "",
                "last_message_time": msg_timestamp.isoformat() if msg_timestamp else None,
                "unread_count": 0,  # TODO: Implement read/unread tracking
                "messaging_channel_id": channel_id,  # The messaging channel
                "account_id": account_id  # The database account ID (e.g., acc_xxx)
            })

        return ConversationsResponse(conversations=conversations)

    except Exception as e:
        logger.error(f"Failed to fetch conversations: {e}")
        return ConversationsResponse(conversations=[])


@router.get(
    "/ui/messages/{sender_id}",
    response_model=MessagesResponse,
    summary="Get conversation messages"
)
async def get_messages(
    sender_id: str,
    account_id: Optional[str] = Query(None, description="Instagram account ID to filter by"),
    auth: dict = Depends(verify_jwt_or_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get message history for a conversation.

    **Authentication:** API key or JWT token

    **Request:**
    ```bash
    curl -X GET "http://localhost:8000/api/v1/ui/messages/17841478096518771?account_id=acc_a3f7e8b2c1d4" \\
      -H "Authorization: Bearer YOUR_API_KEY"
    ```

    **Response:**
    ```json
    {
      "messages": [
        {
          "id": "msg_123",
          "text": "Hello!",
          "direction": "inbound",
          "timestamp": "2026-01-12T09:00:00Z",
          "attachments": []
        },
        {
          "id": "msg_124",
          "text": "Hi there!",
          "direction": "outbound",
          "timestamp": "2026-01-12T09:05:00Z",
          "attachments": []
        }
      ],
      "sender_info": {
        "id": "17841478096518771",
        "name": "@johndoe"
      }
    }
    ```
    """
    try:
        user_id = auth.get("user_id")

        # If no account_id provided, use primary account from auth
        if not account_id:
            account_id = auth.get("account_id")  # From query param or API key context
            if not account_id:
                # User has no linked accounts yet
                logger.warning(f"User {user_id} has no linked accounts, cannot fetch messages")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No account linked. Please link an Instagram account first."
                )

        # Verify user has access to this account
        result = await db.execute(
            select(UserAccount).where(
                UserAccount.user_id == user_id,
                UserAccount.account_id == account_id
            )
        )
        user_account_link = result.scalar_one_or_none()

        if not user_account_link:
            logger.warning(f"User {user_id} attempted to access messages for account {account_id} without permission")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You don't have access to this account"
            )

        # Get the messaging_channel_id from Account table
        result = await db.execute(
            select(Account).where(Account.id == account_id)
        )
        account = result.scalar_one_or_none()

        if not account:
            logger.error(f"Account {account_id} not found in database")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Account not found"
            )

        messaging_channel_id = account.messaging_channel_id

        if not messaging_channel_id:
            logger.warning(f"Account {account_id} has no messaging_channel_id bound yet")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Account has no messaging channel bound yet. Please receive a message first."
            )

        # Decrypt account access token for profile fetching
        from app.services.encryption_service import decrypt_credential
        try:
            access_token = decrypt_credential(account.access_token_encrypted, settings.session_secret) if account.access_token_encrypted else None
        except Exception as e:
            logger.warning(f"Failed to decrypt access token for account {account_id}: {e}")
            access_token = None

        # Get all messages for this conversation thread (both inbound and outbound)
        # Simple approach: Filter by account_id and conversation participant (sender_id)
        # This handles all cases regardless of which Instagram ID was used
        stmt = (
            select(MessageModel)
            .options(selectinload(MessageModel.attachments))  # Eagerly load attachments
            .where(
                MessageModel.account_id == account_id,
                or_(
                    MessageModel.sender_id == sender_id,
                    MessageModel.recipient_id == sender_id
                )
            )
            .order_by(MessageModel.timestamp.desc())  # Get most recent first
            .limit(100)  # Limit to 100 most recent messages
        )

        result = await db.execute(stmt)
        # Reverse to get chronological order (oldest to newest) for UI display
        messages = list(reversed(result.scalars().all()))

        message_list = []
        sender_info = None

        for msg in messages:
            # Build attachments list
            attachments_data = []
            for att in msg.attachments:
                attachments_data.append({
                    "id": att.id,
                    "media_type": att.media_type,
                    "media_url": att.media_url,
                    "media_url_local": att.media_url_local,
                    "media_mime_type": att.media_mime_type
                })

            message_list.append({
                "id": msg.id,
                "text": msg.message_text or "",
                "direction": msg.direction,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "status": getattr(msg, 'status', None),
                "attachments": attachments_data
            })

            # Capture sender info from first message
            if sender_info is None:
                sender_name = await _get_instagram_username(msg.sender_id, access_token)
                sender_info = {
                    "id": msg.sender_id,
                    "name": sender_name
                }

        if sender_info is None:
            sender_name = await _get_instagram_username(sender_id, access_token)
            sender_info = {
                "id": sender_id,
                "name": sender_name
            }

        return MessagesResponse(
            messages=message_list,
            sender_info=SenderInfo(**sender_info)
        )

    except Exception as e:
        logger.error(f"Failed to fetch messages for {sender_id}: {e}")
        # In exception handler, we don't have access_token available, so use sender_id as fallback
        return MessagesResponse(
            messages=[],
            sender_info=SenderInfo(id=sender_id, name=sender_id)
        )


@router.get(
    "/ui/proxy-image",
    summary="Proxy Instagram CDN images (bypass CORS)"
)
async def proxy_instagram_image(
    url: str = Query(..., description="Instagram CDN image URL to proxy")
):
    """
    Proxy Instagram CDN images to bypass CORS and referrer restrictions.

    **Problem**:
    Instagram CDN blocks direct image loading from external sites due to:
    - Referrer policy restrictions (Instagram CDN checks the Referer header)
    - CORS headers (no Access-Control-Allow-Origin)
    - User-Agent requirements

    **Solution**:
    This endpoint fetches the image server-side and serves it to the frontend,
    bypassing these restrictions.

    **Security**:
    - Only allows Instagram CDN URLs (whitelist: `https://scontent.cdninstagram.com/`)
    - Returns 400 for non-Instagram URLs
    - No authentication required (see below)

    **Why No Authentication**:
    - Only proxies public Instagram CDN URLs
    - Browser `<img>` tags don't send JWT tokens
    - Instagram profile pictures are already public data
    - Authentication would break image rendering in HTML

    **Usage Example**:
    ```html
    <!-- Direct (won't work - CORS blocked) -->
    <img src="https://scontent.cdninstagram.com/v/..." />

    <!-- Via proxy (works!) -->
    <img src="/api/v1/ui/proxy-image?url=https://scontent.cdninstagram.com/v/..." />
    ```

    **JavaScript Example**:
    ```javascript
    const instagramUrl = "https://scontent.cdninstagram.com/v/...";
    const proxyUrl = `/api/v1/ui/proxy-image?url=${encodeURIComponent(instagramUrl)}`;
    document.querySelector('img').src = proxyUrl;
    ```

    **Caching**:
    - Images cached for 24 hours (Cache-Control: public, max-age=86400)
    - Reduces load on Instagram CDN
    - Improves frontend performance
    """
    # Security: Only allow Instagram CDN URLs
    if not url.startswith("https://scontent.cdninstagram.com/"):
        logger.warning(f"Rejected non-Instagram URL: {url}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Instagram CDN URLs are allowed"
        )

    try:
        # Fetch image from Instagram CDN with proper headers
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                }
            )

            if response.status_code != 200:
                logger.warning(f"Failed to fetch image from Instagram CDN: {response.status_code}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Image not found or no longer available"
                )

            # Return image with caching headers
            # Note: Referrer-Policy and X-Content-Type-Options help Firefox compatibility
            return Response(
                content=response.content,
                media_type=response.headers.get("content-type", "image/jpeg"),
                headers={
                    "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
                    "Access-Control-Allow-Origin": "*",  # Allow CORS
                    "Referrer-Policy": "no-referrer",  # Prevent referrer leaking to CDN
                    "X-Content-Type-Options": "nosniff",  # Security header
                }
            )

    except httpx.TimeoutException:
        logger.error(f"Timeout fetching image from Instagram CDN")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Timeout fetching image"
        )
    except Exception as e:
        logger.error(f"Error proxying image: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch image"
        )


# ============================================
# Sync Response Models
# ============================================

class SyncResult(BaseModel):
    """Result of syncing messages from Instagram API"""
    conversations_found: int = Field(..., description="Number of conversations found in Instagram API")
    messages_synced: int = Field(..., description="Number of new messages stored")
    messages_skipped: int = Field(..., description="Number of messages already in database (duplicates)")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered during sync")

    class Config:
        from_attributes = True


# ============================================
# Instagram Message Sync Endpoint
# ============================================

@router.post(
    "/ui/sync",
    response_model=SyncResult,
    summary="Sync messages from Instagram API",
    responses={
        200: {"description": "Sync completed successfully"},
        400: {"description": "Account not properly configured"},
        403: {"description": "No permission to access this account"},
        404: {"description": "Account not found"},
        503: {"description": "Instagram API unavailable"}
    }
)
async def sync_messages_from_instagram(
    account_id: Optional[str] = Query(None, description="Instagram account ID to sync"),
    auth: dict = Depends(verify_jwt_or_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Sync messages from Instagram's Conversations API.

    This endpoint fetches the full message history from Instagram and stores
    any messages that are not already in the database. Use this to sync
    messages sent from the native Instagram app.

    **How it works:**
    1. Fetches conversations from Instagram API (`GET /me/conversations`)
    2. For each conversation, gets all messages
    3. Stores new messages in database (deduplicates by message ID)
    4. Returns sync statistics

    **Use cases:**
    - Sync messages sent from Instagram mobile/web app
    - Initial sync when connecting an account
    - Recover missed webhook messages

    **Rate limits:**
    - Instagram API has rate limits (~200 calls/hour)
    - This endpoint makes 1 API call for conversations list
    - Consider using sparingly (e.g., manual refresh only)

    **Authentication:** API key or JWT token
    """
    from app.services.encryption_service import decrypt_credential
    from sqlalchemy.exc import IntegrityError

    user_id = auth.get("user_id")
    errors = []

    # Get account_id from query param or auth context
    if not account_id:
        account_id = auth.get("account_id")
        if not account_id:
            logger.warning(f"User {user_id} has no linked accounts for sync")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No account linked. Please link an Instagram account first."
            )

    # Verify user has access to this account
    result = await db.execute(
        select(UserAccount).where(
            UserAccount.user_id == user_id,
            UserAccount.account_id == account_id
        )
    )
    user_account_link = result.scalar_one_or_none()

    if not user_account_link:
        logger.warning(f"User {user_id} attempted to sync account {account_id} without permission")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this account"
        )

    # Get account details
    result = await db.execute(
        select(Account).where(Account.id == account_id)
    )
    account = result.scalar_one_or_none()

    if not account:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Account not found"
        )

    if not account.access_token_encrypted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Account has no access token. Please re-link the account."
        )

    # Decrypt access token
    try:
        access_token = decrypt_credential(account.access_token_encrypted, settings.session_secret)
    except Exception as e:
        logger.error(f"Failed to decrypt access token for account {account_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to decrypt account credentials"
        )

    # Fetch conversations from Instagram API
    logger.info(f"🔄 Starting Instagram sync for account {account_id} (@{account.username})")

    async with httpx.AsyncClient() as http_client:
        instagram_client = InstagramClient(
            http_client=http_client,
            access_token=access_token,
            logger_instance=logger
        )

        # Get conversations with messages included
        conversations = await instagram_client.get_conversations(limit=50, include_messages=True)

        if conversations is None:
            logger.error(f"Failed to fetch conversations from Instagram API for account {account_id}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Failed to fetch conversations from Instagram. The API may be unavailable."
            )

    conversations_found = len(conversations)
    messages_synced = 0
    messages_skipped = 0

    # Get our business account's messaging channel ID
    # This is needed to determine message direction
    messaging_channel_id = account.messaging_channel_id or account.instagram_account_id

    # Process each conversation
    for conv in conversations:
        try:
            # Extract messages from conversation
            # Instagram returns messages nested under 'messages' -> 'data'
            messages_data = conv.get("messages", {}).get("data", [])

            # Pre-compute the "other party" ID for this conversation
            # This is needed when participants field is not available (fallback mode)
            other_party_id = None

            # Try to get from participants first
            participants = conv.get("participants", {}).get("data", [])
            if participants:
                for p in participants:
                    p_id = p.get("id")
                    if p_id and p_id != messaging_channel_id and p_id != account.instagram_account_id:
                        other_party_id = p_id
                        break

            # If no participants, scan messages to find the other party
            if not other_party_id and messages_data:
                for msg in messages_data:
                    msg_sender = msg.get("from", {}).get("id")
                    if msg_sender and msg_sender != messaging_channel_id and msg_sender != account.instagram_account_id:
                        other_party_id = msg_sender
                        break

            for msg in messages_data:
                try:
                    msg_id = msg.get("id")
                    if not msg_id:
                        continue

                    # Check if message already exists
                    existing = await db.execute(
                        select(MessageModel).where(MessageModel.id == msg_id)
                    )
                    if existing.scalar_one_or_none():
                        messages_skipped += 1
                        continue

                    # Parse message data
                    # Instagram API format:
                    # - id: message ID
                    # - message: text content
                    # - from: {id, name/username} - sender info
                    # - created_time: ISO timestamp
                    sender_info = msg.get("from", {})
                    sender_id = sender_info.get("id", "unknown")
                    message_text = msg.get("message", "")
                    created_time = msg.get("created_time")

                    # Determine direction based on sender
                    # If sender is our business account, it's outbound
                    # Otherwise, it's inbound
                    if sender_id == messaging_channel_id or sender_id == account.instagram_account_id:
                        direction = "outbound"
                        # For outbound, sender is us, recipient is the other party
                        final_sender_id = messaging_channel_id
                        final_recipient_id = other_party_id or "unknown"
                    else:
                        direction = "inbound"
                        final_sender_id = sender_id
                        final_recipient_id = messaging_channel_id

                    # Parse timestamp
                    try:
                        if created_time:
                            # Instagram returns ISO format like "2026-01-25T10:30:00+0000"
                            timestamp = datetime.fromisoformat(created_time.replace("+0000", "+00:00"))
                        else:
                            timestamp = datetime.now(timezone.utc)
                    except Exception:
                        timestamp = datetime.now(timezone.utc)

                    # Create message record
                    new_message = MessageModel(
                        id=msg_id,
                        account_id=account_id,
                        sender_id=final_sender_id,
                        recipient_id=final_recipient_id,
                        message_text=message_text,
                        direction=direction,
                        timestamp=timestamp,
                        delivery_status="synced"  # Mark as synced from API
                    )

                    db.add(new_message)
                    messages_synced += 1

                except IntegrityError:
                    # Race condition - message was added by webhook while we were syncing
                    await db.rollback()
                    messages_skipped += 1
                except Exception as e:
                    logger.warning(f"Failed to process message {msg.get('id')}: {e}")
                    errors.append(f"Message {msg.get('id')}: {str(e)}")

        except Exception as e:
            logger.warning(f"Failed to process conversation {conv.get('id')}: {e}")
            errors.append(f"Conversation {conv.get('id')}: {str(e)}")

    # Commit all changes
    try:
        await db.commit()
    except Exception as e:
        logger.error(f"Failed to commit synced messages: {e}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save synced messages"
        )

    logger.info(
        f"✅ Instagram sync complete for account {account_id}: "
        f"{conversations_found} conversations, {messages_synced} new messages, "
        f"{messages_skipped} skipped"
    )

    return SyncResult(
        conversations_found=conversations_found,
        messages_synced=messages_synced,
        messages_skipped=messages_skipped,
        errors=errors
    )
