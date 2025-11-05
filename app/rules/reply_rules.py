"""
User-defined auto-reply rules.

This module contains the business logic for determining when and how to reply
to incoming messages. Rules are defined here and can be easily modified without
touching the core webhook system.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def get_reply_text(message_text: str, username: Optional[str] = None) -> Optional[str]:
    """
    Get the reply text for a given message.
    
    Returns None if no rule matches (no reply should be sent).
    
    Args:
        message_text: The text content of the incoming message
        username: Optional Instagram username of the sender (for personalization)
        
    Returns:
        The reply text to send, or None if no reply should be sent
    """
    # Rule: "order66" keyword triggers confirmation message
    if "order66" in message_text.lower():
        logger.info(f"🎯 Trigger keyword 'order66' detected")
        
        if username:
            return f"Order 66 confirmed, @{username}! Your request has been received."
        else:
            # Fallback if username not available
            return "Order 66 confirmed! Your request has been received."
    
    # No matching rule
    return None
