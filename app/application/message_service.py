"""
Message Service - Business logic orchestration for message operations.

This service provides a unified interface for:
- Receiving webhook messages (inbound)
- Sending messages via API (outbound)
- Idempotency handling
- Instagram API coordination
- SSE broadcasting (via post-commit hooks)

Replaces fat controllers in webhooks.py and messages.py with clean,
testable business logic.
"""

from typing import Optional, List
from datetime import datetime, timezone
import logging

from app.domain.unit_of_work import AbstractUnitOfWork
from app.domain.entities import Message, Attachment, AccountNotFoundError, DuplicateMessageError
from app.domain.value_objects import (
    AccountId,
    MessageId,
    InstagramUserId,
    AttachmentId,
    IdempotencyKey,
    MessagingChannelId
)
from app.infrastructure.cache_service import get_cached_username
from app.clients.instagram_client import InstagramClient
from app.services.encryption_service import decrypt_credential
from app.config import settings
import httpx
from pathlib import Path

logger = logging.getLogger(__name__)


def validate_attachment_path(url: str) -> Optional[str]:
    """
    Validate and normalize attachment URL path to prevent path traversal attacks.

    Args:
        url: Attachment URL or path to validate (e.g., "/media/outbound/..." or "http://host/media/outbound/...")

    Returns:
        Normalized path if valid, None if invalid or potentially malicious

    Security:
        - Prevents path traversal attacks (../../etc/passwd)
        - Ensures path stays within /media/outbound/ directory
        - Normalizes path separators (handles both / and \\)
        - Handles both full URLs and paths
    """
    if not url:
        return None

    # Extract path from full URL if needed (e.g., "http://host/media/outbound/..." -> "/media/outbound/...")
    path = url
    if url.startswith('http://') or url.startswith('https://'):
        from urllib.parse import urlparse
        parsed = urlparse(url)
        path = parsed.path

    if not path.startswith('/media/outbound/') and not path.startswith('media/outbound/'):
        return None

    # Remove leading slash for database storage (paths stored as "media/outbound/...")
    if path.startswith('/'):
        path = path[1:]

    try:
        # Security validation: check for path traversal attempts
        # Don't use Path() as it can cause issues with forward slashes on Windows
        # Just do string validation

        # Ensure the path still starts with media/outbound/
        if not path.startswith('media/outbound/'):
            logger.warning(f"⚠️ Path traversal attempt detected: {url} -> {path}")
            return None

        # Additional check: ensure no '..' segments
        if '..' in path:
            logger.warning(f"⚠️ Suspicious path detected: {url}")
            return None

        # Normalize path separators (convert backslashes to forward slashes)
        normalized_str = path.replace('\\', '/')

        return normalized_str

    except Exception as e:
        logger.error(f"❌ Invalid attachment path: {url} - {e}")
        return None


def detect_media_type(mime_type: Optional[str], url: str) -> str:
    """
    Detect media type from MIME type or URL extension.

    Args:
        mime_type: MIME type from file upload (e.g., 'image/jpeg')
        url: Attachment URL or path

    Returns:
        Media type string: 'image', 'video', 'audio', or 'file'

    Priority:
        1. MIME type (if provided and recognized)
        2. File extension from URL
        3. Default to 'file'
    """
    # Try MIME type first (most accurate)
    if mime_type:
        mime_lower = mime_type.lower()
        if mime_lower.startswith('image/'):
            return 'image'
        elif mime_lower.startswith('video/'):
            return 'video'
        elif mime_lower.startswith('audio/'):
            return 'audio'

    # Fallback to file extension
    try:
        ext = url.lower().split('.')[-1].strip()
        if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg', 'ico']:
            return 'image'
        elif ext in ['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv', 'm4v']:
            return 'video'
        elif ext in ['mp3', 'wav', 'aac', 'ogg', 'flac', 'm4a', 'wma']:
            return 'audio'
    except Exception:
        pass  # Invalid URL format, fall through to default

    # Default fallback
    return 'file'


class MessageService:
    """
    Application service for message operations.

    Orchestrates:
    - Domain logic (validation, business rules)
    - Infrastructure (persistence, external APIs)
    - Cross-cutting concerns (logging, events)

    All operations use Unit of Work for transaction management.

    Note: Instagram client is created per-account to support multi-account
    scenarios with different OAuth tokens.
    """

    def __init__(self):
        """
        Initialize message service.

        Instagram clients are created per-call with account-specific tokens
        to support multi-account scenarios.
        """
        pass

    async def receive_webhook_message(
        self,
        uow: AbstractUnitOfWork,
        messaging_channel_id: MessagingChannelId,
        instagram_message_id: str,
        sender_id: str,
        recipient_id: str,
        message_text: Optional[str],
        timestamp: datetime,
        attachments: Optional[List[dict]] = None
    ) -> Message:
        """
        Process inbound message from Instagram webhook.

        Args:
            uow: Unit of Work for transaction
            messaging_channel_id: Routing ID from webhook
            instagram_message_id: Instagram's message ID
            sender_id: Customer's Instagram user ID
            recipient_id: Our account's Instagram ID (from webhook)
            message_text: Message content
            timestamp: When message was sent
            attachments: List of attachment metadata

        Returns:
            Saved message

        Raises:
            AccountNotFoundError: If no account found for messaging_channel_id
            DuplicateMessageError: If message already exists
        """
        # 1. Find account by messaging_channel_id
        account = await uow.accounts.get_by_messaging_channel_id(
            messaging_channel_id.value
        )

        if not account:
            # Fallback: try by Instagram account ID
            account = await uow.accounts.get_by_instagram_id(recipient_id)

        if not account:
            logger.error(
                f"No account found for messaging_channel_id={messaging_channel_id}"
            )
            raise AccountNotFoundError(AccountId(f"channel:{messaging_channel_id}"))

        # 2. Create domain entities
        attachment_entities = []
        if attachments:
            for idx, att_data in enumerate(attachments):
                attachment = Attachment(
                    id=AttachmentId(
                        message_id=MessageId(instagram_message_id),
                        index=idx
                    ),
                    message_id=MessageId(instagram_message_id),
                    attachment_index=idx,
                    media_type=att_data.get('type', 'unknown'),
                    media_url=att_data['url'],
                    media_url_local=att_data.get('local_path'),
                    media_mime_type=att_data.get('mime_type')
                )
                attachment_entities.append(attachment)

        message = Message(
            id=MessageId(instagram_message_id),
            account_id=AccountId(account.id),
            sender_id=InstagramUserId(sender_id),
            recipient_id=InstagramUserId(recipient_id),
            message_text=message_text,
            direction='inbound',
            timestamp=timestamp,
            created_at=datetime.now(timezone.utc),
            attachments=attachment_entities
        )

        # 3. Save message
        try:
            saved_message = await uow.messages.save(message)
            logger.info(
                f"📨 Received webhook message: {message.id} "
                f"from {sender_id} to account {account.id}"
            )
            return saved_message

        except DuplicateMessageError:
            logger.warning(f"Webhook duplicate detected: {message.id}")
            # Return existing message
            existing = await uow.messages.get_by_id(message.id)
            return existing if existing else message

    async def send_message(
        self,
        uow: AbstractUnitOfWork,
        account_id: AccountId,
        recipient_id: InstagramUserId,
        message_text: Optional[str],
        attachment_url: Optional[str] = None,
        attachment_mime_type: Optional[str] = None,
        idempotency_key: Optional[IdempotencyKey] = None
    ) -> Message:
        """
        Send outbound message to Instagram user.

        Args:
            uow: Unit of Work for transaction
            account_id: Database account ID
            recipient_id: Customer's Instagram user ID
            message_text: Message content
            attachment_url: Optional media URL to send
            attachment_mime_type: Optional MIME type of attachment (for type detection)
            idempotency_key: For duplicate detection

        Returns:
            Sent message

        Raises:
            AccountNotFoundError: If account doesn't exist
            InstagramAPIError: If sending fails
        """
        # 1. Check idempotency
        if idempotency_key:
            existing = await uow.messages.get_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(f"🔑 Idempotency hit: {idempotency_key}")
                return existing

        # 2. Get account with OAuth token
        account = await uow.accounts.get_by_id(account_id.value)
        if not account:
            logger.error(f"Account not found: {account_id}")
            raise AccountNotFoundError(account_id)

        # 3. Decrypt access token
        if not account.access_token_encrypted:
            error_msg = "Instagram access token not configured for this account"
            logger.error(f"❌ Cannot send message: {error_msg} (account={account_id})")

            # Create failed message for tracking
            failed_message = Message(
                id=MessageId(f"failed_{datetime.now().timestamp()}"),
                account_id=account_id,
                sender_id=InstagramUserId(account.instagram_account_id),
                recipient_id=recipient_id,
                message_text=message_text or '',
                direction='outbound',
                timestamp=datetime.now(timezone.utc),
                idempotency_key=idempotency_key,
                delivery_status='failed',
                error_code='missing_token',
                error_message=error_msg
            )
            await uow.messages.save(failed_message)
            raise ValueError(error_msg)

        try:
            access_token = decrypt_credential(
                account.access_token_encrypted,
                settings.session_secret
            )
        except Exception as e:
            error_msg = f"Failed to decrypt access token: {str(e)}"
            logger.error(f"❌ Cannot send message: {error_msg} (account={account_id})")

            # Create failed message for tracking
            failed_message = Message(
                id=MessageId(f"failed_{datetime.now().timestamp()}"),
                account_id=account_id,
                sender_id=InstagramUserId(account.instagram_account_id),
                recipient_id=recipient_id,
                message_text=message_text or '',
                direction='outbound',
                timestamp=datetime.now(timezone.utc),
                idempotency_key=idempotency_key,
                delivery_status='failed',
                error_code='token_decrypt_error',
                error_message=error_msg
            )
            await uow.messages.save(failed_message)
            raise

        # 4. Send to Instagram API
        try:
            # Create Instagram client with account-specific token
            async with httpx.AsyncClient() as http_client:
                instagram_client = InstagramClient(
                    http_client=http_client,
                    access_token=access_token,
                    logger_instance=logger
                )

                if attachment_url:
                    # Detect attachment type from MIME or extension
                    attachment_type = detect_media_type(attachment_mime_type, attachment_url)

                    # Send message with attachment
                    ig_response = await instagram_client.send_message_with_attachment(
                        recipient_id=recipient_id.value,
                        attachment_url=attachment_url,
                        attachment_type=attachment_type,
                        caption_text=message_text
                    )
                else:
                    # Send text-only message
                    ig_response = await instagram_client.send_message(
                        recipient_id=recipient_id.value,
                        message_text=message_text
                    )

                logger.info(
                    f"📤 Sent to Instagram: message_id={ig_response.message_id}"
                )

        except Exception as e:
            logger.error(f"Instagram API error: {e}")

            # Create failed message for tracking
            failed_message = Message(
                id=MessageId(f"failed_{datetime.now().timestamp()}"),
                account_id=account_id,
                sender_id=InstagramUserId(account.instagram_account_id),
                recipient_id=recipient_id,
                message_text=message_text or '',
                direction='outbound',
                timestamp=datetime.now(timezone.utc),
                idempotency_key=idempotency_key,
                delivery_status='failed',
                error_code='instagram_api_error',
                error_message=str(e)
            )

            await uow.messages.save(failed_message)
            raise

        # 5. Create domain entity for successful send
        attachment_entities = []
        if attachment_url:
            # Validate and normalize attachment path (security: prevent path traversal)
            validated_local_path = validate_attachment_path(attachment_url)

            # Detect media type from MIME or extension
            media_type = detect_media_type(attachment_mime_type, attachment_url)

            # Create attachment entity for sent media
            attachment = Attachment(
                id=AttachmentId(
                    message_id=MessageId(ig_response.message_id),
                    index=0
                ),
                message_id=MessageId(ig_response.message_id),
                attachment_index=0,
                media_type=media_type,
                media_url=attachment_url,
                media_url_local=validated_local_path,
                media_mime_type=attachment_mime_type
            )
            attachment_entities.append(attachment)

        message = Message(
            id=MessageId(ig_response.message_id),
            account_id=account_id,
            sender_id=InstagramUserId(account.instagram_account_id),
            recipient_id=recipient_id,
            message_text=message_text,
            direction='outbound',
            timestamp=datetime.now(timezone.utc),
            attachments=attachment_entities,
            idempotency_key=idempotency_key,
            delivery_status='sent'
        )

        # 6. Save to database
        saved_message = await uow.messages.save(message)

        logger.info(
            f"✅ Message sent and saved: {saved_message.id} "
            f"(account={account_id}, recipient={recipient_id})"
        )

        return saved_message

    async def get_conversations(
        self,
        uow: AbstractUnitOfWork,
        account_id: AccountId,
        limit: int = 50
    ) -> List:
        """
        Get conversations for an account.

        Args:
            uow: Unit of Work
            account_id: Account ID
            limit: Max conversations to return

        Returns:
            List of conversations with enriched usernames
        """
        # Get conversations from repository
        conversations = await uow.messages.get_conversations_for_account(
            account_id,
            limit=limit
        )

        # Enrich with usernames (using cache)
        for conv in conversations:
            if not conv.contact_username:
                username = await get_cached_username(
                    conv.contact_id.value,
                    fetch_func=None  # TODO: Implement username fetching
                )
                conv.contact_username = username or conv.contact_id.value

        logger.debug(f"📬 Retrieved {len(conversations)} conversations")
        return conversations

    async def auto_reply_to_message(
        self,
        uow: AbstractUnitOfWork,
        inbound_message: Message,
        reply_text: str
    ) -> Optional[Message]:
        """
        Send automatic reply to an inbound message.

        Args:
            uow: Unit of Work
            inbound_message: The message to reply to
            reply_text: Auto-reply text

        Returns:
            Sent reply message if successful, None if failed
        """
        try:
            reply = await self.send_message(
                uow=uow,
                account_id=inbound_message.account_id,
                recipient_id=inbound_message.sender_id,  # Reply to sender
                message_text=reply_text,
                idempotency_key=IdempotencyKey(
                    f"auto_reply_{inbound_message.id.value}"
                )
            )

            logger.info(f"🤖 Auto-reply sent: {reply.id}")
            return reply

        except Exception as e:
            logger.error(f"Auto-reply failed: {e}")
            return None
