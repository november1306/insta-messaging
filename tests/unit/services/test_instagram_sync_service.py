"""
Unit tests for InstagramSyncService - conversations_api_id discovery and misclassification fix.

Tests verify:
- Discovery of the third business ID from conversation participants
- Fixing previously misclassified outbound messages
- Integration of discovery into the sync flow

These tests use an in-memory SQLite database and mock the Instagram API client.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone

from app.application.instagram_sync_service import InstagramSyncService
from app.db.models import Account, MessageModel
from app.domain.account_identity import AccountIdentity
from sqlalchemy import select

pytestmark = pytest.mark.unit


# ============================================
# Test Data - mirrors vs_mua_assistant scenario
# ============================================

# The three different IDs Instagram uses for the same business account
OAUTH_PROFILE_ID = "26189522574017165"         # From OAuth profile API
WEBHOOK_CHANNEL_ID = "17841450128868037"        # From webhook recipient.id
CONVERSATIONS_API_ID = "17841428904469177"      # From Conversations API from.id

ACCOUNT_ID = "acc_6ab75324bfa1"
USERNAME = "vs_mua_assistant"
CUSTOMER_ID = "25892293707058947"


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def account():
    """Account with two known IDs but no conversations_api_id yet."""
    return Account(
        id=ACCOUNT_ID,
        instagram_account_id=OAUTH_PROFILE_ID,
        messaging_channel_id=WEBHOOK_CHANNEL_ID,
        conversations_api_id=None,
        username=USERNAME,
        access_token_encrypted=b"encrypted_test_token",
    )


@pytest.fixture
def account_with_conv_id():
    """Account that already has conversations_api_id discovered."""
    return Account(
        id=ACCOUNT_ID,
        instagram_account_id=OAUTH_PROFILE_ID,
        messaging_channel_id=WEBHOOK_CHANNEL_ID,
        conversations_api_id=CONVERSATIONS_API_ID,
        username=USERNAME,
        access_token_encrypted=b"encrypted_test_token",
    )


@pytest.fixture
def mock_instagram_client():
    """Mock Instagram API client."""
    client = MagicMock()
    client.get_conversations = AsyncMock(return_value=[])
    client.get_conversation_messages = AsyncMock(return_value=[])
    client.get_user_profile = AsyncMock(return_value=None)
    return client


@pytest.fixture
def sync_service(test_db, mock_instagram_client):
    """InstagramSyncService with in-memory DB and mocked client."""
    return InstagramSyncService(test_db, mock_instagram_client)


def make_conversation(participants):
    """Helper to create a conversation dict with participants."""
    return {
        "id": "conv_123",
        "updated_time": "2026-02-17T00:00:00+0000",
        "participants": {
            "data": participants
        }
    }


# ============================================
# _discover_conversations_api_id Tests
# ============================================

class TestDiscoverConversationsApiId:
    """Tests for discovering the third business ID from conversation participants."""

    def test_discovers_new_id_by_username_match(self, sync_service, account):
        """Should find the conversations_api_id when participant username matches account."""
        # Arrange
        conversations = [make_conversation([
            {"id": CONVERSATIONS_API_ID, "username": USERNAME},
            {"id": CUSTOMER_ID, "username": "customer_user"},
        ])]

        # Act
        result = sync_service._discover_conversations_api_id(conversations, account)

        # Assert
        assert result == CONVERSATIONS_API_ID

    def test_returns_none_when_username_matches_known_id(self, sync_service, account):
        """Should return None if the matched participant uses an already-known ID."""
        # Arrange - participant uses the webhook channel ID (already known)
        conversations = [make_conversation([
            {"id": WEBHOOK_CHANNEL_ID, "username": USERNAME},
            {"id": CUSTOMER_ID, "username": "customer_user"},
        ])]

        # Act
        result = sync_service._discover_conversations_api_id(conversations, account)

        # Assert
        assert result is None

    def test_returns_none_when_no_username_match(self, sync_service, account):
        """Should return None if no participant username matches the account."""
        # Arrange
        conversations = [make_conversation([
            {"id": "some_id", "username": "other_business"},
            {"id": CUSTOMER_ID, "username": "customer_user"},
        ])]

        # Act
        result = sync_service._discover_conversations_api_id(conversations, account)

        # Assert
        assert result is None

    def test_returns_none_for_empty_conversations(self, sync_service, account):
        """Should handle empty conversation list."""
        result = sync_service._discover_conversations_api_id([], account)
        assert result is None

    def test_case_insensitive_username_match(self, sync_service, account):
        """Username matching should be case-insensitive."""
        # Arrange
        conversations = [make_conversation([
            {"id": CONVERSATIONS_API_ID, "username": "VS_MUA_ASSISTANT"},
            {"id": CUSTOMER_ID, "username": "customer_user"},
        ])]

        # Act
        result = sync_service._discover_conversations_api_id(conversations, account)

        # Assert
        assert result == CONVERSATIONS_API_ID

    def test_returns_none_when_account_has_no_username(self, sync_service):
        """Should handle account with no username gracefully."""
        # Arrange
        account = Account(
            id=ACCOUNT_ID,
            instagram_account_id=OAUTH_PROFILE_ID,
            messaging_channel_id=WEBHOOK_CHANNEL_ID,
            username=None,
            access_token_encrypted=b"encrypted_test_token",
        )
        conversations = [make_conversation([
            {"id": CONVERSATIONS_API_ID, "username": USERNAME},
            {"id": CUSTOMER_ID, "username": "customer_user"},
        ])]

        # Act
        result = sync_service._discover_conversations_api_id(conversations, account)

        # Assert
        assert result is None

    def test_scans_multiple_conversations(self, sync_service, account):
        """Should find the ID even if it's in the second conversation."""
        # Arrange - first conv has no matching username, second does
        conversations = [
            make_conversation([
                {"id": "unrelated_id", "username": "other_business"},
                {"id": "customer_1", "username": "customer_one"},
            ]),
            make_conversation([
                {"id": CONVERSATIONS_API_ID, "username": USERNAME},
                {"id": CUSTOMER_ID, "username": "customer_two"},
            ]),
        ]

        # Act
        result = sync_service._discover_conversations_api_id(conversations, account)

        # Assert
        assert result == CONVERSATIONS_API_ID

    def test_handles_missing_participant_fields(self, sync_service, account):
        """Should skip participants with missing id or username."""
        conversations = [make_conversation([
            {"id": CONVERSATIONS_API_ID},  # No username
            {"username": "customer_user"},  # No id
        ])]

        result = sync_service._discover_conversations_api_id(conversations, account)
        assert result is None


# ============================================
# _fix_misclassified_messages Tests
# ============================================

class TestFixMisclassifiedMessages:
    """Tests for fixing messages incorrectly classified as inbound."""

    @pytest.mark.asyncio
    async def test_fixes_misclassified_outbound_messages(self, sync_service, account, test_db):
        """Messages with sender_id=conversations_api_id should be corrected to outbound."""
        # Arrange - simulate 3 messages that were stored with wrong direction
        for i in range(3):
            msg = MessageModel(
                id=f"msg_misclassified_{i}",
                account_id=ACCOUNT_ID,
                sender_id=CONVERSATIONS_API_ID,  # Business sent via Conv API ID
                recipient_id=CUSTOMER_ID,
                message_text=f"Outbound message {i}",
                direction="inbound",  # Misclassified!
                timestamp=datetime.now(timezone.utc),
            )
            test_db.add(msg)
        await test_db.flush()

        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=OAUTH_PROFILE_ID,
            messaging_channel_id=WEBHOOK_CHANNEL_ID,
            conversations_api_id=CONVERSATIONS_API_ID,
        )

        # Act
        await sync_service._fix_misclassified_messages(account, identity, CONVERSATIONS_API_ID)

        # Assert - all 3 should now be outbound with normalized sender_id
        result = await test_db.execute(
            select(MessageModel).where(MessageModel.account_id == ACCOUNT_ID)
        )
        messages = result.scalars().all()
        assert len(messages) == 3
        for msg in messages:
            assert msg.direction == "outbound"
            assert msg.sender_id == WEBHOOK_CHANNEL_ID  # Normalized to effective_channel_id

    @pytest.mark.asyncio
    async def test_does_not_touch_correctly_classified_inbound(self, sync_service, account, test_db):
        """Genuine inbound messages (from customers) should not be modified."""
        # Arrange - a real inbound message from a customer
        msg = MessageModel(
            id="msg_real_inbound",
            account_id=ACCOUNT_ID,
            sender_id=CUSTOMER_ID,  # Customer sent this
            recipient_id=WEBHOOK_CHANNEL_ID,
            message_text="Hello from customer",
            direction="inbound",
            timestamp=datetime.now(timezone.utc),
        )
        test_db.add(msg)
        await test_db.flush()

        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=OAUTH_PROFILE_ID,
            messaging_channel_id=WEBHOOK_CHANNEL_ID,
            conversations_api_id=CONVERSATIONS_API_ID,
        )

        # Act
        await sync_service._fix_misclassified_messages(account, identity, CONVERSATIONS_API_ID)

        # Assert - should remain inbound
        result = await test_db.execute(
            select(MessageModel).where(MessageModel.id == "msg_real_inbound")
        )
        msg = result.scalar_one()
        assert msg.direction == "inbound"
        assert msg.sender_id == CUSTOMER_ID

    @pytest.mark.asyncio
    async def test_does_not_touch_other_accounts(self, sync_service, account, test_db):
        """Messages from other accounts should not be affected."""
        # Arrange - message from a different account with same conversations_api_id
        msg = MessageModel(
            id="msg_other_account",
            account_id="acc_other",
            sender_id=CONVERSATIONS_API_ID,
            recipient_id=CUSTOMER_ID,
            message_text="Other account message",
            direction="inbound",
            timestamp=datetime.now(timezone.utc),
        )
        test_db.add(msg)
        await test_db.flush()

        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=OAUTH_PROFILE_ID,
            messaging_channel_id=WEBHOOK_CHANNEL_ID,
            conversations_api_id=CONVERSATIONS_API_ID,
        )

        # Act
        await sync_service._fix_misclassified_messages(account, identity, CONVERSATIONS_API_ID)

        # Assert - different account's message should be untouched
        result = await test_db.execute(
            select(MessageModel).where(MessageModel.id == "msg_other_account")
        )
        msg = result.scalar_one()
        assert msg.direction == "inbound"
        assert msg.sender_id == CONVERSATIONS_API_ID

    @pytest.mark.asyncio
    async def test_does_not_touch_already_outbound(self, sync_service, account, test_db):
        """Messages already correctly marked outbound should not be modified."""
        # Arrange
        msg = MessageModel(
            id="msg_already_outbound",
            account_id=ACCOUNT_ID,
            sender_id=WEBHOOK_CHANNEL_ID,  # Already normalized
            recipient_id=CUSTOMER_ID,
            message_text="Correct outbound",
            direction="outbound",
            timestamp=datetime.now(timezone.utc),
        )
        test_db.add(msg)
        await test_db.flush()

        identity = AccountIdentity(
            account_id=ACCOUNT_ID,
            instagram_account_id=OAUTH_PROFILE_ID,
            messaging_channel_id=WEBHOOK_CHANNEL_ID,
            conversations_api_id=CONVERSATIONS_API_ID,
        )

        # Act
        await sync_service._fix_misclassified_messages(account, identity, CONVERSATIONS_API_ID)

        # Assert
        result = await test_db.execute(
            select(MessageModel).where(MessageModel.id == "msg_already_outbound")
        )
        msg = result.scalar_one()
        assert msg.direction == "outbound"
        assert msg.sender_id == WEBHOOK_CHANNEL_ID


# ============================================
# sync_account Integration Tests
# ============================================

class TestSyncAccountDiscovery:
    """Tests verifying discovery is integrated into the sync flow."""

    @pytest.mark.asyncio
    async def test_sync_discovers_and_stores_conversations_api_id(
        self, sync_service, account, mock_instagram_client
    ):
        """sync_account should discover conversations_api_id and store it on the account."""
        # Arrange - API returns conversation with the third ID
        mock_instagram_client.get_conversations.return_value = [
            make_conversation([
                {"id": CONVERSATIONS_API_ID, "username": USERNAME},
                {"id": CUSTOMER_ID, "username": "customer_user"},
            ])
        ]
        mock_instagram_client.get_conversation_messages.return_value = []

        # Act
        await sync_service.sync_account(account, hours_back=999)

        # Assert - conversations_api_id should be stored on account
        assert account.conversations_api_id == CONVERSATIONS_API_ID

    @pytest.mark.asyncio
    async def test_sync_does_not_overwrite_existing_conversations_api_id(
        self, sync_service, account_with_conv_id, mock_instagram_client
    ):
        """sync_account should not overwrite an existing conversations_api_id with same value."""
        # Arrange
        mock_instagram_client.get_conversations.return_value = [
            make_conversation([
                {"id": CONVERSATIONS_API_ID, "username": USERNAME},
                {"id": CUSTOMER_ID, "username": "customer_user"},
            ])
        ]
        mock_instagram_client.get_conversation_messages.return_value = []

        # Act
        await sync_service.sync_account(account_with_conv_id, hours_back=999)

        # Assert - should still be the same
        assert account_with_conv_id.conversations_api_id == CONVERSATIONS_API_ID
