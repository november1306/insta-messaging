#!/usr/bin/env python3
"""
Test script for webhook forwarding implementation (Task 9)

Verifies:
1. Webhook payload construction matches OpenAPI spec
2. HMAC-SHA256 signature generation works correctly
3. HTTP client integration works
"""
import asyncio
import json
import hmac
import hashlib
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch

import httpx

from app.services.webhook_forwarder import WebhookForwarder
from app.core.interfaces import Message
from app.db.models import Account


async def test_payload_construction():
    """Test that webhook payload matches OpenAPI InboundMessageWebhook schema"""
    print("🧪 Test 1: Payload construction")

    # Create test message
    message = Message(
        id="test_msg_123",
        sender_id="1234567890",
        recipient_id="0987654321",
        message_text="Hello from customer!",
        direction="inbound",
        timestamp=datetime(2025, 11, 8, 10, 30, 0, tzinfo=timezone.utc)
    )

    # Create test account
    account = Account(
        id="acc_test123",
        instagram_account_id="0987654321",
        username="test_business",
        access_token_encrypted="dummy",
        crm_webhook_url="https://crm.example.com/webhook",
        webhook_secret="test_secret"
    )

    # Create forwarder with mock HTTP client
    http_client = AsyncMock(spec=httpx.AsyncClient)
    forwarder = WebhookForwarder(http_client)

    # Build payload
    payload = forwarder._build_payload(message, account)

    # Verify payload structure
    assert payload["event"] == "message.received", "Event type should be message.received"
    assert payload["message_id"] == "test_msg_123", "Message ID should match"
    assert payload["account_id"] == "acc_test123", "Account ID should match"
    assert payload["sender_id"] == "1234567890", "Sender ID should match"
    assert payload["message"] == "Hello from customer!", "Message text should match"
    assert payload["message_type"] == "text", "Message type should be text"
    assert payload["timestamp"] == "2025-11-08T10:30:00+00:00", "Timestamp should be ISO format"
    assert payload["instagram_message_id"] == "test_msg_123", "Instagram message ID should match"
    assert payload["conversation_id"] == "conv_1234567890_0987654321", "Conversation ID should be correct"

    print("✅ Payload construction test passed")
    return True


async def test_signature_generation():
    """Test HMAC-SHA256 signature generation"""
    print("\n🧪 Test 2: Signature generation")

    # Create forwarder
    http_client = AsyncMock(spec=httpx.AsyncClient)
    forwarder = WebhookForwarder(http_client)

    # Test payload and secret
    payload = '{"event": "message.received", "message": "test"}'
    secret = "my_webhook_secret"

    # Generate signature
    signature_header = forwarder._generate_signature(payload, secret)

    # Verify format
    assert signature_header.startswith("sha256="), "Signature should start with sha256="

    # Extract signature
    signature = signature_header[7:]  # Remove "sha256=" prefix

    # Manually compute expected signature
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    assert signature == expected_signature, "Signature should match expected value"

    print(f"✅ Signature generation test passed")
    print(f"   Generated: {signature_header}")
    return True


async def test_webhook_delivery():
    """Test webhook HTTP delivery"""
    print("\n🧪 Test 3: Webhook delivery")

    # Create test message
    message = Message(
        id="test_msg_456",
        sender_id="9876543210",
        recipient_id="1234567890",
        message_text="Test message",
        direction="inbound",
        timestamp=datetime.now(timezone.utc)
    )

    # Create test account
    account = Account(
        id="acc_test456",
        instagram_account_id="1234567890",
        username="test_business",
        access_token_encrypted="dummy",
        crm_webhook_url="https://crm.example.com/webhook",
        webhook_secret="test_secret_456"
    )

    # Create mock HTTP client
    mock_response = Mock()
    mock_response.status_code = 200

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.post = AsyncMock(return_value=mock_response)

    # Create forwarder and send webhook
    forwarder = WebhookForwarder(http_client)
    success = await forwarder.forward_message(message, account, "test_secret_456")

    # Verify HTTP client was called
    assert http_client.post.called, "HTTP client should be called"
    call_args = http_client.post.call_args

    # Verify URL
    assert call_args.kwargs["url"] == "https://crm.example.com/webhook", "URL should match"

    # Verify headers
    headers = call_args.kwargs["headers"]
    assert "X-Hub-Signature-256" in headers, "Should include signature header"
    assert headers["X-Hub-Signature-256"].startswith("sha256="), "Signature format should be correct"
    assert headers["Content-Type"] == "application/json", "Content-Type should be JSON"

    # Verify payload
    payload = call_args.kwargs["json"]
    assert payload["event"] == "message.received", "Event should be message.received"
    assert payload["message_id"] == "test_msg_456", "Message ID should match"

    # Verify success
    assert success is True, "Should return success for 2xx status"

    print("✅ Webhook delivery test passed")
    return True


async def test_webhook_failure():
    """Test webhook delivery failure handling"""
    print("\n🧪 Test 4: Webhook failure handling")

    # Create test message and account
    message = Message(
        id="test_msg_789",
        sender_id="1111111111",
        recipient_id="2222222222",
        message_text="Test message",
        direction="inbound",
        timestamp=datetime.now(timezone.utc)
    )

    account = Account(
        id="acc_test789",
        instagram_account_id="2222222222",
        username="test_business",
        access_token_encrypted="dummy",
        crm_webhook_url="https://crm.example.com/webhook",
        webhook_secret="test_secret_789"
    )

    # Test 4xx error
    mock_response = Mock()
    mock_response.status_code = 400

    http_client = AsyncMock(spec=httpx.AsyncClient)
    http_client.post = AsyncMock(return_value=mock_response)

    forwarder = WebhookForwarder(http_client)
    success = await forwarder.forward_message(message, account, "test_secret_789")

    assert success is False, "Should return False for 4xx status"

    # Test network timeout
    http_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
    success = await forwarder.forward_message(message, account, "test_secret_789")

    assert success is False, "Should return False for timeout"

    print("✅ Webhook failure handling test passed")
    return True


async def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Webhook Forwarder Implementation (Task 9)")
    print("=" * 60)

    tests = [
        test_payload_construction,
        test_signature_generation,
        test_webhook_delivery,
        test_webhook_failure
    ]

    results = []
    for test in tests:
        try:
            result = await test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    print("\n" + "=" * 60)
    print(f"Test Results: {sum(results)}/{len(results)} passed")
    print("=" * 60)

    if all(results):
        print("\n🎉 All tests passed! Task 9 implementation is working correctly.")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the implementation.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
