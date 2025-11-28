"""
UI API endpoints for the web frontend
Provides conversation lists and message retrieval for the Vue chat interface

Authentication: Uses API key authentication (same as CRM endpoints).
Generate an API key with: python -m app.cli.generate_api_key --name "UI Access" --type admin --env test
"""
import logging
import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, or_
from app.db.connection import get_db_session
from app.db.models import MessageModel, APIKey
from app.clients.instagram_client import InstagramClient
from app.config import settings
from app.api.auth import verify_api_key
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache for Instagram usernames (in-memory for MVP)
# In production, use Redis or database
username_cache: Dict[str, str] = {}

# Business account can only respond within 24 hours
RESPONSE_WINDOW_HOURS = 24


# ============================================
# UI Data Endpoints (API Key Protected)
# ============================================


@router.get("/ui/account/me")
async def get_current_account(
    api_key: APIKey = Depends(verify_api_key)
):
    """
    Get current user's Instagram account information.

    Returns the business account ID, username, and Instagram handle
    configured in the application settings.

    Requires API key authentication.
    """
    try:
        business_account_id = settings.instagram_business_account_id

        if not business_account_id:
            logger.warning("Instagram business account ID not configured")
            return {
                "account_id": None,
                "username": "Not configured",
                "instagram_handle": None
            }

        # Fetch username from Instagram API (pass is_business_account=True)
        username = await _get_instagram_username(business_account_id, is_business_account=True)

        # Extract handle (remove "@" prefix if present)
        instagram_handle = username.replace("@", "") if username and username.startswith("@") else business_account_id

        return {
            "account_id": business_account_id,
            "username": username if username else f"@{business_account_id}",
            "instagram_handle": instagram_handle
        }
    except Exception as e:
        logger.error(f"Failed to fetch current account info: {e}")
        return {
            "account_id": settings.instagram_business_account_id,
            "username": "Error loading account",
            "instagram_handle": None
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


@router.get("/ui/conversations")
async def get_conversations(
    api_key: APIKey = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get list of all conversations grouped by sender.
    Returns only conversations with valid response tokens (within 24-hour window).

    Business accounts can only initiate/respond to messages within 24 hours
    of the last inbound message from the user.

    Requires API key authentication.
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

        # Batch fetch usernames in parallel to avoid N+1 query problem
        # Collect unique sender IDs
        unique_sender_ids = list(set(msg.sender_id for msg in messages))

        # Fetch all usernames concurrently
        import asyncio
        username_tasks = [_get_instagram_username(sender_id) for sender_id in unique_sender_ids]
        usernames = await asyncio.gather(*username_tasks)

        # Create sender_id -> username mapping
        username_map = dict(zip(unique_sender_ids, usernames))

        conversations = []
        for msg in messages:
            # Get username from pre-fetched map
            sender_name = username_map.get(msg.sender_id, msg.sender_id)

            # Calculate time remaining in response window
            time_remaining = (msg.timestamp + timedelta(hours=RESPONSE_WINDOW_HOURS)) - now
            hours_remaining = max(0, int(time_remaining.total_seconds() / 3600))

            conversations.append({
                "sender_id": msg.sender_id,
                "sender_name": sender_name,
                "last_message": msg.message_text or "",
                "last_message_time": msg.timestamp.isoformat() if msg.timestamp else None,
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
    api_key: APIKey = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get all messages for a specific sender (conversation thread).
    Returns both inbound and outbound messages with Instagram username.

    Requires API key authentication.
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
