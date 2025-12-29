"""
Message Repository implementation using SQLAlchemy.

Refactored to:
- Use rich domain models from app/domain/entities.py
- Remove CRM MySQL dual storage (unused)
- Use centralized username cache
- Implement complete IMessageRepository interface
"""

from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
import logging

from app.core.interfaces import IMessageRepository
from app.domain.entities import Message, Attachment, Conversation, DuplicateMessageError
from app.domain.value_objects import (
    MessageId,
    AccountId,
    InstagramUserId,
    AttachmentId,
    IdempotencyKey,
    optional_idempotency_key
)
from app.db.models import MessageModel, MessageAttachment, Account

logger = logging.getLogger(__name__)


class MessageRepository(IMessageRepository):
    """
    SQLAlchemy implementation of IMessageRepository.

    Handles conversion between:
    - Domain entities (Message, Attachment) → ORM models (MessageModel, MessageAttachment)
    - ORM models → Domain entities

    Simplified:
    - No CRM MySQL dual storage (removed as unused)
    - Uses centralized username cache
    - Clean domain model conversion
    """

    def __init__(self, db_session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            db_session: SQLAlchemy async session
        """
        self._db = db_session

    async def save(self, message: Message) -> Message:
        """
        Save a message and its attachments atomically.

        Args:
            message: Domain Message entity

        Returns:
            Saved message

        Raises:
            DuplicateMessageError: If message ID already exists
        """
        try:
            # Convert domain model → ORM model
            db_message = self._to_orm(message)

            # Add message to session
            self._db.add(db_message)

            # Add attachments
            for attachment in message.attachments:
                db_attachment = self._attachment_to_orm(attachment)
                self._db.add(db_attachment)

            # Flush to database
            await self._db.flush()

            logger.info(
                f"💾 Saved message {message.id} ({message.direction}) "
                f"with {message.attachment_count} attachment(s)"
            )

            return message

        except IntegrityError as e:
            logger.error(f"Message {message.id} already exists")
            raise DuplicateMessageError(message.id) from e
        except Exception as e:
            logger.error(f"Failed to save message {message.id}: {e}")
            raise

    async def get_by_id(self, message_id: MessageId) -> Optional[Message]:
        """
        Retrieve message by ID with attachments.

        Args:
            message_id: Message identifier

        Returns:
            Message with attachments if found, None otherwise
        """
        try:
            # Query with eager loading of attachments
            stmt = (
                select(MessageModel)
                .where(MessageModel.id == message_id.value)
                .options(joinedload(MessageModel.attachments))
            )
            result = await self._db.execute(stmt)
            db_message = result.unique().scalar_one_or_none()

            if db_message is None:
                return None

            # Convert ORM → domain model
            message = self._from_orm(db_message)

            logger.debug(
                f"📖 Retrieved message {message_id} "
                f"with {message.attachment_count} attachment(s)"
            )

            return message

        except Exception as e:
            logger.error(f"Failed to retrieve message {message_id}: {e}")
            raise

    async def get_by_idempotency_key(
        self,
        idempotency_key: IdempotencyKey
    ) -> Optional[Message]:
        """
        Get message by idempotency key (for duplicate detection).

        Args:
            idempotency_key: Idempotency key

        Returns:
            Message if found, None otherwise
        """
        try:
            stmt = (
                select(MessageModel)
                .where(MessageModel.idempotency_key == idempotency_key.value)
                .options(joinedload(MessageModel.attachments))
            )
            result = await self._db.execute(stmt)
            db_message = result.unique().scalar_one_or_none()

            if db_message is None:
                return None

            message = self._from_orm(db_message)
            logger.debug(f"🔑 Found message by idempotency key: {message.id}")
            return message

        except Exception as e:
            logger.error(f"Failed to get message by idempotency key: {e}")
            raise

    async def get_conversations_for_account(
        self,
        account_id: AccountId,
        limit: int = 50
    ) -> List[Conversation]:
        """
        Get conversations for an account (grouped by contact).

        Returns the latest message for each unique contact.

        Args:
            account_id: Account identifier
            limit: Maximum conversations to return

        Returns:
            List of conversations ordered by latest message
        """
        try:
            # Subquery to get latest message per contact
            # For each contact (sender_id), get the most recent message
            latest_msg_subq = (
                select(
                    MessageModel.sender_id.label('contact_id'),
                    func.max(MessageModel.timestamp).label('latest_timestamp')
                )
                .where(MessageModel.account_id == account_id.value)
                .where(MessageModel.direction == 'inbound')  # Only customer messages
                .group_by(MessageModel.sender_id)
                .subquery()
            )

            # Get full message details for latest message per contact
            stmt = (
                select(MessageModel)
                .join(
                    latest_msg_subq,
                    (MessageModel.sender_id == latest_msg_subq.c.contact_id) &
                    (MessageModel.timestamp == latest_msg_subq.c.latest_timestamp)
                )
                .where(MessageModel.account_id == account_id.value)
                .options(joinedload(MessageModel.attachments))
                .order_by(desc(MessageModel.timestamp))
                .limit(limit)
            )

            result = await self._db.execute(stmt)
            db_messages = result.unique().scalars().all()

            # Convert to Conversation objects
            conversations = []
            for db_msg in db_messages:
                message = self._from_orm(db_msg)

                # Count total messages for this contact
                count_stmt = select(func.count(MessageModel.id)).where(
                    MessageModel.account_id == account_id.value,
                    MessageModel.sender_id == message.sender_id.value
                )
                count_result = await self._db.execute(count_stmt)
                total_messages = count_result.scalar()

                conversation = Conversation(
                    account_id=account_id,
                    contact_id=message.sender_id,
                    contact_username=None,  # Fetched separately if needed
                    latest_message=message,
                    unread_count=0,  # TODO: Track read status
                    total_messages=total_messages
                )
                conversations.append(conversation)

            logger.debug(
                f"📬 Retrieved {len(conversations)} conversations "
                f"for account {account_id}"
            )

            return conversations

        except Exception as e:
            logger.error(f"Failed to get conversations: {e}")
            raise

    # Domain ↔ ORM conversion methods

    def _to_orm(self, message: Message) -> MessageModel:
        """Convert domain Message → ORM MessageModel"""
        return MessageModel(
            id=message.id.value,
            account_id=message.account_id.value,
            sender_id=message.sender_id.value,
            recipient_id=message.recipient_id.value,
            message_text=message.message_text,
            direction=message.direction,
            timestamp=message.timestamp,
            created_at=message.created_at,
            idempotency_key=message.idempotency_key.value if message.idempotency_key else None,
            delivery_status=message.delivery_status,
            error_code=message.error_code,
            error_message=message.error_message
        )

    def _from_orm(self, db_message: MessageModel) -> Message:
        """Convert ORM MessageModel → domain Message"""
        # Convert attachments
        attachments = [
            self._attachment_from_orm(db_att)
            for db_att in db_message.attachments
        ]

        return Message(
            id=MessageId(db_message.id),
            account_id=AccountId(db_message.account_id),
            sender_id=InstagramUserId(db_message.sender_id),
            recipient_id=InstagramUserId(db_message.recipient_id),
            message_text=db_message.message_text,
            direction=db_message.direction,
            timestamp=db_message.timestamp,
            created_at=db_message.created_at,
            attachments=attachments,
            idempotency_key=optional_idempotency_key(db_message.idempotency_key),
            delivery_status=db_message.delivery_status,
            error_code=db_message.error_code,
            error_message=db_message.error_message
        )

    def _attachment_to_orm(self, attachment: Attachment) -> MessageAttachment:
        """Convert domain Attachment → ORM MessageAttachment"""
        return MessageAttachment(
            id=attachment.id.value,
            message_id=attachment.message_id.value,
            attachment_index=attachment.attachment_index,
            media_type=attachment.media_type,
            media_url=attachment.media_url,
            media_url_local=attachment.media_url_local,
            media_mime_type=attachment.media_mime_type
        )

    def _attachment_from_orm(self, db_attachment: MessageAttachment) -> Attachment:
        """Convert ORM MessageAttachment → domain Attachment"""
        return Attachment(
            id=AttachmentId.from_string(db_attachment.id),
            message_id=MessageId(db_attachment.message_id),
            attachment_index=db_attachment.attachment_index,
            media_type=db_attachment.media_type,
            media_url=db_attachment.media_url,
            media_url_local=db_attachment.media_url_local,
            media_mime_type=db_attachment.media_mime_type
        )
