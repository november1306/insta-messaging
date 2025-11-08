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
import httpx

from app.api.auth import verify_api_key
from app.db.connection import get_db_session
from app.db.models import OutboundMessage, Account
from app.clients.instagram_client import InstagramClient, InstagramAPIError
from app.config import settings

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
        await db.flush()  # Flush to catch DB errors before commit
    except Exception as e:
        logger.error(f"Failed to create message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create message"
        )
    
    logger.info(f"✅ Message created: {message_id} (status: pending)")
    
    # 4. Check if Instagram access token is configured
    if not settings.instagram_page_access_token or not settings.instagram_page_access_token.strip():
        outbound_message.status = "failed"
        outbound_message.error_code = "missing_config"
        outbound_message.error_message = "Instagram access token not configured"
        
        logger.error(f"❌ Cannot send message {message_id}: Instagram access token not configured")
    else:
        # 5. Attempt Instagram delivery (synchronous for MVP)
        # TODO: Move to async queue with retries in Priority 2
        async with httpx.AsyncClient() as http_client:
            instagram_client = InstagramClient(
                http_client=http_client,
                settings=settings,
                logger_instance=logger
            )
            
            try:
                # Send message via Instagram API
                ig_response = await instagram_client.send_message(
                    recipient_id=request.recipient_id,
                    message_text=request.message
                )
                
                # Update message status to "sent"
                outbound_message.status = "sent"
                outbound_message.instagram_message_id = ig_response.message_id
                
                logger.info(f"✅ Message sent to Instagram: {message_id} (ig_msg_id: {ig_response.message_id})")
                
            except (InstagramAPIError, Exception) as e:
                # Update message status to "failed"
                outbound_message.status = "failed"
                
                if isinstance(e, InstagramAPIError):
                    outbound_message.error_code = "instagram_api_error"
                    outbound_message.error_message = f"HTTP {e.status_code}: {e.message}" if e.status_code else e.message
                else:
                    outbound_message.error_code = "unexpected_error"
                    outbound_message.error_message = str(e)
                
                logger.error(f"❌ Failed to send message {message_id}: {outbound_message.error_message}")
    
    # 6. Single commit at the end - all state changes persisted together
    await db.commit()
    
    # 7. Return response with current status
    return SendMessageResponse(
        message_id=outbound_message.id,
        status=outbound_message.status,
        created_at=outbound_message.created_at
    )
