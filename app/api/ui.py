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
from fastapi import APIRouter, Depends, Header, HTTPException, status
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

        # Fetch profile from Instagram API
        profile = await _get_instagram_profile(business_account_id)

        # Extract handle (remove "@" prefix if present)
        username = profile["username"]
        instagram_handle = username.replace("@", "") if username and username.startswith("@") else business_account_id

        return {
            "account_id": business_account_id,
            "username": username if username else f"@{business_account_id}",
            "instagram_handle": instagram_handle,
            "profile_picture_url": profile["profile_picture_url"]
        }
    except Exception as e:
        logger.error(f"Failed to fetch current account info: {e}")
        return {
            "account_id": settings.instagram_business_account_id,
            "username": "Error loading account",
            "instagram_handle": None,
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
                    "profile_picture_url": profile.get("profile_picture_url")
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

        # Get business account ID to exclude from contacts
        business_account_id = settings.instagram_business_account_id

        # Subquery to get the latest message ID for each sender
        subq = (
            select(
                MessageModel.sender_id,
                func.max(MessageModel.id).label('latest_message_id')
            )
            .where(MessageModel.direction == 'inbound')
            .group_by(MessageModel.sender_id)
            .subquery()
        )

        # Join to get full message details, filter by 24-hour window
        # IMPORTANT: Exclude business account from contacts (no chatting with myself)
        stmt = (
            select(MessageModel)
            .join(
                subq,
                (MessageModel.sender_id == subq.c.sender_id) &
                (MessageModel.id == subq.c.latest_message_id)
            )
            .where(MessageModel.timestamp >= cutoff_time)  # Only conversations within response window
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
                "profile_picture_url": profile["profile_picture_url"],
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
        # Get all messages for this conversation thread (both inbound and outbound)
        # - Inbound: sender_id = user (user sends to business)
        # - Outbound: recipient_id = user (business sends to user, including automated replies)
        stmt = (
            select(MessageModel)
            .where(
                or_(
                    MessageModel.sender_id == sender_id,      # Inbound messages from user
                    MessageModel.recipient_id == sender_id    # Outbound messages to user
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
