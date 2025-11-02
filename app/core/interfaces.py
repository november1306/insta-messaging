"""
Core interfaces for Instagram Messenger Automation.

YAGNI: Start with minimal abstractions. Add complexity when needed.
"""
from abc import ABC, abstractmethod
from typing import Optional
from datetime import datetime


# Simple domain model for messages
class Message:
    """Domain model for a message."""
    def __init__(
        self,
        id: str,
        sender_id: str,
        recipient_id: str,
        message_text: str,
        direction: str,  # 'inbound' or 'outbound'
        timestamp: datetime,
        created_at: Optional[datetime] = None
    ):
        self.id = id
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.message_text = message_text
        self.direction = direction
        self.timestamp = timestamp
        self.created_at = created_at or datetime.now()


# Repository interface (add when we actually implement it)
class IMessageRepository(ABC):
    """Interface for message storage."""
    
    @abstractmethod
    async def save(self, message: Message) -> Message:
        """Save a message to storage."""
        pass
    
    @abstractmethod
    async def get_by_id(self, message_id: str) -> Optional[Message]:
        """Get a message by ID."""
        pass
