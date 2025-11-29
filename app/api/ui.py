"""
UI API endpoints for the web frontend
Provides conversation lists and message retrieval for the Vue chat interface

Authentication:
- POST /ui/session: Validates Basic Auth credentials, returns JWT token
- All other /ui/* endpoints: Protected by JWT token validation
"""
import logging
import httpx
import jwt
import base64
from fastapi import APIRouter, Depends, Header, HTTPException, status, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from app.db.connection import get_db_session
from app.db.models import MessageModel, APIKey
from app.clients.instagram_client import InstagramClient
from app.config import settings
from app.api.auth import verify_api_key, verify_ui_session
from app.services.user_service import UserService
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache for Instagram usernames (in-memory for MVP)
# In production, use Redis or database
username_cache: Dict[str, str] = {}

# Business account can only respond within 24 hours
RESPONSE_WINDOW_HOURS = 24


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

    # Get Instagram business account ID
    account_id = settings.instagram_business_account_id

    if not account_id:
        logger.error("Instagram business account ID not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Account not configured"
        )

    # Create JWT with account context
    expiration_time = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiration_hours)
    payload = {
        "account_id": account_id,
        "user_id": user.id,  # Include user ID in JWT for audit trail
        "username": user.username,  # Include username for logging
        "exp": expiration_time,
        "type": "ui_session"
    }

    # Generate JWT token
    token = jwt.encode(
        payload,
        settings.session_secret,
        algorithm=settings.jwt_algorithm
    )

    logger.info(f"Created UI session for user '{user.username}' (account: {account_id})")

    return {
        "token": token,
        "account_id": account_id,
        "expires_in": settings.jwt_expiration_hours * 3600  # Convert hours to seconds
    }


# ============================================
# UI Data Endpoints (JWT Protected)
# ============================================


@router.get("/ui/account/me")
async def get_current_account(
    session: dict = Depends(verify_ui_session)
):
    """
    Get current user's Instagram account information.

    Returns the business account ID, username, profile picture, and Instagram handle
    from the session context.

    Requires JWT session authentication.
    """
    try:
        business_account_id = settings.instagram_business_account_id

        if not business_account_id:
            logger.warning("Instagram business account ID not configured")
            return {
                "account_id": None,
                "username": "Not configured",
                "instagram_handle": None,
                "profile_picture_url": None
            }

        # Fetch business account profile from Instagram Graph API
        async with httpx.AsyncClient() as http_client:
            instagram_client = InstagramClient(
                http_client=http_client,
                settings=settings,
                logger_instance=logger
            )
            profile = await instagram_client.get_business_account_profile(business_account_id)

        if not profile:
            logger.warning(f"Failed to fetch business account profile for {business_account_id}")
            return {
                "account_id": business_account_id,
                "username": f"@{business_account_id}",
                "instagram_handle": business_account_id,
                "profile_picture_url": None
            }

        username = profile.get("username", "")
        profile_pic_url = profile.get("profile_picture_url")

        logger.info(f"✅ Business account: @{username}, has_pic={bool(profile_pic_url)}")

        return {
            "account_id": business_account_id,
            "username": f"@{username}" if username else f"@{business_account_id}",
            "instagram_handle": username or business_account_id,
            "profile_picture_url": profile_pic_url
        }
    except Exception as e:
        logger.error(f"Failed to fetch current account info: {e}", exc_info=True)
        return {
            "account_id": settings.instagram_business_account_id,
            "username": f"@{settings.instagram_business_account_id}" if settings.instagram_business_account_id else "Unknown",
            "instagram_handle": settings.instagram_business_account_id,
            "profile_picture_url": None
        }


async def _get_instagram_username(sender_id: str, is_business_account: bool = False) -> str:
    """
    Get Instagram username for a sender ID.
    Uses cache to avoid repeated API calls.

    Args:
        sender_id: Instagram user ID
        is_business_account: If True, fetch business account username properly

    Returns:
        Username in @username format, or user_id if fetch fails
    """
    # Check cache first (unless it's the business account)
    if not is_business_account and sender_id in username_cache:
        return username_cache[sender_id]

    # Fetch from Instagram API
    try:
        async with httpx.AsyncClient() as http_client:
            instagram_client = InstagramClient(
                http_client=http_client,
                settings=settings,
                logger_instance=logger
            )
            profile = await instagram_client.get_user_profile(sender_id)

            if profile and "username" in profile:
                username = f"@{profile['username']}"
                username_cache[sender_id] = username
                return username
    except Exception as e:
        logger.warning(f"Failed to fetch username for {sender_id}: {e}")

    # Fallback to sender_id
    return sender_id


async def _get_instagram_profile(sender_id: str) -> dict:
    """
    Get Instagram profile data for a sender ID.

    Args:
        sender_id: Instagram user ID

    Returns:
        Dictionary with username and profile_picture_url, or default values if fetch fails
    """
    # Fetch from Instagram API
    try:
        async with httpx.AsyncClient() as http_client:
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
    session: dict = Depends(verify_ui_session),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get list of all conversations grouped by sender.
    Returns only conversations with valid response tokens (within 24-hour window).

    Business accounts can only initiate/respond to messages within 24 hours
    of the last inbound message from the user.

    Requires JWT session authentication.
    """
    try:
        # Calculate cutoff time for 24-hour response window
        now = datetime.now(timezone.utc)
        cutoff_time = now - timedelta(hours=RESPONSE_WINDOW_HOURS)

        # Get business account ID from session (user's account perspective)
        business_account_id = settings.instagram_business_account_id

        # Subquery to get the latest message ID for each sender
        # Filter by recipient_id to ensure only messages TO this account are included
        subq = (
            select(
                MessageModel.sender_id,
                func.max(MessageModel.id).label('latest_message_id')
            )
            .where(MessageModel.direction == 'inbound')
            .where(MessageModel.recipient_id == business_account_id)  # Only messages to this account
            .group_by(MessageModel.sender_id)
            .subquery()
        )

        # Join to get full message details, filter by 24-hour window
        # IMPORTANT: Filter by account to show only this account's contacts
        stmt = (
            select(MessageModel)
            .join(
                subq,
                (MessageModel.sender_id == subq.c.sender_id) &
                (MessageModel.id == subq.c.latest_message_id)
            )
            .where(MessageModel.timestamp >= cutoff_time)  # Only conversations within response window
            .where(MessageModel.recipient_id == business_account_id)  # Only messages to this account
            .where(MessageModel.sender_id != business_account_id)  # Exclude business account from contacts
            .order_by(desc(MessageModel.timestamp))
        )

        result = await db.execute(stmt)
        messages = result.scalars().all()

        # Batch fetch profiles in parallel to avoid N+1 query problem
        # Collect unique sender IDs
        unique_sender_ids = list(set(msg.sender_id for msg in messages))

        # Fetch all profiles concurrently
        import asyncio
        profile_tasks = [_get_instagram_profile(sender_id) for sender_id in unique_sender_ids]
        profiles = await asyncio.gather(*profile_tasks)

        # Create sender_id -> profile mapping
        profile_map = dict(zip(unique_sender_ids, profiles))

        conversations = []
        for msg in messages:
            # Get profile from pre-fetched map
            profile = profile_map.get(msg.sender_id, {"username": msg.sender_id, "profile_picture_url": None})

            # Calculate time remaining in response window
            # Ensure msg.timestamp is timezone-aware (assume UTC if naive)
            msg_timestamp = msg.timestamp
            if msg_timestamp.tzinfo is None:
                msg_timestamp = msg_timestamp.replace(tzinfo=timezone.utc)

            time_remaining = (msg_timestamp + timedelta(hours=RESPONSE_WINDOW_HOURS)) - now
            hours_remaining = max(0, int(time_remaining.total_seconds() / 3600))

            conversations.append({
                "sender_id": msg.sender_id,
                "sender_name": profile["username"],
                "profile_picture_url": profile["profile_picture_url"],  # Fixed field name for frontend
                "last_message": msg.message_text or "",
                "last_message_time": msg_timestamp.isoformat() if msg_timestamp else None,
                "unread_count": 0,  # TODO: Implement read/unread tracking
                "instagram_account_id": msg.recipient_id,  # The business account that received the message
                "hours_remaining": hours_remaining,  # Hours left to respond
                "can_respond": hours_remaining > 0
            })

        return {"conversations": conversations}

    except Exception as e:
        logger.error(f"Failed to fetch conversations: {e}")
        return {"conversations": []}


@router.get("/ui/messages/{sender_id}")
async def get_messages(
    sender_id: str,
    session: dict = Depends(verify_ui_session),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get all messages for a specific sender (conversation thread).
    Returns both inbound and outbound messages with Instagram username.

    Requires JWT session authentication.
    """
    try:
        # Get business account ID from session (user's account perspective)
        business_account_id = settings.instagram_business_account_id

        # Get all messages for this conversation thread (both inbound and outbound)
        # Filter by account to ensure only messages for THIS business account are returned
        # - Inbound: user sends TO business account
        # - Outbound: business account sends TO user
        stmt = (
            select(MessageModel)
            .where(
                or_(
                    # Inbound: user sends to this business account
                    (MessageModel.sender_id == sender_id) &
                    (MessageModel.recipient_id == business_account_id),

                    # Outbound: this business account sends to user
                    (MessageModel.sender_id == business_account_id) &
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
            message_list.append({
                "id": msg.id,
                "text": msg.message_text or "",
                "direction": msg.direction,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None,
                "status": getattr(msg, 'status', None)
            })

            # Capture sender info from first message
            if sender_info is None:
                sender_name = await _get_instagram_username(msg.sender_id)
                sender_info = {
                    "id": msg.sender_id,
                    "name": sender_name
                }

        if sender_info is None:
            sender_name = await _get_instagram_username(sender_id)
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
        sender_name = await _get_instagram_username(sender_id)
        return {
            "messages": [],
            "sender_info": {"id": sender_id, "name": sender_name}
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
