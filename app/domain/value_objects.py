"""
Value Objects for type-safe ID handling.

Value objects are immutable, self-validating, and enforce business rules.
They prevent ID type confusion between:
- Database account IDs (acc_xxx)
- Instagram user IDs (numeric PSIDs)
- Messaging channel IDs (routing identifiers)
- Message IDs (Instagram message identifiers)

See: .claude/ACCOUNT_ID_GUIDE.md for complete ID type documentation.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AccountId:
    """
    Database account ID value object.

    Format: acc_{random_id}
    Example: acc_89baed550ed9, acc_2d32237c32c7

    Used for:
    - Internal API calls
    - User permissions (UserAccount lookups)
    - Database foreign keys
    - API request parameters (account_id query param)
    """

    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("AccountId cannot be empty")
        if not self.value.startswith("acc_"):
            raise ValueError(
                f"Invalid AccountId format: {self.value}. "
                f"Must start with 'acc_' prefix."
            )
        if len(self.value) < 5:  # acc_ + at least 1 char
            raise ValueError(f"AccountId too short: {self.value}")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"AccountId('{self.value}')"


@dataclass(frozen=True)
class InstagramUserId:
    """
    Instagram user PSID (Page-Scoped ID) value object.

    Format: Numeric string (17-20 digits)
    Example: 24370771369265571, 1558635688632972

    Used for:
    - Instagram Graph API calls
    - Message sender_id and recipient_id
    - Webhook payloads (sender.id, recipient.id)
    - Customer identification

    Note: This is Instagram's official user/page identifier.
    """

    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("InstagramUserId cannot be empty")
        if not self.value.isdigit():
            raise ValueError(
                f"Invalid InstagramUserId format: {self.value}. "
                f"Must be numeric string."
            )
        if len(self.value) < 10:  # Instagram IDs are typically 17-20 digits
            raise ValueError(
                f"InstagramUserId too short: {self.value}. "
                f"Expected at least 10 digits."
            )

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"InstagramUserId('{self.value}')"


@dataclass(frozen=True)
class MessagingChannelId:
    """
    Messaging channel ID value object.

    Format: Numeric string (17-20 digits)
    Source: Webhook entry.id field

    Used for:
    - Routing webhook messages to correct account
    - Message filtering (recipient_id for inbound messages)
    - Account binding (Account.messaging_channel_id)

    Critical: This is the ONLY reliable routing identifier for multi-tenant setups.
    Different from instagram_account_id (which can be shared by multiple OAuth users).

    See: ACCOUNT_ID_GUIDE.md "Webhook Routing & messaging_channel_id" section
    """

    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("MessagingChannelId cannot be empty")
        if not self.value.isdigit():
            raise ValueError(
                f"Invalid MessagingChannelId format: {self.value}. "
                f"Must be numeric string."
            )
        if len(self.value) < 10:
            raise ValueError(
                f"MessagingChannelId too short: {self.value}. "
                f"Expected at least 10 digits."
            )

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"MessagingChannelId('{self.value}')"


@dataclass(frozen=True)
class MessageId:
    """
    Instagram message ID value object.

    Format: Various Instagram formats
    Examples:
    - mid_abc123def456  (common format)
    - aWdfZAG1f...AZDZD  (base64-like format)
    - Instagram assigns these IDs

    Used for:
    - Primary key in messages table
    - Attachment file naming (mid_abc123_0.jpg)
    - Idempotency tracking
    """

    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("MessageId cannot be empty")
        # Instagram message IDs can have various formats
        # We just enforce non-empty and reasonable length
        if len(self.value) < 3:
            raise ValueError(f"MessageId too short: {self.value}")
        if len(self.value) > 200:
            raise ValueError(f"MessageId too long: {self.value}")

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"MessageId('{self.value}')"


@dataclass(frozen=True)
class AttachmentId:
    """
    Attachment ID value object.

    Format: {message_id}_{attachment_index}
    Example: mid_abc123_0, mid_abc123_1

    Used for:
    - Primary key in message_attachments table
    - Filename generation (mid_abc123_0.jpg)
    - Media serving endpoint (/media/attachments/{attachment_id})
    """

    message_id: MessageId
    index: int

    def __post_init__(self):
        if self.index < 0:
            raise ValueError(f"Attachment index must be >= 0, got {self.index}")

    @property
    def value(self) -> str:
        """Get attachment ID as string: message_id_index"""
        return f"{self.message_id.value}_{self.index}"

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"AttachmentId('{self.value}')"

    @classmethod
    def from_string(cls, attachment_id: str) -> "AttachmentId":
        """
        Parse attachment ID from string format.

        Args:
            attachment_id: String like "mid_abc123_0"

        Returns:
            AttachmentId instance

        Raises:
            ValueError: If format is invalid
        """
        parts = attachment_id.rsplit("_", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid AttachmentId format: {attachment_id}. "
                f"Expected format: message_id_index"
            )

        message_id_str, index_str = parts

        try:
            index = int(index_str)
        except ValueError:
            raise ValueError(
                f"Invalid attachment index in {attachment_id}: {index_str} "
                f"is not a number"
            )

        return cls(message_id=MessageId(message_id_str), index=index)


@dataclass(frozen=True)
class IdempotencyKey:
    """
    Idempotency key value object for duplicate request detection.

    Format: Any string (typically UUID or client-generated)
    Example: req_abc123, 550e8400-e29b-41d4-a716-446655440000

    Used for:
    - CRM API send message deduplication
    - Prevents duplicate sends from retries
    """

    value: str

    def __post_init__(self):
        if not self.value:
            raise ValueError("IdempotencyKey cannot be empty")
        if len(self.value) > 100:
            raise ValueError(
                f"IdempotencyKey too long: {len(self.value)} chars. Max 100."
            )

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"IdempotencyKey('{self.value}')"


# Type conversion helpers for database layer
def optional_account_id(value: Optional[str]) -> Optional[AccountId]:
    """Convert optional string to AccountId"""
    return AccountId(value) if value else None


def optional_instagram_user_id(value: Optional[str]) -> Optional[InstagramUserId]:
    """Convert optional string to InstagramUserId"""
    return InstagramUserId(value) if value else None


def optional_message_id(value: Optional[str]) -> Optional[MessageId]:
    """Convert optional string to MessageId"""
    return MessageId(value) if value else None


def optional_idempotency_key(value: Optional[str]) -> Optional[IdempotencyKey]:
    """Convert optional string to IdempotencyKey"""
    return IdempotencyKey(value) if value else None
