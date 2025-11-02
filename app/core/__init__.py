"""Core module containing interfaces and domain models."""

from app.core.interfaces import (
    # Enums
    AccountStatus,
    MessageDirection,
    MessageType,
    MessageStatus,
    ConversationStatus,
    TriggerType,
    
    # Domain Models
    InstagramBusinessAccount,
    Message,
    Conversation,
    ResponseRule,
    InboundMessage,
    SendMessageResponse,
    
    # Repository Interfaces
    IAccountRepository,
    IMessageRepository,
    IConversationRepository,
    IRuleRepository,
    
    # Messaging Interfaces
    IMessageReceiver,
    IMessageSender,
)

__all__ = [
    # Enums
    "AccountStatus",
    "MessageDirection",
    "MessageType",
    "MessageStatus",
    "ConversationStatus",
    "TriggerType",
    
    # Domain Models
    "InstagramBusinessAccount",
    "Message",
    "Conversation",
    "ResponseRule",
    "InboundMessage",
    "SendMessageResponse",
    
    # Repository Interfaces
    "IAccountRepository",
    "IMessageRepository",
    "IConversationRepository",
    "IRuleRepository",
    
    # Messaging Interfaces
    "IMessageReceiver",
    "IMessageSender",
]
