"""
AccountIdentity - Unified ID resolution for Instagram accounts.

This dataclass encapsulates the complex ID handling logic for Instagram business accounts.
It provides a single source of truth for:
- Effective channel ID resolution (messaging_channel_id or instagram_account_id fallback)
- Business ID detection (for determining message direction)
- Direction classification (inbound vs outbound)
- Customer identification from message participants

See: .claude/ACCOUNT_ID_GUIDE.md for complete ID type documentation.
"""

from dataclasses import dataclass
from typing import Literal, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from app.db.models import Account


@dataclass(frozen=True)
class AccountIdentity:
    """
    Immutable identity resolver for an Instagram business account.

    Centralizes the ID fallback logic that was previously scattered across:
    - account_linking_service.py (_sync_conversation_history)
    - ui.py (sync_messages_from_instagram)
    - webhooks.py (direction detection)

    Key insight: Instagram uses TWO different IDs for the same business account:
    - instagram_account_id: From OAuth profile API (stable, used for Graph API calls)
    - messaging_channel_id: From webhook recipient.id (may differ, used for routing)

    This class abstracts away the complexity of handling both IDs.

    Usage:
        identity = AccountIdentity.from_account(account)
        channel_id = identity.effective_channel_id  # Always returns a valid ID
        direction = identity.detect_direction(sender_id)  # 'inbound' or 'outbound'
    """

    account_id: str           # Database account ID (acc_xxx)
    instagram_account_id: str  # OAuth profile ID (from Instagram API)
    messaging_channel_id: Optional[str]  # Webhook routing ID (may be None)

    @property
    def effective_channel_id(self) -> str:
        """
        Get the effective messaging channel ID.

        This is the ID that should be used for:
        - Message routing and filtering
        - Conversation grouping in the UI
        - Direction detection (sender vs recipient)

        Returns messaging_channel_id if set, otherwise falls back to instagram_account_id.
        This fallback is needed because messaging_channel_id is only populated after
        either a webhook arrives or conversation sync discovers a different ID.
        """
        return self.messaging_channel_id or self.instagram_account_id

    @property
    def business_ids(self) -> set[str]:
        """
        Get all possible business IDs for this account.

        Instagram may use either ID when identifying the business account in:
        - Webhook payloads (sender.id or recipient.id)
        - Conversation API responses (participant.id)

        Returns a set for O(1) membership testing.
        """
        ids = {self.instagram_account_id}
        if self.messaging_channel_id:
            ids.add(self.messaging_channel_id)
        return ids

    def is_business_id(self, instagram_id: str) -> bool:
        """
        Check if an Instagram ID belongs to this business account.

        Replaces the scattered double comparisons:
            sender_id == messaging_channel_id or sender_id == account.instagram_account_id

        Args:
            instagram_id: An Instagram user ID to check

        Returns:
            True if the ID matches any known business ID for this account
        """
        return instagram_id in self.business_ids

    def detect_direction(self, sender_id: str) -> Literal['inbound', 'outbound']:
        """
        Determine message direction based on sender ID.

        Args:
            sender_id: Instagram user ID of the message sender

        Returns:
            'outbound' if the business sent the message,
            'inbound' if a customer sent the message
        """
        return 'outbound' if self.is_business_id(sender_id) else 'inbound'

    def identify_other_party(
        self,
        sender_id: str,
        recipient_id: str
    ) -> str:
        """
        Identify the customer ID from a message's sender/recipient pair.

        Given a message, this returns the ID that is NOT the business account
        (i.e., the customer's Instagram user ID).

        Args:
            sender_id: Instagram user ID of the message sender
            recipient_id: Instagram user ID of the message recipient

        Returns:
            The Instagram user ID of the non-business party (customer)
        """
        if self.is_business_id(sender_id):
            return recipient_id
        return sender_id

    def normalize_message_ids(
        self,
        sender_id: str,
        customer_id: str
    ) -> tuple[str, str]:
        """
        Normalize sender and recipient IDs for consistent storage.

        Messages should be stored with consistent IDs:
        - Always use effective_channel_id for the business account
        - Use the actual customer ID for the customer

        This ensures messages can be filtered by effective_channel_id
        regardless of which ID Instagram originally used.

        Args:
            sender_id: Original sender ID from Instagram
            customer_id: Identified customer ID

        Returns:
            Tuple of (normalized_sender_id, normalized_recipient_id)
        """
        if self.is_business_id(sender_id):
            # Outbound: business sent to customer
            return (self.effective_channel_id, customer_id)
        else:
            # Inbound: customer sent to business
            return (sender_id, self.effective_channel_id)

    @classmethod
    def from_account(cls, account: "Account") -> "AccountIdentity":
        """
        Create AccountIdentity from an Account database model.

        Args:
            account: SQLAlchemy Account model instance

        Returns:
            Frozen AccountIdentity instance
        """
        return cls(
            account_id=account.id,
            instagram_account_id=account.instagram_account_id,
            messaging_channel_id=account.messaging_channel_id
        )
