"""
Core interfaces for Instagram Messenger Automation.

These abstract base classes define the contracts that all implementations must follow.
All interfaces are account-aware to support multiple Instagram business accounts.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import datetime
from enum import Enum


# Enums for domain models
class AccountStatus(str, Enum):
    """Status of an Instagram business account."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class MessageDirection(str, Enum):
    """Direction of a message."""
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageType(str, Enum):
    """Type of message content."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    STICKER = "sticker"
    STORY_REPLY = "story_reply"
    UNSUPPORTED = "unsupported"


class MessageStatus(str, Enum):
    """Status of a message."""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class ConversationStatus(str, Enum):
    """Status of a conversation."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    BLOCKED = "blocked"


class TriggerType(str, Enum):
    """Type of response rule trigger."""
    KEYWORD = "keyword"
    PATTERN = "pattern"
    INTENT = "intent"


# Domain Models (Data Classes)
class InstagramBusinessAccount:
    """Domain model for Instagram business account."""
    def __init__(
        self,
        id: str,
        username: str,
        display_name: str,
        access_token_encrypted: str,
        app_secret_encrypted: str,
        webhook_verify_token: str,
        status: AccountStatus = AccountStatus.ACTIVE,
        settings: Optional[dict] = None,
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None
    ):
        self.id = id
        self.username = username
        self.display_name = display_name
        self.access_token_encrypted = access_token_encrypted
        self.app_secret_encrypted = app_secret_encrypted
        self.webhook_verify_token = webhook_verify_token
        self.status = status
        self.settings = settings or {}
        self.created_at = created_at
        self.updated_at = updated_at


class Message:
    """Domain model for a message."""
    def __init__(
        self,
        id: str,
        account_id: str,
        conversation_id: str,
        direction: MessageDirection,
        sender_id: str,
        recipient_id: str,
        message_text: Optional[str] = None,
        message_type: MessageType = MessageType.TEXT,
        status: MessageStatus = MessageStatus.DELIVERED,
        metadata: Optional[dict] = None,
        timestamp: Optional[datetime] = None,
        created_at: Optional[datetime] = None
    ):
        self.id = id
        self.account_id = account_id
        self.conversation_id = conversation_id
        self.direction = direction
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.message_text = message_text
        self.message_type = message_type
        self.status = status
        self.metadata = metadata or {}
        self.timestamp = timestamp
        self.created_at = created_at


class Conversation:
    """Domain model for a conversation."""
    def __init__(
        self,
        id: str,
        account_id: str,
        participant_id: str,
        participant_username: Optional[str] = None,
        status: ConversationStatus = ConversationStatus.ACTIVE,
        last_message_at: Optional[datetime] = None,
        message_count: int = 0,
        metadata: Optional[dict] = None,
        created_at: Optional[datetime] = None
    ):
        self.id = id
        self.account_id = account_id
        self.participant_id = participant_id
        self.participant_username = participant_username
        self.status = status
        self.last_message_at = last_message_at
        self.message_count = message_count
        self.metadata = metadata or {}
        self.created_at = created_at


class ResponseRule:
    """Domain model for a response rule."""
    def __init__(
        self,
        id: int,
        account_id: str,
        name: str,
        trigger_type: TriggerType,
        trigger_value: str,
        response_template: str,
        priority: int = 0,
        is_active: bool = True,
        conditions: Optional[dict] = None,
        created_at: Optional[datetime] = None
    ):
        self.id = id
        self.account_id = account_id
        self.name = name
        self.trigger_type = trigger_type
        self.trigger_value = trigger_value
        self.response_template = response_template
        self.priority = priority
        self.is_active = is_active
        self.conditions = conditions or {}
        self.created_at = created_at


class InboundMessage:
    """Represents an incoming message from Instagram webhook."""
    def __init__(
        self,
        message_id: str,
        sender_id: str,
        recipient_id: str,
        text: Optional[str] = None,
        timestamp: Optional[int] = None,
        message_type: MessageType = MessageType.TEXT,
        metadata: Optional[dict] = None
    ):
        self.message_id = message_id
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.text = text
        self.timestamp = timestamp
        self.message_type = message_type
        self.metadata = metadata or {}


class SendMessageResponse:
    """Response from sending a message."""
    def __init__(
        self,
        success: bool,
        message_id: Optional[str] = None,
        recipient_id: Optional[str] = None,
        error: Optional[str] = None
    ):
        self.success = success
        self.message_id = message_id
        self.recipient_id = recipient_id
        self.error = error


# Repository Interfaces

class IAccountRepository(ABC):
    """Interface for Instagram business account repository."""
    
    @abstractmethod
    async def get_by_id(self, account_id: str) -> Optional[InstagramBusinessAccount]:
        """Get account by ID."""
        pass
    
    @abstractmethod
    async def get_by_username(self, username: str) -> Optional[InstagramBusinessAccount]:
        """Get account by username."""
        pass
    
    @abstractmethod
    async def create(self, account: InstagramBusinessAccount) -> InstagramBusinessAccount:
        """Create new account."""
        pass
    
    @abstractmethod
    async def update(self, account: InstagramBusinessAccount) -> InstagramBusinessAccount:
        """Update existing account."""
        pass
    
    @abstractmethod
    async def get_active_accounts(self) -> List[InstagramBusinessAccount]:
        """Get all active accounts."""
        pass


class IMessageRepository(ABC):
    """Interface for message repository (account-scoped)."""
    
    @abstractmethod
    async def create(self, account_id: str, message: Message) -> Message:
        """Store message for specific account."""
        pass
    
    @abstractmethod
    async def get_conversation_history(
        self, 
        account_id: str,
        conversation_id: str, 
        limit: int = 10
    ) -> List[Message]:
        """Get conversation history for specific account."""
        pass


class IConversationRepository(ABC):
    """Interface for conversation repository (account-scoped)."""
    
    @abstractmethod
    async def get_or_create(
        self, 
        account_id: str,
        participant_id: str
    ) -> Conversation:
        """Get or create conversation for specific account."""
        pass
    
    @abstractmethod
    async def update_last_message_time(
        self, 
        account_id: str,
        conversation_id: str
    ) -> None:
        """Update last message timestamp."""
        pass


class IRuleRepository(ABC):
    """Interface for response rule repository (account-scoped)."""
    
    @abstractmethod
    async def get_active_rules(self, account_id: str) -> List[ResponseRule]:
        """Get active rules for specific account."""
        pass
    
    @abstractmethod
    async def find_matching_rule(
        self, 
        account_id: str,
        message_text: str
    ) -> Optional[ResponseRule]:
        """Find matching rule for specific account."""
        pass


# Messaging Interfaces

class IMessageReceiver(ABC):
    """Interface for receiving and processing Instagram messages (account-aware)."""
    
    @abstractmethod
    async def receive_webhook(self, account_id: str, payload: dict) -> None:
        """Process incoming webhook for specific account."""
        pass
    
    @abstractmethod
    async def validate_signature(self, account_id: str, signature: str, body: str) -> bool:
        """Validate webhook signature using account-specific secret."""
        pass
    
    @abstractmethod
    async def process_message(self, account_id: str, message: InboundMessage) -> None:
        """Handle a single incoming message for specific account."""
        pass


class IMessageSender(ABC):
    """Interface for sending Instagram messages (account-aware)."""
    
    @abstractmethod
    async def send_message(
        self, 
        account_id: str,
        recipient_id: str, 
        message_text: str
    ) -> SendMessageResponse:
        """Send message using specific account credentials."""
        pass
    
    @abstractmethod
    async def send_template(
        self, 
        account_id: str,
        recipient_id: str, 
        template_id: str,
        params: dict
    ) -> SendMessageResponse:
        """Send template message using specific account."""
        pass
