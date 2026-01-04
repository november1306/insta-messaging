"""
SQLAlchemy ORM models for database tables.

YAGNI: Start minimal, add tables only when needed.
"""
from sqlalchemy import Column, String, Text, DateTime, Index, ForeignKey, Boolean, Integer, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
import enum

Base = declarative_base()


# ============================================
# Enums
# ============================================

class APIKeyType(str, enum.Enum):
    """API key types for permission scoping"""
    ADMIN = "admin"  # Full access to all accounts
    ACCOUNT = "account"  # Limited to specific accounts


class MessageModel(Base):
    """
    Messages table - stores all Instagram messages (inbound/outbound).

    Start simple: just store messages. Add complexity later when needed.
    """
    __tablename__ = "messages"

    # Core fields
    id = Column(String(100), primary_key=True)  # Instagram message ID
    account_id = Column(String(50), ForeignKey('accounts.id', ondelete='CASCADE'), nullable=True)  # Database account ID
    sender_id = Column(String(50), nullable=False)  # Instagram user ID
    recipient_id = Column(String(50), nullable=False)  # Instagram user ID
    message_text = Column(Text)  # Message content (text message OR caption for media)
    direction = Column(String(10), nullable=False)  # 'inbound' or 'outbound'
    timestamp = Column(DateTime, nullable=False)  # When message was sent
    created_at = Column(DateTime, default=func.now())  # When we stored it

    # CRM tracking fields (added in merge_tracking_tables migration)
    idempotency_key = Column(String(100), nullable=True)  # For duplicate detection
    delivery_status = Column(String(20), nullable=True)  # 'pending', 'sent', 'failed', 'delivered', 'read'
    error_code = Column(String(50), nullable=True)  # Error code if delivery failed
    error_message = Column(Text, nullable=True)  # Error message if delivery failed

    __table_args__ = (
        Index('idx_timestamp', 'timestamp'),
        Index('idx_sender', 'sender_id'),
        Index('idx_messages_account_id', 'account_id'),  # Added in migration
    )

    # Relationships
    attachments = relationship("MessageAttachment", back_populates="message", cascade="all, delete-orphan")


class MessageAttachment(Base):
    """
    Message attachments - images, videos, audio, files.

    Instagram supports multiple attachments per message (attachments array in webhook).
    Each attachment is a separate row linked to parent message via message_id.

    Design rationale:
    - Separate table for 1-to-many relationship (Instagram feature verified 2024-2025)
    - Proper normalization: avoids JSON columns, enables efficient queries
    - attachment_index preserves display order (0, 1, 2...)
    - Both media_type (from Instagram) and media_mime_type (detected) for flexibility
    - media_url expires in 7 days - media_url_local is our permanent copy
    """
    __tablename__ = "message_attachments"

    # Core fields
    id = Column(String(100), primary_key=True)  # Format: "mid_abc123_0", "mid_abc123_1"
    message_id = Column(String(100), ForeignKey('messages.id', ondelete='CASCADE'), nullable=False)
    attachment_index = Column(Integer, nullable=False)  # Order: 0, 1, 2 (important for display)

    # Media metadata
    media_type = Column(String(20), nullable=False)  # 'image', 'video', 'audio', 'file', 'like_heart'
    media_url = Column(Text, nullable=False)  # Original Instagram URL (expires in 7 days)
    media_url_local = Column(Text, nullable=True)  # Local copy: "media/page456/user123/mid_abc123_0.jpg"
    media_mime_type = Column(String(100), nullable=True)  # 'image/jpeg', 'video/mp4' (detected on download)

    __table_args__ = (
        Index('idx_message_attachments_message_id', 'message_id'),
        Index('idx_message_attachments_media_type', 'media_type'),
    )

    # Relationships
    message = relationship("MessageModel", back_populates="attachments")


# ============================================
# CRM Integration Models
# ============================================

class Account(Base):
    """
    Instagram business accounts for CRM integration and OAuth.

    Stores account credentials and webhook configuration.
    Now supports both CRM-configured accounts and OAuth-linked accounts.

    OAuth fields: token_expires_at, profile_picture_url, account_type
    CRM fields: crm_webhook_url, webhook_secret (now nullable for OAuth-only accounts)
    """
    __tablename__ = "accounts"

    id = Column(String(50), primary_key=True)  # Our internal account ID
    instagram_account_id = Column(String(50), unique=True, nullable=False)  # Instagram's OAuth profile ID (public)
    username = Column(String(100), nullable=False)  # Instagram username
    messaging_channel_id = Column(String(50), unique=True, nullable=True)  # Messaging channel ID from webhook entry.id (stable, used for routing)
    access_token_encrypted = Column(Text, nullable=False)  # Encrypted Instagram access token (Fernet)

    # OAuth-specific fields
    token_expires_at = Column(DateTime, nullable=True)  # When access token expires (60 days for long-lived tokens)
    profile_picture_url = Column(String(500), nullable=True)  # Profile picture URL from Instagram Graph API

    # OAuth tracking fields (for debugging and support)
    account_type = Column(String(20), nullable=True)  # 'business', 'creator', 'unknown' - kept for debugging

    # CRM integration fields (now nullable for OAuth-only accounts)
    crm_webhook_url = Column(String(500), nullable=True)  # Where to send webhooks (optional for OAuth accounts)
    webhook_secret = Column(String(100), nullable=True)  # For webhook signature (optional for OAuth accounts)

    created_at = Column(DateTime, nullable=False, default=func.now())  # Python + DB default for defense-in-depth

    __table_args__ = (
        Index('idx_instagram_account_id', 'instagram_account_id'),
        Index('idx_messaging_channel_id', 'messaging_channel_id'),  # For webhook routing by entry.id
        Index('idx_token_expires_at', 'token_expires_at'),  # For token refresh background tasks
    )


class InstagramProfile(Base):
    """
    Cached Instagram user profiles (senders).

    Caches username and profile picture for customers who message us.
    NOTE: Requires User Profile API permission (pages_messaging) to retrieve profile_pic.
    Without this permission, profile_picture_url will be NULL.

    Reduces Instagram API calls by storing profile data locally.
    """
    __tablename__ = "instagram_profiles"

    sender_id = Column(String(50), primary_key=True)  # Instagram user ID (PSID)
    username = Column(String(100), nullable=True)  # Instagram username (without @ prefix)
    profile_picture_url = Column(String(500), nullable=True)  # Profile picture URL
    last_updated = Column(DateTime, nullable=False, default=func.now())  # When profile was last fetched

    __table_args__ = (
        Index('idx_profile_last_updated', 'last_updated'),  # For finding stale profiles
    )


class CRMOutboundMessage(Base):
    """
    CRM outbound messages - tracks messages sent via CRM integration API.

    This table is specifically for CRM integration to track delivery status
    and enable idempotency for external systems. NOT for general UI message display.
    UI should use the 'messages' table which stores all inbound/outbound messages.

    Tracks delivery status and enables idempotency.
    Minimal fields for MVP - add retry logic fields later if needed.
    """
    __tablename__ = "crm_outbound_messages"

    id = Column(String(50), primary_key=True)  # Our message ID
    account_id = Column(String(50), ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)  # FK to accounts.id
    recipient_id = Column(String(50), nullable=False)  # Instagram PSID
    message_text = Column(Text, nullable=True)  # Message content (nullable for media-only messages)
    idempotency_key = Column(String(100), unique=True, nullable=False)  # Prevent duplicates
    status = Column(String(20), nullable=False, default='pending', server_default='pending')  # Python + DB default
    instagram_message_id = Column(String(100), nullable=True)  # Instagram's message ID (set after successful send)
    error_code = Column(String(50), nullable=True)  # Error code if delivery failed
    error_message = Column(Text, nullable=True)  # Error message if delivery failed
    created_at = Column(DateTime, nullable=False, default=func.now())  # Python + DB default (server_default in migration)
    
    __table_args__ = (
        Index('idx_account_status', 'account_id', 'status'),
        # Note: No need for idx_idempotency_key - unique constraint creates its own index
    )


# ============================================
# Authentication Models
# ============================================

class APIKey(Base):
    """
    API keys for CRM integration authentication.

    Keys are hashed with bcrypt - only the hash is stored, not the actual key.
    The key_prefix allows fast lookup without exposing the full key.
    """
    __tablename__ = "api_keys"

    id = Column(String(50), primary_key=True)  # UUID
    key_prefix = Column(String(20), nullable=False)  # First 10 chars for lookup (e.g., "sk_test_Ab")
    key_hash = Column(String(100), nullable=False)  # bcrypt hash of full key
    name = Column(String(200), nullable=False)  # Descriptive name
    type = Column(Enum(APIKeyType), nullable=False)  # admin or account-scoped
    is_active = Column(Boolean, nullable=False, default=True)  # Can be revoked
    created_at = Column(DateTime, nullable=False, default=func.now())
    last_used_at = Column(DateTime, nullable=True)  # Updated on each use
    expires_at = Column(DateTime, nullable=True)  # Optional expiration

    __table_args__ = (
        Index('idx_api_keys_key_prefix', 'key_prefix'),
        Index('idx_api_keys_is_active', 'is_active'),
    )


class APIKeyPermission(Base):
    """
    Account permissions for account-scoped API keys.

    Admin keys ignore this table and have access to all accounts.
    Account keys can only access accounts listed in this table.
    """
    __tablename__ = "api_key_permissions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    api_key_id = Column(String(50), ForeignKey('api_keys.id', ondelete='CASCADE'), nullable=False)
    account_id = Column(String(50), ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)

    __table_args__ = (
        Index('idx_api_key_id', 'api_key_id'),
        Index('idx_account_id', 'account_id'),
    )


class User(Base):
    """
    Users for UI authentication.

    Stores username and bcrypt-hashed password for login.
    Used for JWT session creation via Basic Auth validation.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)  # bcrypt hash
    is_active = Column(Boolean, nullable=False, default=True)  # Allow deactivation

    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index('idx_users_username', 'username'),
        Index('idx_users_is_active', 'is_active'),
    )


# ============================================
# OAuth Models
# ============================================

class UserAccount(Base):
    """
    User-Account relationship (many-to-many).

    Links users to their Instagram business accounts.
    Supports multiple accounts per user and multiple users per account (team collaboration).

    Fields:
    - is_primary: User's default account for sending messages
    """
    __tablename__ = "user_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    account_id = Column(String(50), ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False)
    is_primary = Column(Boolean, nullable=False, default=False)  # User's default account
    linked_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index('idx_user_accounts_user_id', 'user_id'),
        Index('idx_user_accounts_account_id', 'account_id'),
        Index('idx_user_accounts_user_primary', 'user_id', 'is_primary'),  # Fast lookup for primary account
        UniqueConstraint('user_id', 'account_id', name='uq_user_account'),  # Prevent duplicate links
        {'sqlite_autoincrement': True}  # Ensure autoincrement works on SQLite
    )


class OAuthState(Base):
    """
    OAuth state tokens for CSRF protection.

    Stores random state tokens generated during OAuth flow.
    Used to prevent CSRF attacks by validating the state parameter in the callback.

    Lifecycle:
    1. Create state token when user clicks "Connect Instagram"
    2. Store state with user_id and redirect_uri
    3. Validate state in callback (must match and not be expired)
    4. Delete state after successful validation (one-time use)

    Cleanup: Background task deletes expired states (expires_at < now)
    """
    __tablename__ = "oauth_states"

    state = Column(String(64), primary_key=True)  # Random URL-safe token
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    redirect_uri = Column(String(500), nullable=False)  # Where to redirect after OAuth
    created_at = Column(DateTime, nullable=False, default=func.now())
    expires_at = Column(DateTime, nullable=False)  # 10-minute expiration

    __table_args__ = (
        Index('idx_oauth_states_expires_at', 'expires_at'),  # For cleanup queries
        Index('idx_oauth_states_user_id', 'user_id'),
    )
