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
