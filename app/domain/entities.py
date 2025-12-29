"""
Domain Entities - Rich business objects with identity and lifecycle.

Entities differ from value objects in that they have:
- Identity (tracked by ID, not by value)
- Mutable state (can change over time)
- Business logic (methods that enforce invariants)

The Message entity is an aggregate root - it owns Attachments.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Literal, Optional

from .value_objects import (
    AccountId,
    AttachmentId,
    IdempotencyKey,
    InstagramUserId,
    MessageId,
)


@dataclass
class Attachment:
    """
    Attachment entity - part of Message aggregate.

    Attachments are owned by messages and cannot exist independently.
    They are deleted when the parent message is deleted (CASCADE).
    """

    id: AttachmentId
    message_id: MessageId
    attachment_index: int
    media_type: str  # 'image', 'video', 'audio', 'file', 'like_heart'
    media_url: str  # Original Instagram CDN URL (expires in 7 days)
    media_url_local: Optional[str] = None  # Local copy path
    media_mime_type: Optional[str] = None

    def __post_init__(self):
        # Validate media type
        valid_types = {'image', 'video', 'audio', 'file', 'like_heart', 'story_mention', 'reel_share'}
        if self.media_type not in valid_types:
            raise ValueError(
                f"Invalid media_type: {self.media_type}. "
                f"Must be one of {valid_types}"
            )

        # Validate attachment index matches ID
        if self.id.index != self.attachment_index:
            raise ValueError(
                f"AttachmentId index ({self.id.index}) doesn't match "
                f"attachment_index ({self.attachment_index})"
            )

        # Validate message ID matches
        if self.id.message_id != self.message_id:
            raise ValueError(
                f"AttachmentId message_id ({self.id.message_id}) doesn't match "
                f"message_id ({self.message_id})"
            )

    @property
    def is_downloaded(self) -> bool:
        """Check if attachment has been downloaded locally"""
        return self.media_url_local is not None

    @property
    def file_path(self) -> Optional[str]:
        """Get local file path if downloaded"""
        return self.media_url_local

    def __repr__(self) -> str:
        return (
            f"Attachment(id={self.id}, type={self.media_type}, "
            f"downloaded={self.is_downloaded})"
        )


@dataclass
class Message:
    """
    Message aggregate root.

    Invariants (business rules enforced by domain model):
    1. Must belong to exactly one Account
    2. sender_id and recipient_id are Instagram IDs (NEVER database account IDs)
    3. Must have text OR attachments (not both empty)
    4. Direction must be 'inbound' or 'outbound'
    5. Attachments are part of this aggregate

    Aggregate Boundary:
    - Message is the root
    - Attachments are entities within the aggregate
    - All operations on attachments go through Message
    """

    # Identity
    id: MessageId

    # Ownership (NEW: explicit FK to Account)
    account_id: AccountId

    # Participants (Instagram user IDs)
    sender_id: InstagramUserId
    recipient_id: InstagramUserId

    # Content
    message_text: Optional[str]
    direction: Literal['inbound', 'outbound']

    # Timestamps
    timestamp: datetime
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Aggregate members
    attachments: List[Attachment] = field(default_factory=list)

    # Tracking (for outbound messages)
    idempotency_key: Optional[IdempotencyKey] = None
    delivery_status: Optional[str] = None  # 'pending', 'sent', 'failed'
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def __post_init__(self):
        """Validate business rules"""
        # Business rule: Must have content
        if not self.message_text and not self.attachments:
            raise ValueError(
                "Message must have text or attachments. "
                "Cannot create empty message."
            )

        # Business rule: Valid direction
        if self.direction not in ['inbound', 'outbound']:
            raise ValueError(
                f"Invalid direction: {self.direction}. "
                f"Must be 'inbound' or 'outbound'."
            )

        # Business rule: Delivery status only for outbound
        if self.direction == 'inbound' and self.delivery_status:
            raise ValueError(
                "Inbound messages cannot have delivery_status. "
                "This field is only for outbound messages."
            )

        # Business rule: Idempotency key only for outbound
        if self.direction == 'inbound' and self.idempotency_key:
            raise ValueError(
                "Inbound messages cannot have idempotency_key. "
                "This field is only for outbound messages."
            )

        # Validate all attachments belong to this message
        for att in self.attachments:
            if att.message_id != self.id:
                raise ValueError(
                    f"Attachment {att.id} belongs to message {att.message_id}, "
                    f"but is in aggregate for message {self.id}"
                )

    # Business logic methods

    def add_attachment(self, attachment: Attachment) -> None:
        """
        Add attachment to message (maintains aggregate boundary).

        Args:
            attachment: Attachment to add

        Raises:
            ValueError: If attachment doesn't belong to this message
        """
        if attachment.message_id != self.id:
            raise ValueError(
                f"Cannot add attachment {attachment.id} to message {self.id}. "
                f"Attachment belongs to message {attachment.message_id}."
            )

        # Check for duplicate index
        existing_indexes = {att.attachment_index for att in self.attachments}
        if attachment.attachment_index in existing_indexes:
            raise ValueError(
                f"Attachment index {attachment.attachment_index} already exists"
            )

        self.attachments.append(attachment)

    def is_within_response_window(self, hours: int = 24) -> bool:
        """
        Check if message is within Instagram's response window.

        Instagram allows sending messages to users only within 24 hours
        of their last message to you.

        Args:
            hours: Response window in hours (default: 24)

        Returns:
            True if within window, False otherwise
        """
        if self.direction == 'outbound':
            # Outbound messages don't have a response window
            return False

        age = datetime.now(timezone.utc) - self.timestamp
        return age.total_seconds() < (hours * 3600)

    def mark_as_sent(self) -> None:
        """Mark outbound message as successfully sent"""
        if self.direction != 'outbound':
            raise ValueError("Can only mark outbound messages as sent")
        self.delivery_status = 'sent'
        self.error_code = None
        self.error_message = None

    def mark_as_failed(self, error_code: str, error_message: str) -> None:
        """
        Mark outbound message as failed.

        Args:
            error_code: Error code (e.g., 'user_not_found', 'window_expired')
            error_message: Human-readable error description
        """
        if self.direction != 'outbound':
            raise ValueError("Can only mark outbound messages as failed")
        self.delivery_status = 'failed'
        self.error_code = error_code
        self.error_message = error_message

    @property
    def has_attachments(self) -> bool:
        """Check if message has attachments"""
        return len(self.attachments) > 0

    @property
    def attachment_count(self) -> int:
        """Get number of attachments"""
        return len(self.attachments)

    @property
    def is_text_only(self) -> bool:
        """Check if message is text-only (no attachments)"""
        return self.message_text is not None and not self.has_attachments

    @property
    def is_media_only(self) -> bool:
        """Check if message is media-only (no text)"""
        return self.message_text is None and self.has_attachments

    @property
    def conversation_partner_id(self) -> InstagramUserId:
        """
        Get the ID of the conversation partner (other party).

        For inbound: returns sender_id (customer)
        For outbound: returns recipient_id (customer)
        """
        if self.direction == 'inbound':
            return self.sender_id
        else:
            return self.recipient_id

    def __repr__(self) -> str:
        status = f", status={self.delivery_status}" if self.delivery_status else ""
        attachments_info = f", attachments={self.attachment_count}" if self.has_attachments else ""
        return (
            f"Message(id={self.id}, direction={self.direction}, "
            f"account={self.account_id}{status}{attachments_info})"
        )


@dataclass
class Conversation:
    """
    Conversation aggregate - collection of messages with a specific contact.

    This is a read model for UI display purposes.
    Not persisted directly - computed from messages.
    """

    account_id: AccountId
    contact_id: InstagramUserId  # The other party (customer)
    contact_username: Optional[str]
    latest_message: Message
    unread_count: int = 0
    total_messages: int = 1

    @property
    def last_message_at(self) -> datetime:
        """Get timestamp of latest message"""
        return self.latest_message.timestamp

    @property
    def last_message_text(self) -> str:
        """Get preview text for latest message"""
        if self.latest_message.message_text:
            return self.latest_message.message_text
        elif self.latest_message.has_attachments:
            att_count = self.latest_message.attachment_count
            return f"📎 {att_count} attachment{'s' if att_count > 1 else ''}"
        else:
            return "(empty message)"

    def __repr__(self) -> str:
        username = self.contact_username or "Unknown"
        return (
            f"Conversation(contact={username}, "
            f"messages={self.total_messages}, unread={self.unread_count})"
        )


# Domain exceptions

class DomainError(Exception):
    """Base exception for domain layer errors"""
    pass


class InvalidMessageError(DomainError):
    """Raised when message violates business rules"""
    pass


class DuplicateMessageError(DomainError):
    """Raised when attempting to save duplicate message"""

    def __init__(self, message_id: MessageId):
        self.message_id = message_id
        super().__init__(f"Message {message_id} already exists")


class AccountNotFoundError(DomainError):
    """Raised when account doesn't exist"""

    def __init__(self, account_id: AccountId):
        self.account_id = account_id
        super().__init__(f"Account {account_id} not found")


class MessageNotFoundError(DomainError):
    """Raised when message doesn't exist"""

    def __init__(self, message_id: MessageId):
        self.message_id = message_id
        super().__init__(f"Message {message_id} not found")
