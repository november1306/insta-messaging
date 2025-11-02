"""Configuration management using environment variables"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables"""
    
    def __init__(self):
        # Environment
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # Facebook/Instagram credentials (optional for now, will be in database)
        self.facebook_verify_token = os.getenv("FACEBOOK_VERIFY_TOKEN", "dev_verify_token_12345")
        self.facebook_app_secret = os.getenv("FACEBOOK_APP_SECRET", "")
        self.instagram_page_access_token = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN", "")
        
        # Database configuration
        # For local dev: SQLite (no config needed)
        # For production: MySQL
        self.mysql_host = os.getenv("MYSQL_HOST", "localhost")
        self.mysql_port = int(os.getenv("MYSQL_PORT", "3306"))
        self.mysql_database = os.getenv("MYSQL_DATABASE", "instagram_automation")
        self.mysql_username = os.getenv("MYSQL_USERNAME", "root")
        self.mysql_password = os.getenv("MYSQL_PASSWORD", "")
        
        # Security
        self.app_secret_key = os.getenv("APP_SECRET_KEY", "dev-secret-key-change-in-production")
        
        # Server configuration
        # nosec B104: Binding to 0.0.0.0 is intentional for containerized deployment
        # In production, use a reverse proxy (nginx) to restrict access
        self.host = os.getenv("HOST", "0.0.0.0")  # nosec B104
        self.port = int(os.getenv("PORT", "8000"))
        
        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        
    @property
    def database_url(self) -> str:
        """Get database URL for production (MySQL)"""
        return f"mysql+aiomysql://{self.mysql_username}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
    
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
