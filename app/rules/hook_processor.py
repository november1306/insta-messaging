"""
Simple hook processor for message automation.

Loads hooks from hooks.json and evaluates them against incoming messages.
"""
import json
import logging
import os
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class HookProcessor:
    """Processes message hooks from JSON configuration"""
    
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = Path(__file__).parent / "hooks.json"
        
        self.config_path = config_path
        self.hooks = []
        self.load_hooks()
    
    def load_hooks(self):
        """Load hooks from JSON file"""
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
                all_hooks = data.get("hooks", [])
                
                # Filter enabled hooks and sort by priority
                self.hooks = [h for h in all_hooks if h.get("enabled", False)]
                self.hooks.sort(key=lambda h: h.get("priority", 0), reverse=True)
                
                logger.info(f"✅ Loaded {len(self.hooks)} active hooks from {self.config_path}")
        except Exception as e:
            logger.error(f"❌ Failed to load hooks: {e}")
            self.hooks = []
    
    def check_condition(self, message_text: str, condition: Dict[str, Any]) -> bool:
        """
        Check if message matches condition.
        
        Args:
            message_text: The message to check
            condition: Condition config with 'type', 'value', 'case_sensitive'
        
        Returns:
            True if condition matches
        """
        cond_type = condition.get("type")
        cond_value = condition.get("value", "")
        case_sensitive = condition.get("case_sensitive", False)
        
        # Prepare for comparison
        text = message_text if case_sensitive else message_text.lower()
        value = cond_value if case_sensitive else cond_value.lower()
        
        if cond_type == "contains":
            return value in text
        elif cond_type == "exact":
            return text.strip() == value.strip()
        elif cond_type == "starts_with":
            return text.startswith(value)
        elif cond_type == "ends_with":
            return text.endswith(value)
        else:
            logger.warning(f"Unknown condition type: {cond_type}")
            return False
    
    def find_matching_hook(self, message_text: str) -> Optional[Dict[str, Any]]:
        """
        Find first matching hook for message.
        
        Args:
            message_text: The message to match
        
        Returns:
            Matching hook dict or None
        """
        for hook in self.hooks:
            condition = hook.get("condition", {})
            if self.check_condition(message_text, condition):
                logger.info(f"🎯 Hook matched: '{hook.get('name')}'")
                return hook
        
        return None
    
    def get_reply_text(self, message_text: str, username: Optional[str] = None) -> Optional[str]:
        """
        Get reply text for message based on hooks.
        
        Args:
            message_text: The message text
            username: Optional username for personalization
        
        Returns:
            Reply text or None if no match
        """
        hook = self.find_matching_hook(message_text)
        
        if not hook:
            return None
        
        action = hook.get("action", {})
        
        if action.get("type") != "reply":
            return None
        
        # Get message template
        if username and "{username}" in action.get("message", ""):
            reply = action.get("message", "")
            return reply.replace("{username}", username)
        else:
            # Use fallback or main message
            return action.get("message_fallback") or action.get("message")


# Global instance
_processor: Optional[HookProcessor] = None


def get_processor() -> HookProcessor:
    """Get global hook processor instance"""
    global _processor
    if _processor is None:
        _processor = HookProcessor()
    return _processor


def reload_hooks():
    """Reload hooks from file"""
    global _processor
    _processor = HookProcessor()
    logger.info("🔄 Hooks reloaded")
