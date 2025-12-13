"""
CRM Integration API - Message Sending Endpoints

Implements outbound message sending for CRM integration.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Form, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from pathlib import Path
import uuid
import logging
import httpx

from app.api.auth import verify_api_key, verify_jwt_or_api_key
from app.db.connection import get_db_session
from app.db.models import CRMOutboundMessage, Account, APIKey
from app.clients.instagram_client import InstagramClient, InstagramAPIError
from app.config import settings
from app.api.events import broadcast_new_message, broadcast_message_status
from app.services.api_key_service import APIKeyService
from app.core.interfaces import Message
from app.repositories.message_repository import MessageRepository

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
    recipient_id: str = Form(...),
    account_id: str = Form(...),
    idempotency_key: str = Form(...),
    message: Optional[str] = Form(None),
    metadata: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    http_request: Request = None,
    auth: dict = Depends(verify_jwt_or_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    """
    Send a message with optional text and/or file attachment to an Instagram user.

    Accepts multipart/form-data with:
    - recipient_id, account_id, idempotency_key (required)
    - message (optional text)
    - file (optional attachment: image, video, or audio)

    At least one of message or file must be provided.

    Returns:
        202 Accepted with message_id and status
    """
    logger.info(f"Send message request - account: {account_id}, recipient: {recipient_id}, has_file: {file is not None}")

    # Validate that at least one of message or file is provided
    if not message and not file:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either message text or file attachment is required"
        )

    # Handle both JWT and API key authentication
    if auth.get("auth_type") == "api_key":
        # API key authentication - check permissions
        api_key = auth.get("api_key")
        has_permission = await APIKeyService.check_account_permission(db, api_key, account_id)
        if not has_permission:
            logger.warning(
                f"Permission denied: API key {api_key.id} attempted to send message for account {account_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key does not have permission to access account {account_id}"
            )
    elif auth.get("auth_type") == "jwt":
        # JWT authentication - use account from token
        token_account_id = auth.get("account_id")
        if token_account_id != account_id:
            logger.warning(
                f"Permission denied: JWT token for account {token_account_id} attempted to send message for account {account_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"JWT token does not have permission to access account {account_id}"
            )
    else:
        logger.error(f"Unknown authentication type: {auth.get('auth_type')}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication context"
        )
    
    # 1. Check idempotency - return existing if duplicate
    result = await db.execute(
        select(CRMOutboundMessage).where(CRMOutboundMessage.idempotency_key == idempotency_key)
    )
    existing = result.scalar_one_or_none()

    if existing:
        logger.info(f"Duplicate request detected - returning existing message: {existing.id}")
        return SendMessageResponse(
            message_id=existing.id,
            status=existing.status,
            created_at=existing.created_at
        )

    # 2. Handle file upload if present
    attachment_url = None
    attachment_type = None

    if file:
        # Validate file type
        content_type = file.content_type
        if content_type.startswith('image/'):
            if content_type not in ['image/jpeg', 'image/png']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported image type: {content_type}. Supported: JPEG, PNG"
                )
            attachment_type = 'image'
            max_size = 8 * 1024 * 1024  # 8MB
        elif content_type.startswith('video/'):
            if content_type not in ['video/mp4', 'video/ogg', 'video/avi', 'video/quicktime', 'video/webm']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported video type: {content_type}. Supported: MP4, OGG, AVI, MOV, WebM"
                )
            attachment_type = 'video'
            max_size = 25 * 1024 * 1024  # 25MB
        elif content_type.startswith('audio/'):
            if content_type not in ['audio/aac', 'audio/m4a', 'audio/wav', 'audio/mp4']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported audio type: {content_type}. Supported: AAC, M4A, WAV, MP4"
                )
            attachment_type = 'audio'
            max_size = 25 * 1024 * 1024  # 25MB
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {content_type}"
            )

        # Read and validate file size
        file_content = await file.read()
        if len(file_content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large: {len(file_content)} bytes (max: {max_size} bytes = {max_size//1024//1024}MB)"
            )

        # Generate unique filename
        file_ext = Path(file.filename).suffix if file.filename else '.bin'
        unique_filename = f"{uuid.uuid4()}_{int(datetime.now().timestamp())}{file_ext}"

        # Store file in outbound media directory
        media_dir = Path(__file__).parent.parent.parent / "media" / "outbound" / account_id
        media_dir.mkdir(parents=True, exist_ok=True)
        file_path = media_dir / unique_filename

        with open(file_path, 'wb') as f:
            f.write(file_content)

        # Generate public URL for Instagram API to fetch
        attachment_url = f"{settings.public_base_url}/media/outbound/{account_id}/{unique_filename}"

        logger.info(f"File uploaded: {file.filename} -> {unique_filename} ({len(file_content)} bytes, type: {attachment_type})")

    # 3. Generate message ID
    message_id = f"msg_{uuid.uuid4().hex[:12]}"

    # 4. Create CRM outbound message record (for tracking/idempotency)
    outbound_message = CRMOutboundMessage(
        id=message_id,
        account_id=account_id,
        recipient_id=recipient_id,
        message_text=message,
        idempotency_key=idempotency_key,
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
                # Send message via Instagram API (with or without attachment)
                if attachment_url:
                    # Send message with attachment
                    ig_response = await instagram_client.send_message_with_attachment(
                        recipient_id=recipient_id,
                        attachment_url=attachment_url,
                        attachment_type=attachment_type,
                        caption_text=message  # Optional caption
                    )
                else:
                    # Send text-only message
                    ig_response = await instagram_client.send_message(
                        recipient_id=recipient_id,
                        message_text=message
                    )

                # Update CRM tracking status to "sent"
                outbound_message.status = "sent"
                outbound_message.instagram_message_id = ig_response.message_id

                logger.info(f"✅ Message sent to Instagram: {message_id} (ig_msg_id: {ig_response.message_id})")

                # Save to messages table for UI display (messenger pattern)
                # This ensures the message appears when fetching conversation history
                try:
                    # Get CRM pool from app state for MySQL sync
                    crm_pool = getattr(http_request.app.state, 'crm_pool', None)

                    message_repo = MessageRepository(db, crm_pool=crm_pool)
                    ui_message = Message(
                        id=ig_response.message_id,  # Use Instagram's message ID
                        sender_id=account_id,  # Business account
                        recipient_id=recipient_id,  # Customer
                        message_text=message or '',  # Empty string if media-only
                        direction="outbound",
                        timestamp=datetime.now(timezone.utc)
                    )
                    await message_repo.save(ui_message)
                    logger.info(f"✅ Message saved to messages table for UI: {ig_response.message_id}")
                except Exception as save_error:
                    # Log error but don't fail the request - message was sent successfully
                    logger.error(f"⚠️ Failed to save message to messages table: {save_error}", exc_info=True)

                # Broadcast to SSE clients for real-time UI update
                try:
                    await broadcast_new_message({
                        "id": message_id,
                        "sender_id": account_id,
                        "recipient_id": recipient_id,
                        "text": message or '',
                        "direction": "outbound",
                        "timestamp": outbound_message.created_at.isoformat(),
                        "status": "sent",
                        "instagram_account_id": account_id
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
    - Query crm_outbound_messages by message_id
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
        select(CRMOutboundMessage).where(CRMOutboundMessage.id == message_id)
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
