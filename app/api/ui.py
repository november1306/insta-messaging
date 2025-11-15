"""
UI API endpoints for the web frontend
Provides conversation lists and message retrieval for the Vue chat interface
"""
import logging
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db.connection import get_db_session
from app.db.models import MessageModel
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/ui/conversations")
async def get_conversations(
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get list of all conversations grouped by sender.
    Returns the latest message from each sender.
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
            conversations.append({
                "sender_id": msg.sender_id,
                "sender_name": msg.sender_id,  # MessageModel doesn't have sender_name field
                "last_message": msg.message_text or "",
                "last_message_time": msg.timestamp.isoformat() if msg.timestamp else None,
                "unread_count": 0,  # TODO: Implement read/unread tracking
                "instagram_account_id": msg.sender_id  # MessageModel doesn't have instagram_account_id field
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
    Returns both inbound and outbound messages.
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
                sender_info = {
                    "id": msg.sender_id,
                    "name": msg.sender_id  # MessageModel doesn't have sender_name field
                }

        if sender_info is None:
            sender_info = {
                "id": sender_id,
                "name": sender_id
            }

        return {
            "messages": message_list,
            "sender_info": sender_info
        }

    except Exception as e:
        logger.error(f"Failed to fetch messages for {sender_id}: {e}")
        return {
            "messages": [],
            "sender_info": {"id": sender_id, "name": sender_id}
        }
