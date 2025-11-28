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

from app.api.auth import verify_api_key, verify_jwt_or_api_key
from app.db.connection import get_db_session
from app.db.models import OutboundMessage, Account, APIKey
from app.clients.instagram_client import InstagramClient, InstagramAPIError
from app.config import settings
from app.api.events import broadcast_new_message, broadcast_message_status
from app.services.api_key_service import APIKeyService

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
    """
    Response from send message endpoint.
    
    Note: OpenAPI spec defines status as [pending, accepted, failed] for async delivery.
    MVP implementation (Task 6) does synchronous delivery and returns [pending, sent, failed].
    This will be aligned when async queue is implemented in Priority 2.
    """
    message_id: str = Field(..., description="Message Router's message ID")
    status: str = Field(..., description="pending | sent | failed (MVP) | accepted (future)")
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
    auth: dict = Depends(verify_jwt_or_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Send a message from Instagram business account to a customer.

    Requires permission to access the specified account_id.

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

    # Handle both JWT and API key authentication
    if auth.get("auth_type") == "api_key":
        # API key authentication - check permissions
        api_key = auth.get("api_key")
        has_permission = await APIKeyService.check_account_permission(db, api_key, request.account_id)
        if not has_permission:
            logger.warning(
                f"Permission denied: API key {api_key.id} attempted to send message for account {request.account_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key does not have permission to access account {request.account_id}"
            )
    elif auth.get("auth_type") == "jwt":
        # JWT authentication - use account from token
        token_account_id = auth.get("account_id")
        if token_account_id != request.account_id:
            logger.warning(
                f"Permission denied: JWT token for account {token_account_id} attempted to send message for account {request.account_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"JWT token does not have permission to access account {request.account_id}"
            )
    else:
        logger.error(f"Unknown authentication type: {auth.get('auth_type')}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication context"
        )
    
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
                
                # Broadcast to SSE clients for real-time UI update
                try:
                    await broadcast_new_message({
                        "id": message_id,
                        "sender_id": request.account_id,
                        "recipient_id": request.recipient_id,
                        "text": request.message,
                        "direction": "outbound",
                        "timestamp": outbound_message.created_at.isoformat(),
                        "status": "sent",
                        "instagram_account_id": request.account_id
                    })
                except Exception as sse_error:
                    logger.error(f"Failed to broadcast SSE message: {sse_error}")
                
            except (InstagramAPIError, Exception) as e:
                # Update message status to "failed"
                outbound_message.status = "failed"
                
                if isinstance(e, InstagramAPIError):
                    outbound_message.error_code = "instagram_api_error"
                    error_msg = e.message
                    
                    # Provide helpful error messages for common issues
                    if "не знайдено користувача" in error_msg.lower() or "user not found" in error_msg.lower():
                        error_msg = (
                            f"{error_msg}. This recipient may not exist or hasn't messaged your account yet. "
                            "Instagram requires users to message you first before you can send them messages."
                        )
                    elif "24 hour" in error_msg.lower() or "messaging window" in error_msg.lower():
                        error_msg = (
                            f"{error_msg}. The 24-hour messaging window has expired. "
                            "You can only send messages within 24 hours of the user's last message."
                        )
                    
                    outbound_message.error_message = f"HTTP {e.status_code}: {error_msg}" if e.status_code else error_msg
                else:
                    outbound_message.error_code = "unexpected_error"
                    outbound_message.error_message = str(e)
                
                logger.error(f"❌ Failed to send message {message_id}: {outbound_message.error_message}")
                
                # Broadcast failure to SSE clients
                try:
                    await broadcast_message_status(message_id, "failed")
                except Exception as sse_error:
                    logger.error(f"Failed to broadcast SSE status: {sse_error}")
    
    # 6. Single commit at the end - all state changes persisted together
    await db.commit()
    
    # 7. Return response with current status
    return SendMessageResponse(
        message_id=outbound_message.id,
        status=outbound_message.status,
        created_at=outbound_message.created_at
    )


@router.get("/messages/{message_id}/status", response_model=MessageStatusResponse)
async def get_message_status(
    message_id: str,
    api_key: APIKey = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Get the delivery status of a sent message.

    Requires permission to access the account associated with the message.

    Minimal implementation for MVP (Priority 1):
    - Query outbound_messages by message_id
    - Return 404 if not found
    - Return current status
    - Check permission for the associated account
    
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

    # Check if API key has permission to access this message's account
    has_permission = await APIKeyService.check_account_permission(db, api_key, message.account_id)
    if not has_permission:
        logger.warning(
            f"Permission denied: API key {api_key.id} attempted to access message {message_id} "
            f"from account {message.account_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"API key does not have permission to access this message"
        )

    # Build error detail if message failed
    error_detail = None
    if message.status == "failed" and message.error_message:
        error_detail = ErrorDetail(
            code=message.error_code or "unknown",
            message=message.error_message
        )
    
    # Return status
    # Note: account_id is not validated against accounts table for MVP.
    # If account is deleted, this will return orphaned account_id.
    # TODO: Add account validation in Priority 2 when adding permission checks.
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
