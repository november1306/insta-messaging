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
        # Security: Only use defaults in development mode
        if self.environment == "production":
            self.facebook_verify_token = self._get_required("FACEBOOK_VERIFY_TOKEN")
            self.facebook_app_secret = self._get_required("FACEBOOK_APP_SECRET")
            self.instagram_page_access_token = self._get_required("INSTAGRAM_PAGE_ACCESS_TOKEN")
            self.instagram_business_account_id = self._get_required("INSTAGRAM_BUSINESS_ACCOUNT_ID")
        else:
            # Development defaults (not secure, only for local testing)
            self.facebook_verify_token = os.getenv("FACEBOOK_VERIFY_TOKEN", "dev_verify_token_12345")
            self.facebook_app_secret = os.getenv("FACEBOOK_APP_SECRET", "")
            self.instagram_page_access_token = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN", "")
            self.instagram_business_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "BUSINESS_ACCOUNT_ID_PLACEHOLDER")
        
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


# Global settings instance
settings = Settings()
