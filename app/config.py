"""Configuration management using environment variables"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings - YAGNI: Only what we need right now"""
    
    def __init__(self):
        # Environment
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # Instagram/Facebook credentials
        if self.environment == "production":
            self.facebook_verify_token = self._get_required("FACEBOOK_VERIFY_TOKEN")
            self.facebook_app_secret = self._get_required("FACEBOOK_APP_SECRET")
            self.instagram_page_access_token = self._get_required("INSTAGRAM_PAGE_ACCESS_TOKEN")
            self.instagram_business_account_id = self._get_required("INSTAGRAM_BUSINESS_ACCOUNT_ID")
        else:
            # Development mode: Load from .env file (never commit secrets to git)
            self.facebook_verify_token = os.getenv("FACEBOOK_VERIFY_TOKEN", "")
            self.facebook_app_secret = os.getenv("FACEBOOK_APP_SECRET", "test_secret_dev")
            self.instagram_page_access_token = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN", "")
            self.instagram_business_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
            
            # Warn if using test secret
            if self.facebook_app_secret == "test_secret_dev":
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    "⚠️  Using development test secret for webhook validation. "
                    "Set FACEBOOK_APP_SECRET in .env for production-like testing."
                )
            
            # Check for missing credentials and warn
            self._warn_missing_credentials()
        
        # Server configuration
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))
        
        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
    
    def _get_required(self, key: str) -> str:
        """Get required environment variable or raise error."""
        value = os.getenv(key)
        if not value:
            raise ValueError(
                f"Missing required environment variable: {key}. "
                f"Required in production mode."
            )
        return value
    
    def _warn_missing_credentials(self) -> None:
        """Warn about missing credentials in development mode."""
        import logging
        logger = logging.getLogger(__name__)
        
        # Define required credentials with their descriptions
        required_credentials = {
            "FACEBOOK_VERIFY_TOKEN": "Required for webhook verification. Create a custom token string (e.g., 'my_webhook_token_123').",
            "FACEBOOK_APP_SECRET": "Required for webhook signature validation. Get from: https://developers.facebook.com/apps/YOUR_APP_ID/settings/basic/",
            "INSTAGRAM_PAGE_ACCESS_TOKEN": "Required for sending messages. Generate from Facebook App Dashboard → Instagram → User Token Generator.",
            "INSTAGRAM_BUSINESS_ACCOUNT_ID": "Required for send message API. This is your Instagram Business Account ID (recipient_id from inbound messages)."
        }
        
        # Check which credentials are missing
        missing = [
            f"{key} - {desc}"
            for key, desc in required_credentials.items()
            if not getattr(self, key.lower(), None)
        ]
        
        if missing:
            logger.warning(
                "⚠️  Missing configuration in .env file:\n" + 
                "\n".join(f"  - {config}" for config in missing)
            )


# Global settings instance
settings = Settings()
