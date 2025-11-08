"""
CRM Integration API - Message Sending Endpoints

Implements outbound message sending for CRM integration.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid
import logging

from app.api.auth import verify_api_key
from app.db.connection import get_db_session
from app.db.models import OutboundMessage, Account

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================
# Pydantic Models (from OpenAPI spec)
# ============================================

class SendMessageRequest(BaseModel):
    """Request to send a message to an Instagram user"""
    account_id: str = Field(..., description="Instagram account ID to send from")
    recipient_id: str = Field(..., description="Instagram PSID of the recipient")
    message: str = Field(..., min_length=1, max_length=1000, description="Message text to send")
    idempotency_key: str = Field(..., description="Unique key to prevent duplicate sends")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Optional CRM-specific metadata")


class SendMessageResponse(BaseModel):
    """Response from send message endpoint"""
    message_id: str = Field(..., description="Message Router's message ID")
    status: str = Field(..., description="pending | accepted | failed")
    created_at: datetime
    
    class Config:
        from_attributes = True


class ErrorDetail(BaseModel):
    """Error details for failed messages"""
    code: str
    message: str


class MessageStatusResponse(BaseModel):
    """Response from message status endpoint"""
    message_id: str
    status: str = Field(..., description="pending | sent | delivered | read | failed")
    account_id: str
    recipient_id: str
    instagram_message_id: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    error: Optional[ErrorDetail] = None
    
    class Config:
        from_attributes = True


# ============================================
# Endpoints
# ============================================

@router.post("/messages/send", response_model=SendMessageResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_message(
    request: SendMessageRequest,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Send a message from Instagram business account to a customer.
    
    Minimal implementation for MVP (Priority 1):
    - Check idempotency - return existing if duplicate
    - Create outbound_messages record with status="pending"
    - Return 202 Accepted immediately
    - Skip account validation (will add in Priority 2)
    - Skip actual Instagram delivery (will add in Task 6)
    
    Returns:
        202 Accepted with message_id
    """
    logger.info(f"Send message request - account: {request.account_id}, recipient: {request.recipient_id}")
    
    # 1. Check idempotency - return existing if duplicate
    result = await db.execute(
        select(OutboundMessage).where(OutboundMessage.idempotency_key == request.idempotency_key)
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        logger.info(f"Duplicate request detected - returning existing message: {existing.id}")
        return SendMessageResponse(
            message_id=existing.id,
            status=existing.status,
            created_at=existing.created_at
        )
    
    # 2. Generate message ID
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    
    # 3. Create outbound_messages record
    outbound_message = OutboundMessage(
        id=message_id,
        account_id=request.account_id,
        recipient_id=request.recipient_id,
        message_text=request.message,
        idempotency_key=request.idempotency_key,
        status="pending",
        created_at=datetime.now(timezone.utc)
    )
    
    db.add(outbound_message)
    
    try:
        await db.flush()  # Flush to catch DB errors before auto-commit
    except Exception as e:
        logger.error(f"Failed to create message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create message"
        )
    
    logger.info(f"✅ Message created: {message_id} (status: pending)")
    
    # 4. Return immediately (actual delivery happens in Task 6)
    return SendMessageResponse(
        message_id=outbound_message.id,
        status=outbound_message.status,
        created_at=outbound_message.created_at
    )


@router.get("/messages/{message_id}/status", response_model=MessageStatusResponse)
async def get_message_status(
    message_id: str,
    api_key: str = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get the delivery status of a sent message.
    
    Minimal implementation for MVP (Priority 1):
    - Query outbound_messages by message_id
    - Return 404 if not found
    - Return current status
    - Skip permission checking (will add in Priority 2)
    
    Returns:
        200 OK with message status
        404 Not Found if message doesn't exist
    """
    logger.info(f"Status query for message: {message_id}")
    
    # Query message by ID
    result = await db.execute(
        select(OutboundMessage).where(OutboundMessage.id == message_id)
    )
    message = result.scalar_one_or_none()
    
    # Return 404 if not found
    if not message:
        logger.warning(f"Message not found: {message_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Message '{message_id}' not found"
        )
    
    # Build error detail if message failed
    error_detail = None
    if message.status == "failed" and message.error_message:
        error_detail = ErrorDetail(
            code=message.error_code or "unknown",
            message=message.error_message
        )
    
    # Return status
    return MessageStatusResponse(
        message_id=message.id,
        status=message.status,
        account_id=message.account_id,
        recipient_id=message.recipient_id,
        instagram_message_id=message.instagram_message_id,
        created_at=message.created_at,
        sent_at=None,  # TODO: Add sent_at field in Priority 2
        delivered_at=None,  # TODO: Add delivered_at field in Priority 2
        read_at=None,  # TODO: Add read_at field in Priority 2
        error=error_detail
    )
