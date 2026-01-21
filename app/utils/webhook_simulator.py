"""
Webhook Simulator Utility

Generates valid Instagram webhook payloads with proper HMAC-SHA256 signatures
for testing webhook processing locally without real Instagram messages.
"""

import hmac
import hashlib
import json
import time
import uuid
from typing import Optional


class WebhookSimulator:
    """
    Generate Instagram webhook payloads for local testing.

    Usage:
        simulator = WebhookSimulator(app_secret="your_instagram_app_secret")
        payload_bytes, signature = simulator.generate_message_webhook(
            sender_id="123456789",
            recipient_id="987654321",
            message_text="Hello!",
            messaging_channel_id="17841478096518771"
        )

        # Send to webhook endpoint
        response = httpx.post(
            "http://localhost:8000/webhooks/instagram",
            content=payload_bytes,
            headers={"X-Hub-Signature-256": signature}
        )
    """

    def __init__(self, app_secret: str):
        """
        Initialize with Instagram app secret for signature generation.

        Args:
            app_secret: INSTAGRAM_APP_SECRET from your .env file
        """
        self.app_secret = app_secret

    def generate_message_webhook(
        self,
        sender_id: str,
        recipient_id: str,
        message_text: Optional[str] = None,
        messaging_channel_id: Optional[str] = None,
        attachments: Optional[list[dict]] = None,
        timestamp_ms: Optional[int] = None,
        message_id: Optional[str] = None
    ) -> tuple[bytes, str]:
        """
        Generate a valid Instagram message webhook payload with signature.

        Args:
            sender_id: Instagram user ID of the sender (customer)
            recipient_id: Instagram business account ID (recipient of message)
            message_text: Text content of the message (optional for media-only)
            messaging_channel_id: Channel ID for routing (defaults to recipient_id)
            attachments: List of attachment dicts with "type" and "url" keys
            timestamp_ms: Timestamp in milliseconds (defaults to current time)
            message_id: Message ID (defaults to generated mid_*)

        Returns:
            Tuple of (payload_bytes, signature_header)
            - payload_bytes: JSON payload as bytes
            - signature_header: "sha256=<hex_signature>" for X-Hub-Signature-256 header
        """
        # Generate defaults
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)

        if message_id is None:
            message_id = f"mid_{uuid.uuid4().hex[:16]}"

        if messaging_channel_id is None:
            messaging_channel_id = recipient_id

        # Build message object
        message_obj = {
            "mid": message_id
        }

        if message_text:
            message_obj["text"] = message_text

        if attachments:
            message_obj["attachments"] = [
                {
                    "type": att["type"],
                    "payload": {"url": att["url"]}
                }
                for att in attachments
            ]

        # Build webhook payload (matches Instagram's format exactly)
        payload = {
            "object": "instagram",
            "entry": [
                {
                    "id": messaging_channel_id,
                    "time": timestamp_ms // 1000,  # entry.time is in seconds
                    "messaging": [
                        {
                            "sender": {"id": sender_id},
                            "recipient": {"id": recipient_id},
                            "timestamp": timestamp_ms,
                            "message": message_obj
                        }
                    ]
                }
            ]
        }

        # Convert to bytes for signature
        payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')

        # Generate HMAC-SHA256 signature
        signature = hmac.new(
            self.app_secret.encode('utf-8'),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        signature_header = f"sha256={signature}"

        return payload_bytes, signature_header

    def pretty_print_payload(self, payload_bytes: bytes) -> str:
        """
        Pretty print a webhook payload for debugging.

        Args:
            payload_bytes: JSON payload as bytes

        Returns:
            Formatted JSON string
        """
        return json.dumps(json.loads(payload_bytes), indent=2)
