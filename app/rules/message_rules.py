"""
Simple message rules - KISS principle.

Admin: Edit this file to add/modify auto-reply rules.
Just use simple if/elif/else logic.
"""
from typing import Optional


def get_reply(message_text: str) -> Optional[str]:
    """
    Get reply for a message based on simple if/elif/else rules.
    
    Use {username} placeholder in reply text for personalization.
    The webhook handler will replace it with the actual username.
    
    Args:
        message_text: The incoming message text
        
    Returns:
        Reply text with optional {username} placeholder, or None if no rule matches
    """
    # Convert to lowercase for case-insensitive matching
    msg = message_text.lower()
    
    # Rule 1: order66 keyword
    if "order66" in msg:
        # Use {username} placeholder - webhook handler will replace it
        return "Order 66 confirmed, {username}! Your request has been received."
    
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
