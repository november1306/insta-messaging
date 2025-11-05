"""
User-defined auto-reply rules.

This module contains the business logic for determining when and how to reply
to incoming messages. Rules are defined here and can be easily modified without
touching the core webhook system.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def should_reply(message_text: str) -> bool:
    """
    Determine if a message should trigger an auto-reply.
    
    Args:
        message_text: The text content of the incoming message
        
    Returns:
        True if the message should trigger a reply, False otherwise
    """
    # Rule: Reply to messages containing "order66" (case-insensitive)
    trigger_keyword = "order66"
    
    if trigger_keyword.lower() in message_text.lower():
        logger.info(f"🎯 Trigger keyword '{trigger_keyword}' detected")
        return True
    
    return False


def get_reply_text(message_text: str, username: Optional[str] = None) -> Optional[str]:
    """
    Get the reply text for a given message.
    
    Args:
        message_text: The text content of the incoming message
        username: Optional Instagram username of the sender (for personalization)
        
    Returns:
        The reply text to send, or None if no reply should be sent
    """
    # Rule: "order66" keyword triggers confirmation message
    if "order66" in message_text.lower():
        if username:
            return f"Order 66 confirmed, @{username}! Your request has been received."
        else:
            # Fallback if username not available
            return "Order 66 confirmed! Your request has been received."
    
    # No matching rule
    return None
