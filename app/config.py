"""Configuration management using environment variables"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables"""
    
    def __init__(self):
        # Facebook/Instagram credentials
        self.facebook_verify_token = self._get_required_env("FACEBOOK_VERIFY_TOKEN")
        self.facebook_app_secret = self._get_required_env("FACEBOOK_APP_SECRET")
        self.instagram_page_access_token = self._get_required_env("INSTAGRAM_PAGE_ACCESS_TOKEN")
        
        # Server configuration
        # nosec B104: Binding to 0.0.0.0 is intentional for containerized deployment
        # In production, use a reverse proxy (nginx) to restrict access
        self.host = os.getenv("HOST", "0.0.0.0")  # nosec B104
        self.port = int(os.getenv("PORT", "8000"))
        self.environment = os.getenv("ENVIRONMENT", "development")
        
    def _get_required_env(self, key: str) -> str:
        """Get required environment variable or raise error"""
        value = os.getenv(key)
        if not value:
            raise ValueError(
                f"Missing required environment variable: {key}. "
                f"Please set it in your .env file or environment."
            )
        return value


# Global settings instance
settings = Settings()
