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
import asyncio
import httpx

logger = logging.getLogger(__name__)


class MessageRepository(IMessageRepository):
    """
    SQLAlchemy implementation of IMessageRepository.
    
    Handles conversion between domain Message objects and MessageModel ORM objects.
    """
    
    def __init__(self, db_session: AsyncSession, crm_pool=None) -> None:
        """
        Initialize repository with database session and optional CRM pool.

        Args:
            db_session: SQLAlchemy async session for database operations
            crm_pool: aiomysql connection pool for CRM MySQL sync (optional)
        """
        self._db = db_session
        self._crm_pool = crm_pool
    
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

            # Sync to CRM MySQL (fire-and-forget, non-blocking)
            if self._crm_pool:
                task = asyncio.create_task(self._sync_to_crm(message))
                # Ensure task exceptions are logged, not silently dropped
                task.add_done_callback(self._handle_crm_task_done)

            return message
            
        except IntegrityError as e:
            # Session manager in get_db_session() handles rollback automatically
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

    async def _sync_to_crm(self, message: Message) -> None:
        """
        Sync message to CRM MySQL database (fire-and-forget).

        Args:
            message: Domain Message object to sync

        Note:
            This is a best-effort sync - errors are logged but not raised.
            CRM failures don't affect local storage.
        """
        try:
            # Determine user_id based on direction (inbound = sender, outbound = recipient)
            user_id = message.sender_id if message.direction == 'inbound' else message.recipient_id

            # Fetch username from Instagram API
            username = await self._get_instagram_username(user_id)

            # Map direction to CRM format ('inbound' -> 'in', 'outbound' -> 'out')
            direction = 'in' if message.direction == 'inbound' else 'out'

            # Insert into CRM MySQL
            async with self._crm_pool.acquire() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        "INSERT INTO messages (user_id, username, direction, message, created_at) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (user_id, username, direction, message.message_text, message.timestamp)
                    )
                    await conn.commit()

            logger.info(f"✅ CRM sync OK: {message.id}")

        except Exception as e:
            # TODO: CRM table missing fields (instagram_message_id, sender/recipient, conversation_id, status)
            # TODO: Add retry logic for transient failures
            # TODO: Add performance monitoring (track sync duration)
            logger.error(f"❌ CRM sync failed for message {message.id}: {e}")

    def _handle_crm_task_done(self, task: asyncio.Task) -> None:
        """
        Handle completion of CRM sync background task.

        This callback ensures that any unhandled exceptions in the fire-and-forget
        task are properly logged rather than silently dropped.

        Args:
            task: The completed asyncio Task
        """
        try:
            # Check if task raised an exception
            if not task.cancelled() and task.exception() is not None:
                exc = task.exception()
                logger.error(f"❌ Unhandled exception in CRM sync task: {exc}")
        except Exception as e:
            # This should never happen, but log it just in case
            logger.error(f"❌ Error in CRM task callback: {e}")

    async def _get_instagram_username(self, user_id: str) -> str:
        """
        Fetch Instagram username from Graph API.

        Args:
            user_id: Instagram user PSID

        Returns:
            Instagram username, or user_id if API call fails

        Note:
            Falls back to user_id if API call fails (best-effort).
        """
        try:
            from app.config import settings

            # Instagram Graph API endpoint for user info
            url = f"https://graph.instagram.com/{user_id}"
            params = {
                "fields": "username",
                "access_token": settings.instagram_page_access_token
            }

            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                return data.get("username", user_id)

        except Exception as e:
            logger.warning(f"Failed to fetch username for {user_id}: {e}. Using user_id as fallback.")
            return user_id
