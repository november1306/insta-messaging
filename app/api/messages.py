"""
CRM Integration API - Message Sending Endpoints

Implements outbound message sending for CRM integration.
Refactored to use Domain-Driven Design with MessageService.
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
from app.db.models import CRMOutboundMessage, Account, APIKey, MessageAttachment
from app.domain.unit_of_work import SQLAlchemyUnitOfWork
from app.application.message_service import MessageService
from app.domain.value_objects import AccountId, InstagramUserId, IdempotencyKey
from app.domain.entities import AccountNotFoundError
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
    attachment_url: Optional[str] = Field(None, description="Public URL of attachment if file was uploaded")
    attachment_type: Optional[str] = Field(None, description="Type of attachment: image | video | audio")
    attachment_local_path: Optional[str] = Field(None, description="Local path for frontend to fetch authenticated media")

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
        # JWT authentication - check if user has access to this account via UserAccount table
        user_id = auth.get("user_id")
        if not user_id:
            logger.error("JWT authentication missing user_id")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication context"
            )

        # Check if user has access to this account
        from app.db.models import UserAccount
        result = await db.execute(
            select(UserAccount).where(
                UserAccount.user_id == user_id,
                UserAccount.account_id == account_id
            )
        )
        user_account_link = result.scalar_one_or_none()

        if not user_account_link:
            logger.warning(
                f"Permission denied: User {user_id} attempted to send message for account {account_id} without permission"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"You don't have permission to access account {account_id}"
            )
    else:
        logger.error(f"Unknown authentication type: {auth.get('auth_type')}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication context"
        )
    
    # Note: Idempotency check is handled by MessageService to eliminate redundant queries

    # 1. Handle file upload if present
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

    # 5. Send message using MessageService + Unit of Work
    try:
        # Create Unit of Work for transactional messaging
        async with SQLAlchemyUnitOfWork(db) as uow:
            # Create MessageService (Instagram client created internally per-account)
            message_service = MessageService()

            try:
                # Send message via MessageService
                sent_message = await message_service.send_message(
                    uow=uow,
                    account_id=AccountId(account_id),
                    recipient_id=InstagramUserId(recipient_id),
                    message_text=message,
                    attachment_url=attachment_url,
                    attachment_mime_type=file.content_type if file else None,
                    idempotency_key=IdempotencyKey(idempotency_key)
                )

                # Update CRM tracking record
                outbound_message.status = "sent"
                outbound_message.instagram_message_id = sent_message.id.value

                logger.info(f"✅ Message sent via MessageService: {message_id} (ig_msg_id: {sent_message.id.value})")

                # Schedule SSE broadcast as post-commit hook
                async def broadcast_sse():
                    try:
                        message_data = {
                            "id": sent_message.id.value,
                            "tracking_message_id": outbound_message.id,
                            "sender_id": sent_message.sender_id.value,
                            "recipient_id": sent_message.recipient_id.value,
                            "text": sent_message.message_text or '',
                            "direction": "outbound",
                            "timestamp": sent_message.timestamp.isoformat(),
                            "status": "sent",
                            "instagram_account_id": account_id
                        }

                        # Include attachment if present
                        if sent_message.attachments:
                            attachments_data = []
                            for att in sent_message.attachments:
                                attachments_data.append({
                                    "id": att.id.value,
                                    "media_type": att.media_type,
                                    "media_url": att.media_url,
                                    "media_url_local": att.media_url_local,
                                    "media_mime_type": att.media_mime_type,
                                    "attachment_index": att.attachment_index
                                })
                            message_data["attachments"] = attachments_data

                        await broadcast_new_message(message_data)
                    except Exception as sse_error:
                        logger.error(f"Failed to broadcast SSE message: {sse_error}")

                uow.add_post_commit_hook(broadcast_sse)

                # Commit transaction (triggers post-commit hooks)
                await uow.commit()

            except (InstagramAPIError, ValueError, AccountNotFoundError, Exception) as e:
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
                elif isinstance(e, AccountNotFoundError):
                    outbound_message.error_code = "account_not_found"
                    outbound_message.error_message = str(e)
                elif isinstance(e, ValueError):
                    # Covers missing_token and token_decrypt_error from MessageService
                    outbound_message.error_code = "configuration_error"
                    outbound_message.error_message = str(e)
                else:
                    outbound_message.error_code = "unexpected_error"
                    outbound_message.error_message = str(e)

                logger.error(f"❌ Failed to send message {message_id}: {outbound_message.error_message}")

                # Broadcast failure to SSE clients
                try:
                    await broadcast_message_status(message_id, "failed")
                except Exception as sse_error:
                    logger.error(f"Failed to broadcast SSE status: {sse_error}")

        # Commit CRM tracking record (after UoW context exits)
        await db.commit()

    except Exception as outer_error:
        logger.error(f"❌ Unexpected error in send_message: {outer_error}", exc_info=True)
        await db.rollback()
    
    # 7. Return response with current status (including attachment info)
    return SendMessageResponse(
        message_id=outbound_message.id,
        status=outbound_message.status,
        created_at=outbound_message.created_at,
        attachment_url=attachment_url,  # Will be None if no file uploaded
        attachment_type=attachment_type,  # Will be None if no file uploaded
        attachment_local_path=f"media/outbound/{account_id}/{unique_filename}" if attachment_url else None
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
