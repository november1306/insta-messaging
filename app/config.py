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
        self.facebook_verify_token = os.getenv("FACEBOOK_VERIFY_TOKEN", "dev_verify_token_12345")
        self.facebook_app_secret = os.getenv("FACEBOOK_APP_SECRET", "")
        self.instagram_page_access_token = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN", "")
        
        # Server configuration
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))
        
        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")


# Global settings instance
settings = Settings()
