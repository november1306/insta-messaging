"""
Webhook forwarding service for CRM integration.

Forwards incoming Instagram messages to configured CRM webhook endpoints.
Implements HMAC-SHA256 signature generation for webhook security.
"""
import hmac
import hashlib
import json
import logging
from typing import Optional
from datetime import datetime

import httpx

from app.config import settings
from app.core.interfaces import Message
from app.db.models import Account


logger = logging.getLogger(__name__)


class WebhookForwarder:
    """
    Service for forwarding Instagram messages to CRM webhooks.

    Responsibilities:
    - Construct InboundMessageWebhook payload (per OpenAPI spec)
    - Generate HMAC-SHA256 signature for webhook security
    - Send POST request to CRM webhook URL
    - Log success/failure (no retries in MVP - that's Priority 3)

    Usage:
        forwarder = WebhookForwarder(http_client)
        success = await forwarder.forward_message(message, account)
    """

    def __init__(self, http_client: httpx.AsyncClient):
        """
        Initialize webhook forwarder.

        Args:
            http_client: Async HTTP client for making webhook requests
        """
        self.http_client = http_client

    async def forward_message(
        self,
        message: Message,
        account: Account,
        webhook_secret: str
    ) -> bool:
        """
        Forward an inbound Instagram message to the CRM webhook.

        Args:
            message: The inbound message to forward
            account: Account configuration with webhook URL
            webhook_secret: Decrypted webhook secret for signature generation

        Returns:
            True if webhook sent successfully, False otherwise

        Note:
            This is MVP implementation - no retries, no queuing.
            Failed deliveries are logged but not retried.
            Retry logic will be added in Priority 3 (Task 17).
        """
        try:
            # Construct webhook payload (per OpenAPI InboundMessageWebhook schema)
            payload = self._build_payload(message, account)
            payload_json = json.dumps(payload)

            # Generate HMAC-SHA256 signature (same approach as Instagram uses)
            signature_header = self._generate_signature(payload_json, webhook_secret)

            # Log webhook attempt (never log message content or secrets)
            logger.info(
                f"📤 Forwarding message to CRM webhook - "
                f"message_id: {message.id}, account: {account.id}"
            )

            # Send POST request to CRM webhook
            response = await self.http_client.post(
                url=account.crm_webhook_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": signature_header,
                    "User-Agent": "Instagram-Message-Router/1.0"
                },
                timeout=settings.crm_webhook_timeout  # Configurable timeout (default: 10s)
            )

            # Check response status
            if 200 <= response.status_code < 300:
                logger.info(
                    f"✅ Webhook delivered successfully - "
                    f"message_id: {message.id}, status: {response.status_code}"
                )
                return True
            else:
                logger.warning(
                    f"⚠️ CRM webhook returned non-2xx status - "
                    f"message_id: {message.id}, status: {response.status_code}"
                )
                return False

        except httpx.TimeoutException:
            logger.warning(
                f"⚠️ CRM webhook timeout - "
                f"message_id: {message.id}, url: {account.crm_webhook_url}"
            )
            return False

        except httpx.RequestError as e:
            logger.warning(
                f"⚠️ Failed to send webhook - "
                f"message_id: {message.id}, error: {e}"
            )
            return False

        except Exception as e:
            logger.error(
                f"❌ Unexpected error forwarding webhook - "
                f"message_id: {message.id}, error: {e}",
                exc_info=True
            )
            return False

    def _build_payload(self, message: Message, account: Account) -> dict:
        """
        Build InboundMessageWebhook payload per OpenAPI spec.

        Args:
            message: The inbound message
            account: Account configuration

        Returns:
            Dictionary matching InboundMessageWebhook schema

        Schema reference:
            openapi.yaml lines 515-557
        """
        # Construct conversation_id from sender/recipient
        # Format: conv_{sender}_{recipient} for consistent conversation grouping
        conversation_id = f"conv_{message.sender_id}_{message.recipient_id}"

        # Build payload matching OpenAPI spec
        payload = {
            "event": "message.received",
            "message_id": message.id,  # Instagram message ID
            "account_id": account.id,  # Our internal account ID
            "sender_id": message.sender_id,  # Instagram PSID
            "sender_username": None,  # Optional - skip in MVP (would require API call)
            "message": message.message_text,
            "message_type": "text",  # MVP only handles text messages
            "timestamp": message.timestamp.isoformat(),  # ISO 8601 format
            "instagram_message_id": message.id,  # Same as message_id for now
            "conversation_id": conversation_id
        }

        return payload

    def _generate_signature(self, payload: str, secret: str) -> str:
        """
        Generate HMAC-SHA256 signature for webhook payload.

        Uses same approach as Instagram/Facebook webhooks:
        - HMAC-SHA256 with shared secret
        - Returns "sha256={hex_digest}" format

        Args:
            payload: JSON string of webhook payload
            secret: Shared webhook secret (decrypted)

        Returns:
            Signature header value in format "sha256={signature}"

        Security:
            - CRM can verify webhooks are from us by computing same signature
            - Uses cryptographically secure HMAC
            - Constant-time comparison should be used on CRM side
        """
        signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        return f"sha256={signature}"
