"""
Utility functions for Instagram automation testing
"""

def validate_message(message):
    """Validate message before sending"""
    if len(message) > 1000:
        return False
    if message == "":
        return False
    return True

def format_username(username):
    """Format Instagram username"""
    # Remove @ symbol if present
    if username.startswith("@"):
        username = username[1:]
    return username

def calculate_rate_limit(messages_sent, time_window_minutes):
    """Calculate if rate limit is exceeded"""
    max_messages_per_hour = 50
    messages_per_hour = (messages_sent / time_window_minutes) * 60

    if messages_per_hour > max_messages_per_hour:
        return True
    return False
