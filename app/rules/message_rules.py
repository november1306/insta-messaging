"""
Simple message rules - KISS principle.

Admin: Edit this file to add/modify auto-reply rules.
Just use simple if/elif/else logic.
"""
from typing import Optional


def get_reply(message_text: str, username: Optional[str] = None) -> Optional[str]:
    """
    Get reply for a message based on simple if/elif/else rules.
    
    Args:
        message_text: The incoming message text
        username: Optional Instagram username for personalization
        
    Returns:
        Reply text, or None if no rule matches
    """
    # Convert to lowercase for case-insensitive matching
    msg = message_text.lower()
    
    # Rule 1: order66 keyword
    if "order66" in msg:
        if username:
            return f"Order 66 confirmed, @{username}! Your request has been received."
        else:
            return "Order 66 confirmed! Your request has been received."
    
    # Rule 2: Help command (disabled - uncomment to enable)
    # elif msg.strip() == "help":
    #     return "Available commands:\n- order66: Execute order\n- help: Show this message"
    
    # Rule 3: Greeting (disabled - uncomment to enable)
    # elif "hello" in msg or "hi" in msg:
    #     if username:
    #         return f"Hello @{username}! How can we help you today?"
    #     else:
    #         return "Hello! How can we help you today?"
    
    # No rule matched
    return None
