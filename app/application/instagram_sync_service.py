"""
Instagram Sync Service - Unified message synchronization logic.

This service handles fetching and storing messages from Instagram's Conversations API.
It consolidates the duplicated sync logic from:
- account_linking_service.py (_sync_conversation_history)
- ui.py (sync_messages_from_instagram)

Key features:
- Two-phase fetch: Fast conversation list, then messages for recent only
- 24-hour filter: Only syncs conversations within Instagram's messaging window
- Retry logic: Handles transient API failures with exponential backoff
- Deduplication: Skips messages already in database
- Consistent ID handling: Uses AccountIdentity for all ID operations
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import asyncio
import logging

from app.db.models import Account, MessageModel, InstagramProfile
from app.domain.account_identity import AccountIdentity
from app.clients.instagram_client import InstagramClient

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """
    Result of a sync operation.

    Attributes:
        conversations_found: Total conversations returned by Instagram API
        conversations_synced: Conversations within the time window that were processed
        messages_synced: New messages stored in database
        messages_skipped: Messages already in database (duplicates)
        errors: Non-fatal errors encountered during sync
    """
    conversations_found: int = 0
    conversations_synced: int = 0
    messages_synced: int = 0
    messages_skipped: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class InstagramSyncService:
    """
    Service for synchronizing Instagram messages to local database.

    This service implements the two-phase fetch pattern for performance:
    1. Phase 1: Fetch conversation list WITHOUT messages (fast, ~2s)
    2. Phase 2: Filter by time, then fetch messages for recent conversations only

    This is much faster than fetching all messages upfront, especially for
    accounts with many historical conversations.

    Usage:
        async with httpx.AsyncClient() as http_client:
            instagram_client = InstagramClient(http_client, access_token)
            sync_service = InstagramSyncService(db, instagram_client)
            result = await sync_service.sync_account(account)
    """

    def __init__(
        self,
        db: AsyncSession,
        instagram_client: InstagramClient
    ):
        """
        Initialize sync service.

        Args:
            db: SQLAlchemy async session
            instagram_client: Configured Instagram API client
        """
        self.db = db
        self.instagram_client = instagram_client

    async def sync_account(
        self,
        account: Account,
        hours_back: int = 24,
        max_messages_per_conversation: int = 25,
        cache_profiles: bool = True
    ) -> SyncResult:
        """
        Sync messages from Instagram API for an account.

        Args:
            account: Account to sync messages for
            hours_back: Only sync conversations updated within this many hours (default 24)
            max_messages_per_conversation: Max messages to fetch per conversation
            cache_profiles: Whether to cache customer profiles

        Returns:
            SyncResult with sync statistics
        """
        result = SyncResult()
        identity = AccountIdentity.from_account(account)

        try:
            # PHASE 1: Fast fetch of conversation list
            logger.info(f"📥 Phase 1: Fetching conversation list for account {account.id}...")
            conversations = await self._fetch_conversations_with_retry()

            if not conversations:
                logger.info(f"No conversations to sync for account {account.id}")
                return result

            result.conversations_found = len(conversations)

            # Filter to recent conversations
            cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours_back)
            recent_conversations = self._filter_by_time(conversations, cutoff_time)

            logger.info(
                f"📅 Phase 1 complete: {len(recent_conversations)}/{result.conversations_found} "
                f"conversations from last {hours_back}h"
            )

            # PHASE 2: Fetch and store messages for recent conversations
            logger.info(f"📥 Phase 2: Syncing messages for {len(recent_conversations)} conversations...")

            for conv in recent_conversations:
                try:
                    conv_result = await self._sync_conversation(
                        account=account,
                        identity=identity,
                        conversation=conv,
                        max_messages=max_messages_per_conversation,
                        cache_profiles=cache_profiles
                    )
                    result.conversations_synced += 1
                    result.messages_synced += conv_result.messages_synced
                    result.messages_skipped += conv_result.messages_skipped
                except Exception as e:
                    conv_id = conv.get("id", "unknown")[:20]
                    logger.warning(f"Failed to sync conversation {conv_id}...: {e}")
                    result.errors.append(f"Conversation {conv_id}: {str(e)}")

            logger.info(
                f"✅ Sync complete for account {account.id}: "
                f"{result.conversations_synced}/{result.conversations_found} conversations, "
                f"{result.messages_synced} new messages, {result.messages_skipped} skipped"
            )

        except Exception as e:
            logger.warning(f"⚠️ Sync failed for account {account.id}: {e}")
            result.errors.append(str(e))

        return result

    async def _fetch_conversations_with_retry(
        self,
        max_retries: int = 2
    ) -> list[dict]:
        """
        Fetch conversations with retry logic for transient API failures.

        Instagram API occasionally returns 500 errors, especially for newly
        linked accounts. This method retries with exponential backoff.

        Returns:
            List of conversations (empty list if API fails after all retries)
        """
        for attempt in range(max_retries + 1):
            try:
                conversations = await self.instagram_client.get_conversations(
                    limit=50,
                    include_messages=False
                )
                if conversations is not None:
                    return conversations
                # API returned None (error response) - treat as retryable
                raise Exception("Instagram API returned error response")
            except Exception as e:
                is_last_attempt = attempt >= max_retries
                if is_last_attempt:
                    logger.warning(
                        f"⚠️ Conversation fetch failed after {max_retries + 1} attempts: {e}. "
                        "Sync will be attempted on next inbound message."
                    )
                    return []

                delay = attempt + 1  # 1s, 2s
                logger.warning(
                    f"⚠️ Conversation fetch attempt {attempt + 1}/{max_retries + 1} failed, "
                    f"retrying in {delay}s: {e}"
                )
                await asyncio.sleep(delay)

        return []  # Unreachable, but satisfies type checker

    def _filter_by_time(
        self,
        conversations: list[dict],
        cutoff_time: datetime
    ) -> list[dict]:
        """
        Filter conversations to those updated after cutoff time.

        Args:
            conversations: List of conversation dicts from Instagram API
            cutoff_time: Only include conversations updated after this time

        Returns:
            Filtered list of recent conversations
        """
        recent = []
        for conv in conversations:
            updated_time_str = conv.get("updated_time")
            if updated_time_str:
                try:
                    # Parse ISO format with flexible timezone handling
                    # Instagram typically: 2026-01-13T21:30:45+0000
                    # Also support: Z suffix, different offsets
                    timestamp = updated_time_str.replace('+0000', '+00:00').replace('Z', '+00:00')
                    updated_time = datetime.fromisoformat(timestamp)

                    if updated_time >= cutoff_time:
                        recent.append(conv)
                except (ValueError, AttributeError) as e:
                    # If parsing fails, include to be safe
                    logger.warning(f"⚠️ Could not parse updated_time: {updated_time_str} ({type(e).__name__})")
                    recent.append(conv)
            else:
                # No timestamp, include to be safe
                recent.append(conv)
        return recent

    async def _sync_conversation(
        self,
        account: Account,
        identity: AccountIdentity,
        conversation: dict,
        max_messages: int,
        cache_profiles: bool
    ) -> SyncResult:
        """
        Sync a single conversation's messages.

        Args:
            account: Account model
            identity: AccountIdentity for ID resolution
            conversation: Conversation dict from Instagram API
            max_messages: Maximum messages to fetch
            cache_profiles: Whether to cache customer profiles

        Returns:
            SyncResult for this conversation
        """
        result = SyncResult()
        conv_id = conversation.get("id")
        if not conv_id:
            return result

        # Identify the customer from participants
        customer_id = self._identify_customer(conversation, identity)

        # Cache customer profile if requested
        if cache_profiles and customer_id:
            await self._cache_customer_profile(customer_id)

        # Fetch messages for this conversation
        messages = await self.instagram_client.get_conversation_messages(
            conv_id,
            limit=max_messages
        )

        if not messages:
            return result

        # If we couldn't identify customer from participants, try from messages
        if not customer_id:
            customer_id = self._identify_customer_from_messages(messages, identity)

        if not customer_id:
            logger.warning(f"⚠️ Could not identify customer in conversation {conv_id[:20]}...")
            return result

        # Store messages
        for msg in messages:
            try:
                stored = await self._store_message(
                    account=account,
                    identity=identity,
                    message=msg,
                    customer_id=customer_id
                )
                if stored:
                    result.messages_synced += 1
                else:
                    result.messages_skipped += 1
            except IntegrityError:
                # Race condition - message was added by webhook while syncing
                await self.db.rollback()
                result.messages_skipped += 1
            except Exception as e:
                msg_id = msg.get("id", "unknown")
                logger.warning(f"Failed to store message {msg_id}: {e}")
                result.errors.append(f"Message {msg_id}: {str(e)}")

        return result

    def _identify_customer(
        self,
        conversation: dict,
        identity: AccountIdentity
    ) -> Optional[str]:
        """
        Identify customer ID from conversation participants.

        Instagram conversations have exactly 2 participants:
        - The business account (matches one of our known IDs)
        - The customer (the other participant)

        Args:
            conversation: Conversation dict with 'participants' field
            identity: AccountIdentity for business ID detection

        Returns:
            Customer's Instagram user ID, or None if not found
        """
        participants = conversation.get("participants", {}).get("data", [])
        if len(participants) != 2:
            return None

        participant1_id = participants[0].get("id")
        participant2_id = participants[1].get("id")

        if not participant1_id or not participant2_id:
            return None

        # Find which participant is NOT the business account
        if identity.is_business_id(participant1_id):
            return participant2_id
        elif identity.is_business_id(participant2_id):
            return participant1_id
        else:
            # Neither matches known business IDs - assume first is business
            # (Instagram convention: lists business account first)
            logger.debug(
                f"Neither participant matches known business IDs "
                f"({participant1_id}, {participant2_id}), assuming first is business"
            )
            return participant2_id

    def _identify_customer_from_messages(
        self,
        messages: list[dict],
        identity: AccountIdentity
    ) -> Optional[str]:
        """
        Fallback: Identify customer by scanning message senders.

        Used when participants field is not available or empty.

        Args:
            messages: List of message dicts
            identity: AccountIdentity for business ID detection

        Returns:
            First non-business sender ID found, or None
        """
        for msg in messages:
            sender_id = msg.get("from", {}).get("id")
            if sender_id and not identity.is_business_id(sender_id):
                return sender_id
        return None

    async def _store_message(
        self,
        account: Account,
        identity: AccountIdentity,
        message: dict,
        customer_id: str
    ) -> bool:
        """
        Store a single message in the database.

        Args:
            account: Account model
            identity: AccountIdentity for ID normalization
            message: Message dict from Instagram API
            customer_id: Identified customer Instagram user ID

        Returns:
            True if message was stored, False if it already existed
        """
        message_id = message.get("id")
        if not message_id:
            return False

        # Check if message already exists (deduplication)
        result = await self.db.execute(
            select(MessageModel).where(MessageModel.id == message_id)
        )
        if result.scalar_one_or_none():
            return False  # Already exists

        # Extract message data
        message_text = message.get("message", "")
        created_time = message.get("created_time")
        from_data = message.get("from", {})
        sender_id = from_data.get("id", "unknown")

        # Determine direction using AccountIdentity
        direction = identity.detect_direction(sender_id)

        # Normalize IDs for consistent storage
        normalized_sender, normalized_recipient = identity.normalize_message_ids(
            sender_id, customer_id
        )

        # Parse timestamp
        try:
            if created_time:
                timestamp = datetime.fromisoformat(
                    created_time.replace("+0000", "+00:00").replace("Z", "+00:00")
                )
            else:
                timestamp = datetime.now(timezone.utc)
        except Exception:
            timestamp = datetime.now(timezone.utc)

        # Create message record
        new_message = MessageModel(
            id=message_id,
            account_id=account.id,
            sender_id=normalized_sender,
            recipient_id=normalized_recipient,
            message_text=message_text or "",
            direction=direction,
            timestamp=timestamp,
            delivery_status="synced"  # Mark as synced from API
        )
        self.db.add(new_message)
        return True

    async def _cache_customer_profile(self, customer_id: str):
        """
        Cache customer profile in InstagramProfile table.

        Args:
            customer_id: Instagram user ID to cache profile for
        """
        try:
            profile = await self.instagram_client.get_user_profile(customer_id)
            if not profile:
                return

            # Check if profile already cached
            result = await self.db.execute(
                select(InstagramProfile).where(InstagramProfile.sender_id == customer_id)
            )
            cached = result.scalar_one_or_none()

            username = profile.get("username", "")
            profile_pic = profile.get("profile_picture_url")

            if cached:
                # Update existing
                cached.username = username
                cached.profile_picture_url = profile_pic
                cached.last_updated = datetime.now(timezone.utc)
            else:
                # Create new
                new_profile = InstagramProfile(
                    sender_id=customer_id,
                    username=username,
                    profile_picture_url=profile_pic,
                    last_updated=datetime.now(timezone.utc)
                )
                self.db.add(new_profile)
        except Exception as e:
            # Profile caching is non-critical, just log and continue
            logger.debug(f"Failed to cache profile for {customer_id}: {e}")
