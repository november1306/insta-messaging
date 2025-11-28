"""
SQLAlchemy ORM models for database tables.

YAGNI: Start minimal, add tables only when needed.
"""
from sqlalchemy import Column, String, Text, DateTime, Index, ForeignKey, Boolean, Integer, Enum
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
    sender_id = Column(String(50), nullable=False)  # Instagram user ID
    recipient_id = Column(String(50), nullable=False)  # Instagram user ID
    message_text = Column(Text)  # Message content
    direction = Column(String(10), nullable=False)  # 'inbound' or 'outbound'
    timestamp = Column(DateTime, nullable=False)  # When message was sent
    created_at = Column(DateTime, default=func.now())  # When we stored it
    
    __table_args__ = (
        Index('idx_timestamp', 'timestamp'),
        Index('idx_sender', 'sender_id'),
    )


# ============================================
# CRM Integration Models
# ============================================

class Account(Base):
    """
    Instagram business accounts for CRM integration.
    
    Stores account credentials and webhook configuration.
    Minimal fields for MVP - add more later if needed.
    """
    __tablename__ = "accounts"
    
    id = Column(String(50), primary_key=True)  # Our internal account ID
    instagram_account_id = Column(String(50), unique=True, nullable=False)  # Instagram's account ID
    username = Column(String(100), nullable=False)  # Instagram username
    access_token_encrypted = Column(Text, nullable=False)  # Encrypted Instagram access token
    crm_webhook_url = Column(String(500), nullable=False)  # Where to send webhooks
    webhook_secret = Column(String(100), nullable=False)  # For webhook signature
    created_at = Column(DateTime, nullable=False, default=func.now())  # Python + DB default for defense-in-depth
    
    __table_args__ = (
        Index('idx_instagram_account_id', 'instagram_account_id'),
    )


class OutboundMessage(Base):
    """
    Outbound messages sent via CRM integration API.
    
    Tracks delivery status and enables idempotency.
    Minimal fields for MVP - add retry logic fields later if needed.
    """
    __tablename__ = "outbound_messages"
    
    id = Column(String(50), primary_key=True)  # Our message ID
    account_id = Column(String(50), ForeignKey('accounts.id'), nullable=False)  # FK to accounts.id
    recipient_id = Column(String(50), nullable=False)  # Instagram PSID
    message_text = Column(Text, nullable=False)  # Message content
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
        Index('idx_key_prefix', 'key_prefix'),
        Index('idx_is_active', 'is_active'),
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
        Index('idx_username', 'username'),
        Index('idx_is_active', 'is_active'),
    )
