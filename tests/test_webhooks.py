"""
Tests for Instagram webhook endpoints.

Tests webhook verification, message parsing, and storage.
"""
import pytest
import hmac
import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.main import app
from app.db.connection import init_db, get_db_session
from app.repositories.message_repository import MessageRepository
from app.api.webhooks import _extract_message_data, _validate_webhook_signature


# Sample Instagram webhook payload (based on Facebook's documentation)
SAMPLE_WEBHOOK_PAYLOAD = {
    "object": "instagram",
    "entry": [
        {
            "id": "instagram-page-id",
            "time": 1234567890,
            "messaging": [
                {
                    "sender": {"id": "1234567890"},
                    "recipient": {"id": "0987654321"},
                    "timestamp": 1234567890123,
                    "message": {
                        "mid": "test_message_id_001",
                        "text": "Hello, I want to order a product"
                    }
                }
            ]
        }
    ]
}


# Complex payload with multiple messages and edge cases
COMPLEX_WEBHOOK_PAYLOAD = {
    "object": "instagram",
    "entry": [
        {
            "id": "instagram-page-id",
            "time": 1234567890,
            "messaging": [
                # Valid text message
                {
                    "sender": {"id": "user_001"},
                    "recipient": {"id": "page_001"},
                    "timestamp": 1234567890123,
                    "message": {
                        "mid": "msg_001",
                        "text": "First message"
                    }
                },
                # Image message (should be skipped)
                {
                    "sender": {"id": "user_002"},
                    "recipient": {"id": "page_001"},
                    "timestamp": 1234567891123,
                    "message": {
                        "mid": "msg_002",
                        "attachments": [
                            {
                                "type": "image",
                                "payload": {"url": "https://example.com/image.jpg"}
                            }
                        ]
                    }
                },
                # Another valid text message
                {
                    "sender": {"id": "user_003"},
                    "recipient": {"id": "page_001"},
                    "timestamp": 1234567892123,
                    "message": {
                        "mid": "msg_003",
                        "text": "Second message"
                    }
                },
                # Delivery receipt (should be skipped)
                {
                    "sender": {"id": "user_001"},
                    "recipient": {"id": "page_001"},
                    "timestamp": 1234567893123,
                    "delivery": {
                        "mids": ["msg_001"]
                    }
                }
            ]
        }
    ]
}


class TestWebhookVerification:
    """Tests for webhook verification endpoint (GET)."""
    
    def test_webhook_verification_success(self, monkeypatch):
        """Test successful webhook verification."""
        # Set the verify token for this test
        monkeypatch.setenv("FACEBOOK_VERIFY_TOKEN", "test_token_123")
        from app.config import Settings
        settings = Settings()
        
        # Patch the settings in the webhooks module
        import app.api.webhooks as webhooks_module
        webhooks_module.settings = settings
        
        client = TestClient(app)
        response = client.get(
            "/webhooks/instagram",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "test_token_123",
                "hub.challenge": "1234567890"
            }
        )
        assert response.status_code == 200
        assert response.json() == 1234567890
    
    def test_webhook_verification_invalid_token(self):
        """Test webhook verification with invalid token."""
        client = TestClient(app)
        response = client.get(
            "/webhooks/instagram",
            params={
                "hub.mode": "subscribe",
                "hub.verify_token": "wrong_token",
                "hub.challenge": "1234567890"
            }
        )
        assert response.status_code == 403


class TestMessageExtraction:
    """Tests for message data extraction logic."""
    
    def test_extract_valid_text_message(self):
        """Test extracting data from valid text message."""
        messaging_event = {
            "sender": {"id": "user_123"},
            "recipient": {"id": "page_456"},
            "timestamp": 1234567890123,
            "message": {
                "mid": "msg_abc",
                "text": "Hello world"
            }
        }
        
        result = _extract_message_data(messaging_event)
        
        assert result is not None
        assert result["id"] == "msg_abc"
        assert result["sender_id"] == "user_123"
        assert result["recipient_id"] == "page_456"
        assert result["text"] == "Hello world"
        assert isinstance(result["timestamp"], datetime)
        assert result["timestamp"].tzinfo == timezone.utc
    
    def test_extract_image_message_returns_none(self):
        """Test that image messages are skipped."""
        messaging_event = {
            "sender": {"id": "user_123"},
            "recipient": {"id": "page_456"},
            "timestamp": 1234567890123,
            "message": {
                "mid": "msg_abc",
                "attachments": [{"type": "image"}]
            }
        }
        
        result = _extract_message_data(messaging_event)
        assert result is None
    
    def test_extract_delivery_receipt_returns_none(self):
        """Test that delivery receipts are skipped."""
        messaging_event = {
            "sender": {"id": "user_123"},
            "recipient": {"id": "page_456"},
            "timestamp": 1234567890123,
            "delivery": {
                "mids": ["msg_abc"]
            }
        }
        
        result = _extract_message_data(messaging_event)
        assert result is None
    
    def test_extract_missing_fields_returns_none(self):
        """Test that messages with missing fields are skipped."""
        messaging_event = {
            "sender": {"id": "user_123"},
            # Missing recipient
            "timestamp": 1234567890123,
            "message": {
                "mid": "msg_abc",
                "text": "Hello"
            }
        }
        
        result = _extract_message_data(messaging_event)
        assert result is None


class TestWebhookMessageProcessing:
    """Tests for webhook message processing endpoint (POST)."""
    
    # Signature validation unit tests
    def test_valid_signature_accepted(self, monkeypatch):
        """Test that valid signatures are accepted."""
        monkeypatch.setenv("FACEBOOK_APP_SECRET", "test_secret_dev")
        from app.config import Settings
        import app.api.webhooks as webhooks_module
        webhooks_module.settings = Settings()
        
        payload = b'{"test": "data"}'
        signature = hmac.new(
            b"test_secret_dev",
            payload,
            hashlib.sha256
        ).hexdigest()
        
        assert _validate_webhook_signature(payload, f"sha256={signature}") is True
    
    def test_invalid_signature_rejected(self, monkeypatch):
        """Test that invalid signatures are rejected."""
        monkeypatch.setenv("FACEBOOK_APP_SECRET", "test_secret_dev")
        from app.config import Settings
        import app.api.webhooks as webhooks_module
        webhooks_module.settings = Settings()
        
        payload = b'{"test": "data"}'
        
        assert _validate_webhook_signature(payload, "sha256=invalid_signature") is False
    
    def test_missing_signature_header_rejected(self, monkeypatch):
        """Test that missing signature header is rejected."""
        monkeypatch.setenv("FACEBOOK_APP_SECRET", "test_secret_dev")
        from app.config import Settings
        import app.api.webhooks as webhooks_module
        webhooks_module.settings = Settings()
        
        payload = b'{"test": "data"}'
        
        assert _validate_webhook_signature(payload, "") is False
    
    def test_malformed_signature_header_rejected(self, monkeypatch):
        """Test that malformed signature header is rejected."""
        monkeypatch.setenv("FACEBOOK_APP_SECRET", "test_secret_dev")
        from app.config import Settings
        import app.api.webhooks as webhooks_module
        webhooks_module.settings = Settings()
        
        payload = b'{"test": "data"}'
        
        assert _validate_webhook_signature(payload, "invalid_format") is False
    
    # Webhook endpoint integration tests
    @patch('app.api.webhooks._validate_webhook_signature')
    def test_webhook_with_valid_payload(self, mock_validate):
        """Test webhook endpoint with valid message payload."""
        mock_validate.return_value = True
        
        client = TestClient(app)
        response = client.post(
            "/webhooks/instagram",
            json=SAMPLE_WEBHOOK_PAYLOAD,
            headers={"X-Hub-Signature-256": "sha256=mock_signature"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["messages_processed"] == 1
    
    @patch('app.api.webhooks._validate_webhook_signature')
    def test_webhook_with_complex_payload(self, mock_validate):
        """Test webhook with multiple messages and edge cases."""
        mock_validate.return_value = True
        
        client = TestClient(app)
        response = client.post(
            "/webhooks/instagram",
            json=COMPLEX_WEBHOOK_PAYLOAD,
            headers={"X-Hub-Signature-256": "sha256=mock_signature"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        # Should process 2 text messages, skip 2 non-text events
        assert data["messages_processed"] == 2
    
    @patch('app.api.webhooks._validate_webhook_signature')
    def test_webhook_with_invalid_payload_not_dict(self, mock_validate):
        """Test webhook with invalid payload (not a dictionary)."""
        mock_validate.return_value = True
        
        client = TestClient(app)
        response = client.post(
            "/webhooks/instagram",
            json=["invalid", "payload"],
            headers={"X-Hub-Signature-256": "sha256=mock_signature"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["messages_processed"] == 0
    
    @patch('app.api.webhooks._validate_webhook_signature')
    def test_webhook_with_missing_entry_field(self, mock_validate):
        """Test webhook with missing 'entry' field."""
        mock_validate.return_value = True
        
        client = TestClient(app)
        response = client.post(
            "/webhooks/instagram",
            json={"object": "instagram"},
            headers={"X-Hub-Signature-256": "sha256=mock_signature"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["messages_processed"] == 0
    
    @patch('app.api.webhooks._validate_webhook_signature')
    def test_webhook_handles_duplicate_messages(self, mock_validate):
        """Test that duplicate messages are handled gracefully."""
        mock_validate.return_value = True
        
        client = TestClient(app)
        
        # Send same webhook twice
        response1 = client.post(
            "/webhooks/instagram",
            json=SAMPLE_WEBHOOK_PAYLOAD,
            headers={"X-Hub-Signature-256": "sha256=mock_signature"}
        )
        response2 = client.post(
            "/webhooks/instagram",
            json=SAMPLE_WEBHOOK_PAYLOAD,
            headers={"X-Hub-Signature-256": "sha256=mock_signature"}
        )
        
        # Both should return 200
        assert response1.status_code == 200
        assert response2.status_code == 200
        
        # First should process 1 message
        assert response1.json()["messages_processed"] == 1
        # Second should skip duplicate (0 processed)
        assert response2.json()["messages_processed"] == 0
    
    @patch('app.api.webhooks._validate_webhook_signature')
    def test_webhook_rejects_invalid_signature(self, mock_validate):
        """Test webhook rejects requests with invalid signatures."""
        mock_validate.return_value = False
        
        client = TestClient(app)
        response = client.post(
            "/webhooks/instagram",
            json=SAMPLE_WEBHOOK_PAYLOAD,
            headers={"X-Hub-Signature-256": "sha256=invalid"}
        )
        
        assert response.status_code == 401
    
    def test_webhook_rejects_missing_signature_header(self):
        """Test webhook rejects requests without signature header."""
        client = TestClient(app)
        response = client.post(
            "/webhooks/instagram",
            json=SAMPLE_WEBHOOK_PAYLOAD
        )
        
        assert response.status_code == 401
