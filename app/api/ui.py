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
import base64
from fastapi import APIRouter, Depends, Header, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_, and_, case
from sqlalchemy.orm import selectinload
from app.db.connection import get_db_session
from app.db.models import MessageModel, APIKey, UserAccount, Account
from app.clients.instagram_client import InstagramClient
from app.config import settings
from app.api.auth import verify_api_key, verify_ui_session
from app.services.user_service import UserService
from app.infrastructure.cache_service import get_cached_username
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# Session Authentication Endpoint
# ============================================


@router.post("/ui/session")
async def create_session(
    authorization: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Create a UI session token (JWT) by validating Basic Auth credentials.

    This endpoint validates username/password credentials from the Authorization header
    and returns a JWT token for subsequent requests.

    Args:
        authorization: Basic Auth header (e.g., "Basic base64(username:password)")
        db: Database session

    Returns:
        dict: Session token and account information
            - token (str): JWT token for UI authentication
            - account_id (str): Instagram business account ID
            - expires_in (int): Token expiration time in seconds

    Raises:
        HTTPException: 401 if credentials are missing or invalid
    """
    # Check if Authorization header is present and valid format
    if not authorization or not authorization.startswith("Basic "):
        logger.warning("Session creation failed: Missing or invalid Authorization header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Basic Auth credentials. Provide 'Authorization: Basic <credentials>'.",
            headers={"WWW-Authenticate": "Basic"}
        )

    # Decode Basic Auth credentials
    try:
        # Extract base64 part after "Basic "
        encoded_credentials = authorization[6:].strip()

        # Decode base64
        decoded_bytes = base64.b64decode(encoded_credentials)
        decoded_str = decoded_bytes.decode('utf-8')

        # Split username:password
        if ':' not in decoded_str:
            raise ValueError("Invalid credentials format")

        username, password = decoded_str.split(':', 1)

    except Exception as e:
        logger.warning(f"Session creation failed: Invalid Basic Auth format - {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Basic Auth format. Use base64(username:password).",
            headers={"WWW-Authenticate": "Basic"}
        )

    # Validate credentials against database
    user = await UserService.validate_credentials(db, username, password)

    if not user:
        logger.warning(f"Session creation failed: Invalid credentials for username '{username}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
            headers={"WWW-Authenticate": "Basic"}
        )

    # Query user's primary Instagram account (if any)
    result = await db.execute(
        select(UserAccount).where(
            UserAccount.user_id == user.id,
            UserAccount.is_primary == True
        )
    )
    primary_link = result.scalar_one_or_none()
    primary_account_id = primary_link.account_id if primary_link else None

    # Create JWT with user and account context
    # Note: primary_account_id can be None if user hasn't linked any Instagram accounts yet
    expiration_time = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiration_hours)
    payload = {
        "user_id": user.id,
        "username": user.username,
        "primary_account_id": primary_account_id,  # Can be None for new users
        "exp": expiration_time,
        "type": "ui_session"
    }

    # Generate JWT token
    token = jwt.encode(
        payload,
        settings.session_secret,
        algorithm=settings.jwt_algorithm
    )

    logger.info(f"Created UI session for user '{user.username}' (id={user.id}, primary_account={primary_account_id})")

    return {
        "token": token,
        "account_id": primary_account_id,  # For backward compatibility (may be None)
        "user_id": user.id,
        "username": user.username,
        "expires_in": settings.jwt_expiration_hours * 3600  # Convert hours to seconds
    }


# ============================================
# UI Data Endpoints (JWT Protected)
# ============================================


@router.get("/ui/account/me")
async def get_current_account(
    account_id: Optional[str] = Query(None, description="Instagram account ID. If not provided, uses user's primary account."),
    session: dict = Depends(verify_ui_session),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get current user's Instagram account information.

    Returns the business account ID, username, profile picture, and Instagram handle.

    Requires JWT session authentication.

    Args:
        account_id: Optional account ID. If not provided, uses user's primary account from session.
    """
    try:
        user_id = session.get("user_id")

        # If no account_id provided, use primary account from session
        if not account_id:
            account_id = session.get("account_id")  # This is primary_account_id
            if not account_id:
                # User has no linked accounts yet
                logger.info(f"User {user_id} has no linked accounts")
                return {
                    "account_id": None,
                    "username": "No account linked",
                    "instagram_handle": None,
                    "profile_picture_url": None
                }

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

        return {
            "account_id": account_id,
            "instagram_account_id": business_account_id,
            "username": f"@{username}" if username else f"@{business_account_id}",
            "instagram_handle": username or business_account_id,
            "profile_picture_url": profile_pic_url
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch current account info: {e}", exc_info=True)
        return {
            "account_id": None,
            "username": "Error loading account",
            "instagram_handle": None,
            "profile_picture_url": None
        }


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
                    "profile_picture_url": profile.get("profile_pic")
                }
    except Exception as e:
        logger.warning(f"Failed to fetch profile for {sender_id}: {e}")

    # Fallback
    return {
        "username": sender_id,
        "profile_picture_url": None
    }


@router.get("/ui/conversations")
async def get_conversations(
    account_id: Optional[str] = Query(None, description="Instagram account ID to filter by"),
    session: dict = Depends(verify_ui_session),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get list of all conversations grouped by sender.
    Returns all conversations with time remaining indicator.

    Business accounts can only initiate/respond to messages within 24 hours
    of the last inbound message from the user. The response includes hours_remaining
    which can be negative for expired conversations.

    Requires JWT session authentication.

    Args:
        account_id: Optional Instagram account ID to filter conversations.
                   If not provided, uses user's primary account from session.
    """
    try:
        user_id = session.get("user_id")

        # If no account_id provided, use primary account from session
        if not account_id:
            account_id = session.get("account_id")  # This is primary_account_id
            if not account_id:
                # User has no linked accounts yet
                logger.info(f"User {user_id} has no linked accounts, returning empty conversations")
                return {"conversations": []}

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
            return {"conversations": []}

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
                func.max(MessageModel.timestamp).label('latest_timestamp')
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
        # Match on contact_id AND timestamp to get the actual latest message
        stmt = (
            select(MessageModel)
            .join(
                subq,
                and_(
                    or_(
                        and_(MessageModel.direction == 'inbound', MessageModel.sender_id == subq.c.contact_id),
                        and_(MessageModel.direction == 'outbound', MessageModel.recipient_id == subq.c.contact_id)
                    ),
                    MessageModel.timestamp == subq.c.latest_timestamp
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

        return {"conversations": conversations}

    except Exception as e:
        logger.error(f"Failed to fetch conversations: {e}")
        return {"conversations": []}


@router.get("/ui/messages/{sender_id}")
async def get_messages(
    sender_id: str,
    account_id: Optional[str] = Query(None, description="Instagram account ID to filter by"),
    session: dict = Depends(verify_ui_session),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get all messages for a specific sender (conversation thread).
    Returns both inbound and outbound messages with Instagram username.

    Requires JWT session authentication.

    Args:
        sender_id: Instagram user ID of the conversation partner
        account_id: Optional Instagram account ID. If not provided, uses user's primary account.
    """
    try:
        user_id = session.get("user_id")

        # If no account_id provided, use primary account from session
        if not account_id:
            account_id = session.get("account_id")  # This is primary_account_id
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
        # Filter by messaging_channel_id to ensure only messages for THIS channel are returned
        # - Inbound: user sends TO this messaging channel
        # - Outbound: this messaging channel sends TO user
        stmt = (
            select(MessageModel)
            .options(selectinload(MessageModel.attachments))  # Eagerly load attachments
            .where(
                or_(
                    # Inbound: user sends to this messaging channel
                    (MessageModel.sender_id == sender_id) &
                    (MessageModel.recipient_id == messaging_channel_id),

                    # Outbound: this messaging channel sends to user
                    (MessageModel.sender_id == messaging_channel_id) &
                    (MessageModel.recipient_id == sender_id)
                )
            )
            .order_by(MessageModel.timestamp)
        )

        result = await db.execute(stmt)
        messages = result.scalars().all()

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

        return {
            "messages": message_list,
            "sender_info": sender_info
        }

    except Exception as e:
        logger.error(f"Failed to fetch messages for {sender_id}: {e}")
        # In exception handler, we don't have access_token available, so use sender_id as fallback
        return {
            "messages": [],
            "sender_info": {"id": sender_id, "name": sender_id}
        }


@router.get("/ui/proxy-image")
async def proxy_instagram_image(
    url: str = Query(..., description="Instagram CDN image URL to proxy")
):
    """
    Proxy Instagram CDN images to bypass CORS and referrer restrictions.

    Instagram CDN blocks direct image loading from external sites due to:
    - Referrer policy restrictions
    - CORS headers
    - User-Agent requirements

    This endpoint fetches the image server-side and serves it to the frontend,
    bypassing these restrictions.

    Public endpoint (no auth required) since:
    - Only proxies public Instagram CDN URLs
    - Browser <img> tags don't send JWT tokens
    - Instagram profile pictures are already public data
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
            return Response(
                content=response.content,
                media_type=response.headers.get("content-type", "image/jpeg"),
                headers={
                    "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
                    "Access-Control-Allow-Origin": "*",  # Allow CORS
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
