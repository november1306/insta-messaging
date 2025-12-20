"""Configuration management using environment variables"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Development placeholder for secrets (not secure - for local testing only)
DEV_SECRET_PLACEHOLDER = "test_secret_dev"


class Settings:
    """Application settings - YAGNI: Only what we need right now"""
    
    def __init__(self):
        # Environment
        self.environment = os.getenv("ENVIRONMENT", "development")
        
        # Instagram/Facebook credentials
        if self.environment == "production":
            self.facebook_verify_token = self._get_required("FACEBOOK_VERIFY_TOKEN")
            self.facebook_app_secret = self._get_required("FACEBOOK_APP_SECRET")
            self.instagram_app_secret = self._get_required("INSTAGRAM_APP_SECRET")
            self.instagram_page_access_token = self._get_required("INSTAGRAM_PAGE_ACCESS_TOKEN")
            self.instagram_business_account_id = self._get_required("INSTAGRAM_BUSINESS_ACCOUNT_ID")
            
            # Reject test secrets in production
            if self.facebook_app_secret == DEV_SECRET_PLACEHOLDER:
                raise ValueError(
                    f"Cannot use test secret '{DEV_SECRET_PLACEHOLDER}' in production mode. "
                    "Set a real FACEBOOK_APP_SECRET from your Facebook app."
                )
            if self.instagram_app_secret == DEV_SECRET_PLACEHOLDER:
                raise ValueError(
                    f"Cannot use test secret '{DEV_SECRET_PLACEHOLDER}' in production mode. "
                    "Set a real INSTAGRAM_APP_SECRET from your Instagram app settings."
                )
        else:
            # Development mode: Load from .env file (never commit secrets to git)
            self.facebook_verify_token = os.getenv("FACEBOOK_VERIFY_TOKEN", "")
            self.facebook_app_secret = os.getenv("FACEBOOK_APP_SECRET", DEV_SECRET_PLACEHOLDER)
            self.instagram_app_secret = os.getenv("INSTAGRAM_APP_SECRET", DEV_SECRET_PLACEHOLDER)
            self.instagram_page_access_token = os.getenv("INSTAGRAM_PAGE_ACCESS_TOKEN", "")
            self.instagram_business_account_id = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
            
            # Warn about default test secrets
            if self.instagram_app_secret == DEV_SECRET_PLACEHOLDER:
                import logging
                logging.getLogger(__name__).warning(
                    "⚠️  Using default INSTAGRAM_APP_SECRET - webhook signature validation will fail with real Instagram webhooks"
                )
            
            # Check for missing credentials and warn
            self._warn_missing_credentials()

        # JWT/Session configuration for UI authentication
        if self.environment == "production":
            self.session_secret = self._get_required("SESSION_SECRET")
        else:
            # Development: Generate random secret if not provided
            session_secret_env = os.getenv("SESSION_SECRET", "")
            if session_secret_env:
                self.session_secret = session_secret_env
            else:
                # Generate a random secret on startup for development
                import secrets
                self.session_secret = secrets.token_urlsafe(32)
                import logging
                logging.getLogger(__name__).warning(
                    "⚠️  No SESSION_SECRET provided - generated random secret for this session. "
                    "JWT tokens will not persist across restarts. Set SESSION_SECRET in .env for persistent tokens."
                )

        self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
        self.jwt_expiration_hours = int(os.getenv("JWT_EXPIRATION_HOURS", "24"))

        # Instagram OAuth configuration
        self.instagram_oauth_client_id = os.getenv("INSTAGRAM_OAUTH_CLIENT_ID", "")
        self.instagram_oauth_client_secret = os.getenv("INSTAGRAM_OAUTH_CLIENT_SECRET", "")
        self.instagram_oauth_redirect_uri = os.getenv(
            "INSTAGRAM_OAUTH_REDIRECT_URI",
            "http://localhost:8000/oauth/instagram/callback"
        )

        # Server configuration
        self.host = os.getenv("HOST", "0.0.0.0")
        self.port = int(os.getenv("PORT", "8000"))

        # Database configuration (SQLite only - configurable path)
        self.database_url = os.getenv(
            "DATABASE_URL",
            "sqlite+aiosqlite:///./instagram_automation.db"
        )

        # Public base URL for outbound media (required for Instagram API to fetch attachments)
        self.public_base_url = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

        # CRM webhook configuration
        self.crm_webhook_timeout = float(os.getenv("CRM_WEBHOOK_TIMEOUT", "10.0"))  # seconds

        # CRM MySQL configuration (dual storage)
        self.crm_mysql_enabled = os.getenv("CRM_MYSQL_ENABLED", "false").lower() == "true"
        self.crm_mysql_host = os.getenv("CRM_MYSQL_HOST", "")
        self.crm_mysql_user = os.getenv("CRM_MYSQL_USER", "")
        self.crm_mysql_password = os.getenv("CRM_MYSQL_PASSWORD", "")
        self.crm_mysql_database = os.getenv("CRM_MYSQL_DATABASE", "")

        # Logging
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
    
    def _get_required(self, key: str) -> str:
        """Get required environment variable or raise error."""
        value = os.getenv(key, "").strip()
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
            "FACEBOOK_APP_SECRET": "Required for Facebook webhook signature validation. Get from: https://developers.facebook.com/apps/YOUR_APP_ID/settings/basic/",
            "INSTAGRAM_APP_SECRET": "Required for Instagram webhook signature validation. Get from Instagram app settings.",
            "INSTAGRAM_PAGE_ACCESS_TOKEN": "Required for sending messages. Generate from Facebook App Dashboard → Instagram → User Token Generator.",
            "INSTAGRAM_BUSINESS_ACCOUNT_ID": "Required for send message API. This is your Instagram Business Account ID (recipient_id from inbound messages)."
        }
        
        # Check which credentials are missing or empty
        missing = [
            f"{key} - {desc}"
            for key, desc in required_credentials.items()
            if not getattr(self, key.lower(), "").strip()
        ]
        
        if missing:
            logger.warning(
                "⚠️  Missing configuration - webhook validation will fail until these are set:\n" + 
                "\n".join(f"  - {config}" for config in missing) +
                "\n\nCopy .env.example to .env and fill in your credentials."
            )


# Global settings instance
settings = Settings()
