"""
SQLAlchemy ORM models for database tables.

YAGNI: Start minimal, add tables only when needed.
"""
from sqlalchemy import Column, String, Text, DateTime, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


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
    created_at = Column(DateTime, default=func.now())
    
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
    account_id = Column(String(50), nullable=False)  # FK to accounts.id
    recipient_id = Column(String(50), nullable=False)  # Instagram PSID
    message_text = Column(Text, nullable=False)  # Message content
    idempotency_key = Column(String(100), unique=True, nullable=False)  # Prevent duplicates
    status = Column(String(20), nullable=False, default='pending')  # pending, sent, delivered, failed
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_account_status', 'account_id', 'status'),
        Index('idx_idempotency_key', 'idempotency_key'),
    )
