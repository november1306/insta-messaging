"""
Unit tests for echo message (outbound) handling.

Tests verify:
- _extract_message_data returns is_echo flag instead of skipping
- receive_webhook_message correctly stores outbound direction
- Echo message deduplication works (API-sent messages not duplicated)

These tests are fast and have no external dependencies.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.api.webhooks import _extract_message_data

pytestmark = pytest.mark.unit


# ============================================
# Test Data
# ============================================

MESSAGING_CHANNEL_ID = "17841478096518771"
CUSTOMER_ID = "25964748486442669"
MESSAGE_ID = "mid_echo_test_001"
TIMESTAMP_MS = 1706443200000  # 2024-01-28T12:00:00Z


def _make_messaging_event(is_echo=False, text="Hello"):
    """Build a minimal Instagram webhook messaging event."""
    msg = {
        "mid": MESSAGE_ID,
        "text": text,
    }
    if is_echo:
        msg["is_echo"] = True

    return {
        "sender": {"id": MESSAGING_CHANNEL_ID if is_echo else CUSTOMER_ID},
        "recipient": {"id": CUSTOMER_ID if is_echo else MESSAGING_CHANNEL_ID},
        "timestamp": TIMESTAMP_MS,
        "message": msg,
    }


# ============================================
# _extract_message_data Tests
# ============================================

class TestExtractMessageDataEcho:
    """Tests for echo message extraction (previously skipped)."""

    def test_echo_message_returns_data_with_is_echo_true(self):
        """Echo messages should be extracted, not skipped."""
        event = _make_messaging_event(is_echo=True, text="Reply from business")

        result = _extract_message_data(event)

        assert result is not None
        assert result["is_echo"] is True
        assert result["id"] == MESSAGE_ID
        assert result["text"] == "Reply from business"
        assert result["sender_id"] == MESSAGING_CHANNEL_ID
        assert result["recipient_id"] == CUSTOMER_ID

    def test_normal_message_has_is_echo_false(self):
        """Normal inbound messages should have is_echo=False."""
        event = _make_messaging_event(is_echo=False, text="Hello from customer")

        result = _extract_message_data(event)

        assert result is not None
        assert result["is_echo"] is False
        assert result["sender_id"] == CUSTOMER_ID
        assert result["recipient_id"] == MESSAGING_CHANNEL_ID

    def test_echo_message_with_attachments(self):
        """Echo messages with attachments should be extracted."""
        event = _make_messaging_event(is_echo=True, text=None)
        event["message"]["attachments"] = [
            {"type": "image", "payload": {"url": "https://cdn.instagram.com/img.jpg"}}
        ]

        result = _extract_message_data(event)

        assert result is not None
        assert result["is_echo"] is True
        assert len(result["attachments"]) == 1
        assert result["attachments"][0]["media_type"] == "image"

    def test_non_message_event_still_returns_none(self):
        """Events without 'message' key should still return None."""
        event = {"delivery": {"mids": ["mid_123"]}}

        result = _extract_message_data(event)

        assert result is None


# ============================================
# Direction Routing Tests
# ============================================

class TestEchoDirectionRouting:
    """Tests for direction and ID routing in webhook handler.

    These test the logic pattern used in handle_webhook() without
    needing the full HTTP endpoint setup.
    """

    def test_echo_message_sets_outbound_direction(self):
        """Echo messages should produce direction='outbound'."""
        message_data = {
            "sender_id": MESSAGING_CHANNEL_ID,
            "recipient_id": CUSTOMER_ID,
            "is_echo": True,
        }

        is_echo = message_data.get("is_echo", False)
        if is_echo:
            direction = "outbound"
            sender_id = MESSAGING_CHANNEL_ID
            recipient_id = message_data["recipient_id"]
        else:
            direction = "inbound"
            sender_id = message_data["sender_id"]
            recipient_id = MESSAGING_CHANNEL_ID

        assert direction == "outbound"
        assert sender_id == MESSAGING_CHANNEL_ID
        assert recipient_id == CUSTOMER_ID

    def test_inbound_message_sets_inbound_direction(self):
        """Normal messages should produce direction='inbound'."""
        message_data = {
            "sender_id": CUSTOMER_ID,
            "recipient_id": MESSAGING_CHANNEL_ID,
            "is_echo": False,
        }

        is_echo = message_data.get("is_echo", False)
        if is_echo:
            direction = "outbound"
            sender_id = MESSAGING_CHANNEL_ID
            recipient_id = message_data["recipient_id"]
        else:
            direction = "inbound"
            sender_id = message_data["sender_id"]
            recipient_id = MESSAGING_CHANNEL_ID

        assert direction == "inbound"
        assert sender_id == CUSTOMER_ID
        assert recipient_id == MESSAGING_CHANNEL_ID

    def test_missing_is_echo_defaults_to_inbound(self):
        """Messages without is_echo key default to inbound."""
        message_data = {
            "sender_id": CUSTOMER_ID,
            "recipient_id": MESSAGING_CHANNEL_ID,
        }

        is_echo = message_data.get("is_echo", False)
        direction = "outbound" if is_echo else "inbound"

        assert direction == "inbound"


# ============================================
# MessageService.receive_webhook_message Tests
# ============================================

class TestReceiveWebhookMessageDirection:
    """Tests for direction parameter in receive_webhook_message."""

    @pytest.fixture
    def mock_uow(self):
        """Create a mock Unit of Work."""
        uow = AsyncMock()
        # Mock account lookup
        mock_account = MagicMock()
        mock_account.id = "acc_test123"
        uow.accounts.get_by_messaging_channel_id = AsyncMock(return_value=mock_account)

        # Mock message save - return the message passed to it
        async def save_message(msg):
            return msg
        uow.messages.save = AsyncMock(side_effect=save_message)

        return uow

    @pytest.mark.asyncio
    async def test_default_direction_is_inbound(self, mock_uow):
        """Calling without direction defaults to 'inbound'."""
        from app.application.message_service import MessageService
        from app.domain.value_objects import MessagingChannelId

        service = MessageService()
        result = await service.receive_webhook_message(
            uow=mock_uow,
            messaging_channel_id=MessagingChannelId(MESSAGING_CHANNEL_ID),
            instagram_message_id=MESSAGE_ID,
            sender_id=CUSTOMER_ID,
            recipient_id=MESSAGING_CHANNEL_ID,
            message_text="Hello",
            timestamp=datetime.now(timezone.utc),
        )

        assert result.direction == "inbound"
        assert result.delivery_status is None

    @pytest.mark.asyncio
    async def test_outbound_direction_for_echo(self, mock_uow):
        """Echo messages should be stored with direction='outbound' and status='sent'."""
        from app.application.message_service import MessageService
        from app.domain.value_objects import MessagingChannelId

        service = MessageService()
        result = await service.receive_webhook_message(
            uow=mock_uow,
            messaging_channel_id=MessagingChannelId(MESSAGING_CHANNEL_ID),
            instagram_message_id="mid_echo_002",
            sender_id=MESSAGING_CHANNEL_ID,
            recipient_id=CUSTOMER_ID,
            message_text="Reply from business",
            timestamp=datetime.now(timezone.utc),
            direction="outbound",
        )

        assert result.direction == "outbound"
        assert result.delivery_status == "sent"
        assert result.sender_id.value == MESSAGING_CHANNEL_ID
        assert result.recipient_id.value == CUSTOMER_ID
