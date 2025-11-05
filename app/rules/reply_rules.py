"""
User-defined auto-reply rules.

ADMIN: Edit app/rules/message_rules.py to add/modify reply rules.
This file just provides a simple interface.
"""
from typing import Optional
from app.rules.message_rules import get_reply


def get_reply_text(message_text: str) -> Optional[str]:
    """
    Get the reply text for a given message.
    
    Returns None if no rule matches (no reply should be sent).
    Reply may contain {username} placeholder for personalization.
    
    Args:
        message_text: The text content of the incoming message
        
    Returns:
        The reply text (with optional {username} placeholder), or None if no reply should be sent
    """
    return get_reply(message_text)
