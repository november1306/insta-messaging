"""
SQLAlchemy ORM models for database tables.

These models map to actual database tables and are separate from
the domain models in app/core/interfaces.py
"""
from sqlalchemy import Column, String, Integer, Text, DateTime, Boolean, JSON, Enum as SQLEnum, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
import enum

Base = declarative_base()


# Enums matching domain models
class AccountStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class MessageDirectionEnum(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class MessageTypeEnum(str, enum.Enum):
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    STICKER = "sticker"
    STORY_REPLY = "story_reply"
    UNSUPPORTED = "unsupported"


class MessageStatusEnum(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class ConversationStatusEnum(str, enum.Enum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    BLOCKED = "blocked"


class TriggerTypeEnum(str, enum.Enum):
    KEYWORD = "keyword"
    PATTERN = "pattern"
    INTENT = "intent"


class InstagramBusinessAccountModel(Base):
    """Instagram business account table"""
    __tablename__ = "instagram_business_accounts"
    
    id = Column(String(50), primary_key=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    display_name = Column(String(200))
    access_token_encrypted = Column(Text, nullable=False)
    app_secret_encrypted = Column(Text, nullable=False)
    webhook_verify_token = Column(String(100), nullable=False)
    status = Column(SQLEnum(AccountStatusEnum), default=AccountStatusEnum.ACTIVE, index=True)
    settings = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class MessageModel(Base):
    """Messages table (account-scoped)"""
    __tablename__ = "messages"
    
    id = Column(String(100), primary_key=True)
    account_id = Column(String(50), ForeignKey("instagram_business_accounts.id"), nullable=False)
    conversation_id = Column(String(100), nullable=False)
    direction = Column(SQLEnum(MessageDirectionEnum), nullable=False)
    sender_id = Column(String(50))
    recipient_id = Column(String(50))
    message_text = Column(Text)
    message_type = Column(String(50), default="text")
    message_metadata = Column("metadata", JSON, default=dict)
    status = Column(String(50), default="delivered")
    timestamp = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_account_conversation', 'account_id', 'conversation_id'),
        Index('idx_timestamp', 'timestamp'),
    )


class ConversationModel(Base):
    """Conversations table (account-scoped)"""
    __tablename__ = "conversations"
    
    id = Column(String(100), primary_key=True)
    account_id = Column(String(50), ForeignKey("instagram_business_accounts.id"), nullable=False)
    participant_id = Column(String(50), nullable=False)
    participant_username = Column(String(100))
    status = Column(SQLEnum(ConversationStatusEnum), default=ConversationStatusEnum.ACTIVE)
    last_message_at = Column(DateTime)
    message_count = Column(Integer, default=0)
    conversation_metadata = Column("metadata", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_account_id', 'account_id'),
        Index('idx_last_message_at', 'last_message_at'),
        Index('idx_unique_account_participant', 'account_id', 'participant_id', unique=True),
    )


class ResponseRuleModel(Base):
    """Response rules table (account-scoped)"""
    __tablename__ = "response_rules"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(String(50), ForeignKey("instagram_business_accounts.id"), nullable=False)
    name = Column(String(200), nullable=False)
    trigger_type = Column(SQLEnum(TriggerTypeEnum), nullable=False)
    trigger_value = Column(Text, nullable=False)
    response_template = Column(Text, nullable=False)
    priority = Column(Integer, default=0)
    is_active = Column(Boolean, default=True)
    rule_conditions = Column("conditions", JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_account_active', 'account_id', 'is_active'),
    )
