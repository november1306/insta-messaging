"""
Message Repository implementation using SQLAlchemy.

Implements IMessageRepository interface for storing and retrieving messages.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.interfaces import IMessageRepository, Message
from app.db.models import MessageModel
import logging

logger = logging.getLogger(__name__)


class MessageRepository(IMessageRepository):
    """
    SQLAlchemy implementation of IMessageRepository.
    
    Handles conversion between domain Message objects and MessageModel ORM objects.
    """
    
    def __init__(self, db_session: AsyncSession) -> None:
        """
        Initialize repository with database session.
        
        Args:
            db_session: SQLAlchemy async session for database operations
        """
        self._db = db_session
    
    async def save(self, message: Message) -> Message:
        """
        Save a message to the database.
        
        Args:
            message: Domain Message object to save
            
        Returns:
            The saved Message object
            
        Raises:
            ValueError: If a message with the same ID already exists
            Exception: If database operation fails
        """
        try:
            # Convert domain model to ORM model
            db_message = MessageModel(
                id=message.id,
                sender_id=message.sender_id,
                recipient_id=message.recipient_id,
                message_text=message.message_text,
                direction=message.direction,
                timestamp=message.timestamp,
                created_at=message.created_at
            )
            
            # Add to session and flush to get any DB-generated values
            # Note: Transaction will be committed by the session context manager
            # in get_db_session() (app/db/connection.py)
            self._db.add(db_message)
            await self._db.flush()
            
            logger.info(f"Saved message {message.id} ({message.direction})")
            
            return message
            
        except IntegrityError as e:
            # Rollback the failed transaction to clean up the session state
            await self._db.rollback()
            logger.error(f"Message {message.id} already exists: {e}")
            raise ValueError(f"Message {message.id} already exists") from e
        except Exception as e:
            logger.error(f"Failed to save message {message.id}: {e}")
            raise
    
    async def get_by_id(self, message_id: str) -> Optional[Message]:
        """
        Retrieve a message by its ID.
        
        Args:
            message_id: The message ID to look up
            
        Returns:
            Message object if found, None otherwise
        """
        try:
            # Query database for message
            stmt = select(MessageModel).where(MessageModel.id == message_id)
            result = await self._db.execute(stmt)
            db_message = result.scalar_one_or_none()
            
            if db_message is None:
                logger.debug(f"Message {message_id} not found")
                return None
            
            # Convert ORM model to domain model
            message = Message(
                id=db_message.id,
                sender_id=db_message.sender_id,
                recipient_id=db_message.recipient_id,
                message_text=db_message.message_text,
                direction=db_message.direction,
                timestamp=db_message.timestamp,
                created_at=db_message.created_at
            )
            
            logger.debug(f"Retrieved message {message_id}")
            return message
            
        except Exception as e:
            logger.error(f"Failed to retrieve message {message_id}: {e}")
            raise
