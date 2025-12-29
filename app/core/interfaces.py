"""
Core interfaces for Instagram Messenger Automation.

Updated to use new domain models from app/domain/entities.py

Note: The Message class here is a legacy interface for backward compatibility
with WebhookForwarder. New code should use app.domain.entities.Message instead.
"""
from abc import ABC, abstractmethod
from typing import Optional, List, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime

# Import domain models
if TYPE_CHECKING:
    from app.domain.entities import Message as DomainMessage, Conversation
    from app.domain.value_objects import MessageId, AccountId, IdempotencyKey
    from app.db.models import Account


@dataclass
class Message:
    """
    Legacy Message interface for backward compatibility.

    Used by: WebhookForwarder, CRM integration

    TODO: Replace with domain.entities.Message in future refactoring.
    This is a simple DTO (Data Transfer Object) without business logic.
    """
    id: str
    sender_id: str
    recipient_id: str
    message_text: Optional[str]
    direction: str
    timestamp: datetime


class IMessageRepository(ABC):
    """
    Interface for message storage and retrieval.

    Implementations must handle:
    - Message persistence with attachments
    - Idempotency checking
    - Conversation grouping
    """

    @abstractmethod
    async def save(self, message: 'Message') -> 'Message':
        """
        Save a message with attachments.

        Args:
            message: Domain Message entity

        Returns:
            Saved message

        Raises:
            DuplicateMessageError: If message ID already exists
        """
        pass

    @abstractmethod
    async def get_by_id(self, message_id: 'MessageId') -> Optional['Message']:
        """
        Get message by ID with attachments.

        Args:
            message_id: Message identifier

        Returns:
            Message if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_idempotency_key(
        self,
        idempotency_key: 'IdempotencyKey'
    ) -> Optional['Message']:
        """
        Get message by idempotency key (for duplicate detection).

        Args:
            idempotency_key: Idempotency key

        Returns:
            Message if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_conversations_for_account(
        self,
        account_id: 'AccountId',
        limit: int = 50
    ) -> List['Conversation']:
        """
        Get conversations for an account.

        Args:
            account_id: Account identifier
            limit: Maximum number of conversations to return

        Returns:
            List of conversations (latest message per contact)
        """
        pass


class IAccountRepository(ABC):
    """Interface for account storage and retrieval"""

    @abstractmethod
    async def get_by_id(self, account_id: str) -> Optional['Account']:
        """Get account by database ID"""
        pass

    @abstractmethod
    async def get_by_instagram_id(self, instagram_id: str) -> Optional['Account']:
        """Get account by Instagram account ID"""
        pass

    @abstractmethod
    async def get_by_messaging_channel_id(
        self,
        channel_id: str
    ) -> Optional['Account']:
        """Get account by messaging channel ID"""
        pass
