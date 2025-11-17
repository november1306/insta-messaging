"""
UI API endpoints for the web frontend
Provides conversation lists and message retrieval for the Vue chat interface
"""
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db.connection import get_db_session
from app.db.models import MessageModel
from app.clients.instagram_client import InstagramClient
from app.config import settings
from app.api.ui_auth import (
    LoginRequest, LoginResponse,
    authenticate_user, create_jwt_token
)
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache for Instagram usernames (in-memory for MVP)
# In production, use Redis or database
username_cache: Dict[str, str] = {}


# ============================================
# Authentication Endpoints
# ============================================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login to the UI with username and password.

    Returns a JWT token for subsequent requests.

    Default credentials:
    - Username: admin, Password: admin123
    - Username: demo, Password: demo123
    """
    user = await authenticate_user(request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    # Generate JWT token
    token, expires_in = create_jwt_token(user["username"], user["role"])

    return LoginResponse(
        token=token,
        expires_in=expires_in,
        username=user["username"],
        role=user["role"],
        display_name=user["display_name"]
    )


# ============================================
# UI Data Endpoints
# ============================================


async def _get_instagram_username(sender_id: str) -> str:
    """
    Get Instagram username for a sender ID.
    Uses cache to avoid repeated API calls.
    """
    # Check if this is the business account
    if sender_id == settings.instagram_business_account_id:
        return f"{sender_id} (me)"
    
    # Check cache first
    if sender_id in username_cache:
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
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get list of all conversations grouped by sender.
    Returns the latest message from each sender with Instagram usernames.
    """
    try:
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

        # Join to get full message details
        stmt = (
            select(MessageModel)
            .join(
                subq,
                (MessageModel.sender_id == subq.c.sender_id) &
                (MessageModel.id == subq.c.latest_message_id)
            )
            .order_by(desc(MessageModel.timestamp))
        )

        result = await db.execute(stmt)
        messages = result.scalars().all()

        conversations = []
        for msg in messages:
            # Fetch Instagram username
            sender_name = await _get_instagram_username(msg.sender_id)
            
            conversations.append({
                "sender_id": msg.sender_id,
                "sender_name": sender_name,
                "last_message": msg.message_text or "",
                "last_message_time": msg.timestamp.isoformat() if msg.timestamp else None,
                "unread_count": 0,  # TODO: Implement read/unread tracking
                "instagram_account_id": msg.recipient_id  # The business account that received the message
            })

        return {"conversations": conversations}

    except Exception as e:
        logger.error(f"Failed to fetch conversations: {e}")
        return {"conversations": []}


@router.get("/ui/messages/{sender_id}")
async def get_messages(
    sender_id: str,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get all messages for a specific sender (conversation thread).
    Returns both inbound and outbound messages with Instagram username.
    """
    try:
        # Get all messages for this sender
        stmt = (
            select(MessageModel)
            .where(MessageModel.sender_id == sender_id)
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
