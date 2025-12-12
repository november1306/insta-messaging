"""
Core interfaces for Instagram Messenger Automation.

YAGNI: Start with minimal abstractions. Add complexity when needed.
"""
from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime, timezone
from dataclasses import dataclass


@dataclass
class Attachment:
    """
    Single media attachment (image, video, audio, file).

    Represents one attachment in a message. Messages can have multiple attachments
    (Instagram supports sending multiple images/videos in one message).
    """
    id: str                          # Format: "mid_abc123_0", "mid_abc123_1"
    message_id: str                  # Parent message ID
    attachment_index: int            # Order: 0, 1, 2... (preserves display order)
    media_type: str                  # "image", "video", "audio", "file", "like_heart"
    media_url: str                   # Instagram CDN URL (expires in 7 days)
    media_url_local: Optional[str]   # Our local copy: "media/page456/user123/mid_abc123_0.jpg" (permanent)
    media_mime_type: Optional[str]   # "image/jpeg", "video/mp4" (detected when downloaded)


# Simple domain model for messages
class Message:
    """
    Domain model for a message with optional media attachments.

    A message can be:
    - Text-only (attachments=None or [])
    - Media-only (message_text=None, attachments=[...])
    - Both (message_text="Caption", attachments=[...])
    """
    def __init__(
        self,
        id: str,
        sender_id: str,
        recipient_id: str,
        message_text: Optional[str],  # Made optional - can be None for media-only messages
        direction: str,  # 'inbound' or 'outbound'
        timestamp: datetime,
        created_at: Optional[datetime] = None,
        attachments: Optional[List[Attachment]] = None  # NEW: List of attachments
    ):
        self.id = id
        self.sender_id = sender_id
        self.recipient_id = recipient_id
        self.message_text = message_text
        self.direction = direction
        self.timestamp = timestamp
        self.created_at = created_at or datetime.now(timezone.utc)
        self.attachments = attachments if attachments is not None else []  # Default to empty list


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
