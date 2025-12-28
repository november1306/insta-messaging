"""
Message Repository implementation using SQLAlchemy.

Implements IMessageRepository interface for storing and retrieving messages.
"""
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.core.interfaces import IMessageRepository, Message, Attachment
from app.db.models import MessageModel, MessageAttachment
import logging
import asyncio
import httpx

logger = logging.getLogger(__name__)


class MessageRepository(IMessageRepository):
    """
    SQLAlchemy implementation of IMessageRepository.

    Handles conversion between domain Message objects and MessageModel ORM objects.
    """

    # Class-level username cache (shared across all instances)
    # Maps Instagram user_id -> username
    _username_cache: dict[str, str] = {}

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
        Save a message and its attachments to the database.

        Args:
            message: Domain Message object to save (with optional attachments)

        Returns:
            The saved Message object

        Raises:
            ValueError: If a message with the same ID already exists
            Exception: If database operation fails

        Note:
            Message and attachments are saved atomically in a transaction.
            Session commit is handled by get_db_session() context manager.
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

            # Add message to session
            self._db.add(db_message)

            # Save attachments (if any) - transaction ensures atomicity
            if message.attachments:
                for attachment in message.attachments:
                    db_attachment = MessageAttachment(
                        id=attachment.id,
                        message_id=attachment.message_id,
                        attachment_index=attachment.attachment_index,
                        media_type=attachment.media_type,
                        media_url=attachment.media_url,
                        media_url_local=attachment.media_url_local,
                        media_mime_type=attachment.media_mime_type
                    )
                    self._db.add(db_attachment)

            # Flush to database (commit handled by session context manager)
            await self._db.flush()

            attachment_count = len(message.attachments) if message.attachments else 0
            logger.info(f"Saved message {message.id} ({message.direction}) with {attachment_count} attachment(s)")

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
        Retrieve a message by its ID with its attachments.

        Args:
            message_id: The message ID to look up

        Returns:
            Message object with attachments if found, None otherwise
        """
        try:
            # Query database for message
            stmt = select(MessageModel).where(MessageModel.id == message_id)
            result = await self._db.execute(stmt)
            db_message = result.scalar_one_or_none()

            if db_message is None:
                logger.debug(f"Message {message_id} not found")
                return None

            # Fetch attachments for this message
            attachments_stmt = (
                select(MessageAttachment)
                .where(MessageAttachment.message_id == message_id)
                .order_by(MessageAttachment.attachment_index)  # Preserve order
            )
            attachments_result = await self._db.execute(attachments_stmt)
            db_attachments = attachments_result.scalars().all()

            # Convert attachments to domain models
            attachments = []
            for db_att in db_attachments:
                attachment = Attachment(
                    id=db_att.id,
                    message_id=db_att.message_id,
                    attachment_index=db_att.attachment_index,
                    media_type=db_att.media_type,
                    media_url=db_att.media_url,
                    media_url_local=db_att.media_url_local,
                    media_mime_type=db_att.media_mime_type
                )
                attachments.append(attachment)

            # Convert ORM model to domain model
            message = Message(
                id=db_message.id,
                sender_id=db_message.sender_id,
                recipient_id=db_message.recipient_id,
                message_text=db_message.message_text,
                direction=db_message.direction,
                timestamp=db_message.timestamp,
                created_at=db_message.created_at,
                attachments=attachments  # Include attachments
            )

            logger.debug(f"Retrieved message {message_id} with {len(attachments)} attachment(s)")
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
        # Safety check: ensure pool is available
        if self._crm_pool is None:
            logger.warning(f"CRM sync skipped for message {message.id}: pool is None")
            return

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
        Fetch Instagram username from Graph API with caching.

        Args:
            user_id: Instagram user PSID

        Returns:
            Instagram username, or user_id if API call fails

        Note:
            - Uses class-level cache to avoid redundant API calls
            - Only fetches username once per user_id
            - Falls back to user_id if API call fails (best-effort)
        """
        # Check cache first
        if user_id in self._username_cache:
            logger.debug(f"Username cache hit for {user_id}: {self._username_cache[user_id]}")
            return self._username_cache[user_id]

        # OAuth system: No global token available for username fetching
        # Username should be fetched via per-account OAuth tokens when needed
        # For CRM MySQL dual storage, user_id is acceptable fallback
        logger.debug(
            f"Username not in cache for {user_id}. "
            "OAuth system should fetch usernames via per-account tokens. "
            "Using user_id as fallback for CRM storage."
        )

        # Cache the user_id to avoid repeated lookups
        self._username_cache[user_id] = user_id
        return user_id
