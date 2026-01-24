"""Instagram webhook endpoints - Refactored to use Domain-Driven Design"""
from fastapi import APIRouter, Request, Query, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.db.connection import get_db_session
from app.db.models import Account
from app.domain.unit_of_work import SQLAlchemyUnitOfWork
from app.application.message_service import MessageService
from app.domain.value_objects import MessagingChannelId, InstagramUserId, AccountId
from app.clients import InstagramClient
from app.services.media_downloader import MediaDownloader
from app.clients.instagram_client import InstagramAPIError
from app.rules.reply_rules import get_reply_text
from app.services.webhook_forwarder import WebhookForwarder
from app.services.encryption_service import decrypt_credential
from app.api.events import broadcast_new_message
from datetime import datetime, timezone
import asyncio
import logging
import httpx
import hmac
import hashlib
import json

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/instagram",
    summary="Instagram webhook verification (setup)",
    responses={
        200: {
            "description": "Verification successful - webhook configured correctly",
            "content": {"text/plain": {"example": "1234567890"}}
        },
        403: {
            "description": "Verification failed - token mismatch",
            "content": {"application/json": {"example": {"detail": "Verification token mismatch"}}}
        }
    }
)
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge")
):
    """
    Instagram webhook verification endpoint.

    Instagram sends a GET request to this endpoint during webhook setup to verify
    that your server is configured correctly and ready to receive webhook events.

    ## Setup Instructions

    1. **Go to Instagram Developer Console**:
       - Navigate to your app → Products → Webhooks
       - Click "Add Subscription"

    2. **Configure Webhook**:
       - Callback URL: `https://your-domain.com/webhooks/instagram`
       - Verify Token: Set in your `.env` as `FACEBOOK_VERIFY_TOKEN`
       - Subscription Fields: `messages`, `messaging_postbacks`

    3. **Test Verification**:
       - Click "Verify and Save"
       - Instagram will call this endpoint with GET request
       - Should return 200 OK with challenge value

    ## How It Works

    Instagram sends:
    ```
    GET /webhooks/instagram?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=1234567890
    ```

    We validate `hub.verify_token` matches `FACEBOOK_VERIFY_TOKEN` and return `hub.challenge`.

    ## Troubleshooting

    **Error: "Verification token mismatch"**
    - Check `FACEBOOK_VERIFY_TOKEN` in `.env` matches webhook config
    - Token is case-sensitive

    **Error: "URL couldn't be validated"**
    - Ensure URL is publicly accessible (not localhost)
    - Use ngrok for local testing: `ngrok http 8000`
    - Check HTTPS certificate is valid

    **Security Note**:
    This endpoint does NOT validate Instagram's signature (signature validation is only
    required for POST requests, not GET verification).
    """
    logger.info(f"Webhook verification request received - mode: {hub_mode}")
    
    # Verify the token matches our configured token
    if hub_mode == "subscribe" and hub_verify_token == settings.facebook_verify_token:
        logger.info("✅ Webhook verification successful")
        # Return the challenge to complete verification
        # Facebook expects the challenge as plain text (string or int)
        try:
            return int(hub_challenge)
        except ValueError:
            return hub_challenge
    else:
        logger.warning(f"❌ Webhook verification failed - invalid token")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Verification token mismatch"
        )


@router.post(
    "/instagram",
    summary="Receive Instagram messages via webhook",
    responses={
        200: {
            "description": "Webhook processed successfully",
            "content": {
                "application/json": {
                    "example": {"status": "ok", "messages_processed": 3}
                }
            }
        },
        401: {
            "description": "Invalid webhook signature",
            "content": {
                "application/json": {
                    "example": {"detail": "Invalid signature"}
                }
            }
        }
    }
)
async def handle_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Receive Instagram messages via webhook.

    Instagram sends POST requests to this endpoint when:
    - Customer sends you a message
    - Customer sends you media (image, video, audio)
    - Customer reacts to your message
    - Delivery/read receipts are available (future)

    ## Security (HMAC-SHA256 Validation)

    Every webhook request is signed by Instagram using HMAC-SHA256:
    ```
    X-Hub-Signature-256: sha256=<computed-signature>
    ```

    We verify this signature using `INSTAGRAM_APP_SECRET` to ensure:
    - Request actually came from Instagram (not a malicious actor)
    - Payload wasn't tampered with during transmission

    ## Processing Flow

    1. **Validate Signature**: Compute HMAC-SHA256 of request body and compare
    2. **Parse Payload**: Extract message data from JSON body
    3. **Route to Account**: Use `messaging_channel_id` (from `entry.id`) to find account
    4. **Download Attachments**: Fetch media from Instagram CDN (7-day expiration)
    5. **Store Message**: Save to database with attachments
    6. **Broadcast to UI**: Send to connected frontend clients via SSE
    7. **Forward to CRM**: POST to CRM webhook URL (if configured)
    8. **Return 200 OK**: Always return success to prevent retries

    ## Webhook Payload Structure

    Instagram sends JSON like this:
    ```json
    {
      "object": "instagram",
      "entry": [
        {
          "id": "17841478096518771",  // messaging_channel_id (CRITICAL for routing!)
          "time": 1673024400,
          "messaging": [
            {
              "sender": {"id": "25964748486442669"},
              "recipient": {"id": "17841478096518771"},
              "timestamp": 1673024400000,
              "message": {
                "mid": "mid_abc123",
                "text": "Hello!",
                "attachments": [
                  {
                    "type": "image",
                    "payload": {"url": "https://scontent..."}
                  }
                ]
              }
            }
          ]
        }
      ]
    }
    ```

    ## Message Deduplication

    Instagram may retry webhook delivery if we don't respond with 200 OK within 20 seconds.
    We use `mid` (message ID) as unique constraint to prevent duplicate storage.

    ## Media Attachments (7-Day Expiration)

    Instagram CDN URLs expire after 7 days. We download media immediately and store locally:
    - **Location**: `media/inbound/{account_id}/{sender_id}/{filename}`
    - **Authenticated Access**: Media requires JWT token or API key
    - **Supported Types**: Images (JPEG, PNG), Videos (MP4, MOV), Audio (AAC, M4A)

    ## CRM Forwarding

    If `crm_webhook_url` is configured for the account, we forward messages to your CRM:
    ```
    POST {crm_webhook_url}
    X-Hub-Signature-256: sha256=<hmac-signature>
    Content-Type: application/json

    {message JSON payload}
    ```

    Your CRM should:
    - Validate HMAC signature using `webhook_secret` (from account config)
    - Return 200 OK within 20 seconds
    - Handle duplicate messages (we may retry on failure)

    ## Idempotency

    - Always returns 200 OK (even on processing errors) to prevent Instagram retries
    - Duplicate messages (same `mid`) are silently ignored
    - Failed attachments don't fail entire webhook (message stored without attachment)

    ## Testing with ngrok

    For local development:
    ```bash
    # Terminal 1: Start your app
    python -m uvicorn app.main:app --reload

    # Terminal 2: Start ngrok
    ngrok http 8000

    # Use ngrok URL in Instagram webhook config:
    # https://abc123.ngrok.io/webhooks/instagram
    ```

    ## Troubleshooting

    **Error: "Invalid signature"**
    - Check `INSTAGRAM_APP_SECRET` in `.env` matches Instagram app settings
    - Use Instagram app secret, NOT Facebook app secret
    - Ensure app secret hasn't been regenerated

    **Messages not appearing**:
    - Check webhook is subscribed to `messages` field
    - Verify `messaging_channel_id` is bound to account
    - Check logs for "No account configuration found"

    **Attachments not downloading**:
    - Instagram CDN URLs expire after 7 days
    - Webhook must process within 20 seconds (or Instagram retries)
    - Check `media/` directory has write permissions
    """
    # Get the raw request body for signature validation
    raw_body = await request.body()
    
    # Validate webhook signature before processing
    signature_header = request.headers.get("X-Hub-Signature-256", "")
    if not _validate_webhook_signature(raw_body, signature_header):
        logger.warning("❌ Invalid webhook signature - potential security threat")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid signature"
        )
    
    logger.info("✅ Webhook signature validated")

    messages_processed = 0

    try:
        # Parse the JSON body (json.loads handles bytes directly)
        body = json.loads(raw_body)

        # Validate request body structure
        if not isinstance(body, dict):
            logger.warning("Invalid webhook payload: not a dictionary")
            return {"status": "ok", "messages_processed": 0}

        if "entry" not in body:
            logger.warning("Invalid webhook payload: missing 'entry' field")
            return {"status": "ok", "messages_processed": 0}

        # Log only metadata, never log message content or personal data
        entry_count = len(body.get("entry", []))
        object_type = body.get("object", "unknown")

        logger.info(f"📨 Webhook POST request received - object: {object_type}, entries: {entry_count}")

        # Initialize MessageService (Instagram clients created per-account inside methods)
        message_service = MessageService()

        # Parse and store messages from webhook payload
        for entry in body.get("entry", []):
            # CRITICAL: Extract messaging_channel_id from entry.id (stable identifier for routing)
            # This is the ONLY reliable way to identify which account received this webhook
            # entry.id is NOT the same as OAuth profile ID - it's the messaging channel ID
            messaging_channel_id = entry.get("id")

            if messaging_channel_id:
                # Bind channel ID to account (idempotent - safe to call multiple times)
                await _bind_channel_id(db, messaging_channel_id)
            else:
                logger.warning("Webhook entry missing 'id' field - cannot route messages")
                continue
            # Log if entry has no messaging events (binding-only webhook)
            messaging_events = entry.get("messaging", [])
            if not messaging_events:
                logger.info(
                    f"📌 Webhook entry {messaging_channel_id} has no messaging events "
                    f"- channel ID bound but no messages to process (this is normal for verification webhooks)"
                )

            # Each entry can contain multiple messaging events
            for messaging_event in messaging_events:
                try:
                    # Extract message data
                    message_data = _extract_message_data(messaging_event)

                    if message_data:
                        # Add messaging_channel_id to message data for routing
                        message_data["messaging_channel_id"] = messaging_channel_id

                        # Download and process attachments (if any)
                        attachments_list = []
                        if "attachments" in message_data and message_data["attachments"]:
                            downloader = MediaDownloader()

                            for att_data in message_data["attachments"]:
                                try:
                                    # Download media from Instagram CDN (URL expires in 7 days)
                                    media_file = await downloader.download_media(
                                        instagram_url=att_data["media_url"],
                                        message_id=message_data["id"],
                                        attachment_index=att_data["index"],
                                        media_type=att_data["media_type"]
                                    )

                                    # Prepare attachment data for MessageService
                                    attachments_list.append({
                                        "type": att_data["media_type"],
                                        "url": att_data["media_url"],
                                        "local_path": media_file.local_path,
                                        "mime_type": media_file.mime_type
                                    })

                                except Exception as download_error:
                                    # Log error but continue - save message with URL only
                                    logger.error(
                                        f"❌ Failed to download attachment {att_data['index']} "
                                        f"for message {message_data['id']}: {download_error}"
                                    )
                                    # Create attachment with URL only (no local copy)
                                    attachments_list.append({
                                        "type": att_data["media_type"],
                                        "url": att_data["media_url"],
                                        "local_path": None,
                                        "mime_type": None
                                    })

                        # Save message using Unit of Work + MessageService
                        try:
                            # Create Unit of Work
                            async with SQLAlchemyUnitOfWork(db) as uow:
                                # Save message via MessageService
                                saved_message = await message_service.receive_webhook_message(
                                    uow=uow,
                                    messaging_channel_id=MessagingChannelId(messaging_channel_id),
                                    instagram_message_id=message_data["id"],
                                    sender_id=message_data["sender_id"],
                                    recipient_id=messaging_channel_id,  # Use messaging_channel_id for routing
                                    message_text=message_data["text"],
                                    timestamp=message_data["timestamp"],
                                    attachments=attachments_list if attachments_list else None
                                )

                                # Get account for SSE broadcast and auto-reply
                                account = await uow.accounts.get_by_messaging_channel_id(messaging_channel_id)

                                # Schedule SSE broadcast as post-commit hook
                                async def broadcast_sse():
                                    try:
                                        # Build attachments data for frontend
                                        attachments_data = []
                                        if saved_message.attachments:
                                            for att in saved_message.attachments:
                                                attachments_data.append({
                                                    "id": att.id.value,
                                                    "index": att.attachment_index,
                                                    "media_type": att.media_type,
                                                    "media_url": att.media_url,
                                                    "media_url_local": att.media_url_local,
                                                    "media_mime_type": att.media_mime_type
                                                })

                                        # Get sender profile (username and profile picture) from cache or Instagram API
                                        from app.db.models import InstagramProfile
                                        from datetime import timedelta

                                        sender_username = saved_message.sender_id.value
                                        profile_picture_url = None

                                        # Check cache first (within same database session)
                                        cached_profile = await db.execute(
                                            select(InstagramProfile).where(
                                                InstagramProfile.sender_id == saved_message.sender_id.value
                                            )
                                        )
                                        cached_profile = cached_profile.scalar_one_or_none()

                                        # Use cached profile if fresh (< 24 hours old)
                                        if cached_profile and (datetime.now(timezone.utc) - cached_profile.last_updated.replace(tzinfo=timezone.utc)) < timedelta(hours=24):
                                            sender_username = f"@{cached_profile.username}" if cached_profile.username else saved_message.sender_id.value
                                            profile_picture_url = cached_profile.profile_picture_url
                                            logger.debug(f"Using cached profile for sender {saved_message.sender_id.value}")
                                        else:
                                            # Fetch from Instagram API and update cache
                                            if account and account.access_token_encrypted:
                                                try:
                                                    access_token = decrypt_credential(account.access_token_encrypted, settings.session_secret)

                                                    async with httpx.AsyncClient() as http_client:
                                                        instagram_client = InstagramClient(
                                                            http_client=http_client,
                                                            access_token=access_token,
                                                            logger_instance=logger
                                                        )
                                                        profile = await instagram_client.get_user_profile(saved_message.sender_id.value)

                                                        if profile:
                                                            username = profile.get('username', '')
                                                            sender_username = f"@{username}" if username else saved_message.sender_id.value
                                                            # Extract profile_pic from API response and store as profile_picture_url
                                                            # Note: Field name is 'profile_pic' for ISGIDs, 'profile_picture_url' for business accounts
                                                            profile_picture_url = profile.get('profile_pic') or profile.get('profile_picture_url')

                                                            # Update or create cache entry
                                                            if cached_profile:
                                                                cached_profile.username = username
                                                                cached_profile.profile_picture_url = profile_picture_url
                                                                cached_profile.last_updated = datetime.now(timezone.utc)
                                                            else:
                                                                new_profile = InstagramProfile(
                                                                    sender_id=saved_message.sender_id.value,
                                                                    username=username,
                                                                    profile_picture_url=profile_picture_url,
                                                                    last_updated=datetime.now(timezone.utc)
                                                                )
                                                                db.add(new_profile)

                                                            await db.commit()
                                                            logger.debug(f"Cached profile for sender {saved_message.sender_id.value}")
                                                except Exception as profile_error:
                                                    logger.warning(f"Failed to fetch sender profile for SSE: {profile_error}")

                                        await broadcast_new_message({
                                            "id": saved_message.id.value,
                                            "sender_id": saved_message.sender_id.value,
                                            "sender_name": sender_username,
                                            "profile_picture_url": profile_picture_url,
                                            "text": saved_message.message_text,
                                            "direction": "inbound",
                                            "timestamp": saved_message.timestamp.isoformat() if saved_message.timestamp else None,
                                            "messaging_channel_id": saved_message.recipient_id.value,
                                            "account_id": saved_message.account_id.value if saved_message.account_id else None,
                                            "attachments": attachments_data
                                        })
                                    except Exception as sse_error:
                                        logger.error(f"Failed to broadcast SSE message: {sse_error}")

                                uow.add_post_commit_hook(broadcast_sse)

                                # Commit transaction (triggers post-commit hooks)
                                await uow.commit()

                            messages_processed += 1
                            attachment_summary = f" with {saved_message.attachment_count} attachment(s)" if saved_message.attachment_count > 0 else ""
                            logger.info(f"✅ Stored message {saved_message.id.value} from {saved_message.sender_id.value}{attachment_summary}")

                            # Handle auto-reply ONLY for newly saved messages
                            if account:
                                try:
                                    # Create new UoW for auto-reply (separate transaction)
                                    async with SQLAlchemyUnitOfWork(db) as auto_reply_uow:
                                        # Check if message should trigger a reply
                                        reply_text = get_reply_text(saved_message.message_text)

                                        if reply_text:
                                            # Prepare Instagram client with account token
                                            access_token = decrypt_credential(account.access_token_encrypted, settings.session_secret) if account.access_token_encrypted else None

                                            if access_token:
                                                async with httpx.AsyncClient() as http_client:
                                                    instagram_client = InstagramClient(
                                                        http_client=http_client,
                                                        access_token=access_token,
                                                        settings=settings,
                                                        logger_instance=logger
                                                    )

                                                    # Set Instagram client for MessageService
                                                    message_service._instagram_client = instagram_client

                                                    # Send auto-reply
                                                    await message_service.auto_reply_to_message(
                                                        uow=auto_reply_uow,
                                                        inbound_message=saved_message,
                                                        reply_text=reply_text
                                                    )

                                                    await auto_reply_uow.commit()
                                except Exception as auto_reply_error:
                                    logger.error(f"⚠️ Auto-reply failed: {auto_reply_error}", exc_info=True)

                            # Forward to CRM webhook (fire-and-forget)
                            asyncio.create_task(_forward_to_crm_domain(saved_message, messaging_channel_id))

                        except Exception as save_error:
                            # DuplicateMessageError or other errors
                            from app.domain.entities import DuplicateMessageError
                            if isinstance(save_error, DuplicateMessageError):
                                logger.info(f"ℹ️ Message {message_data['id']} already exists (webhook retry)")
                            else:
                                logger.error(f"Failed to save message {message_data['id']}: {save_error}", exc_info=True)
                            continue
                    else:
                        # Non-text message or unsupported event type
                        # Log the event type to help debug what we're skipping
                        event_type = "unknown"
                        if "message" in messaging_event:
                            event_type = "message (failed extraction)"
                        elif "delivery" in messaging_event:
                            event_type = "delivery_receipt"
                        elif "read" in messaging_event:
                            event_type = "read_receipt"
                        elif "echo" in messaging_event:
                            event_type = "echo"
                        elif "reaction" in messaging_event:
                            event_type = "reaction"

                        logger.info(
                            f"ℹ️ Skipped event type: {event_type} "
                            f"(channel_id: {messaging_channel_id}, keys: {list(messaging_event.keys())})"
                        )
                
                except Exception as msg_error:
                    # Log error but continue processing other messages
                    logger.error(f"Error processing individual message: {msg_error}", exc_info=True)
                    continue

        logger.info(f"✅ Processed {messages_processed} messages from webhook")

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        # Transaction will be rolled back by get_db_session() on exception
        messages_processed = 0  # Reset count since transaction rolled back
    
    # Always return 200 to acknowledge receipt and prevent Facebook retries
    return {"status": "ok", "messages_processed": messages_processed}




def _validate_webhook_signature(payload: bytes, signature_header: str) -> bool:
    """
    Validate the webhook signature from Facebook.
    
    Facebook signs all webhook requests with HMAC-SHA256 using the app secret.
    The signature is sent in the X-Hub-Signature-256 header as "sha256=<signature>".
    
    Args:
        payload: Raw request body as bytes
        signature_header: Value of X-Hub-Signature-256 header
        
    Returns:
        True if signature is valid, False otherwise
        
    Security:
        - Uses constant-time comparison to prevent timing attacks
        - Validates signature format before comparison
        - Logs security events for monitoring
    """
    try:
        # Extract signature or use invalid placeholder to prevent timing attacks
        if not signature_header or not signature_header.startswith("sha256="):
            logger.warning("Missing or malformed signature header")
            expected_signature = "invalid"  # Will fail compare_digest below
        else:
            expected_signature = signature_header[7:]  # len("sha256=") = 7
        
        # Validate Instagram app secret is configured
        from app.config import DEV_SECRET_PLACEHOLDER
        
        if not settings.instagram_app_secret:
            logger.error("INSTAGRAM_APP_SECRET not configured - cannot validate webhook signature")
            return False
        
        # Development mode: Allow test secret for local ngrok testing
        # The signature will fail with real Instagram webhooks, but this enables
        # testing the webhook flow locally before getting real credentials
        if settings.instagram_app_secret == DEV_SECRET_PLACEHOLDER:
            if settings.environment == "production":
                # This should never happen due to config.py validation, but double-check
                logger.error("Cannot use test secret in production - webhook validation will fail")
                return False
            logger.warning(
                "⚠️  Using test secret for webhook validation. "
                "This will fail with real Instagram webhooks. "
                "Set INSTAGRAM_APP_SECRET to your real Instagram app secret."
            )
        
        # Always compute HMAC-SHA256 signature to prevent timing attacks
        # Use Instagram app secret for Instagram webhooks
        app_secret = settings.instagram_app_secret.encode('utf-8')
        computed_signature = hmac.new(
            app_secret,
            payload,
            hashlib.sha256
        ).hexdigest()
        
        # Use constant-time comparison to prevent timing attacks
        is_valid = hmac.compare_digest(computed_signature, expected_signature)
        
        if is_valid:
            logger.debug("✅ Webhook signature validated")
        else:
            logger.warning("❌ Invalid webhook signature")
        
        return is_valid
        
    except Exception as e:
        logger.error(f"Signature validation error: {e}", exc_info=True)
        return False


def _extract_message_data(messaging_event: dict) -> dict | None:
    """
    Extract message data from a messaging event (text and/or media attachments).

    Args:
        messaging_event: A single messaging event from the webhook payload

    Returns:
        Dictionary with message data (text and/or attachments), None if invalid
    """
    try:
        # Check if this is a message event (not delivery, read, etc.)
        if "message" not in messaging_event:
            return None

        message = messaging_event["message"]

        # Skip echo messages (messages we sent that Instagram echoes back)
        # Instagram sends these with is_echo: true to confirm delivery
        if message.get("is_echo"):
            logger.info(f"ℹ️ Skipping echo message (outbound confirmation): mid={message.get('mid')}, sender={messaging_event.get('sender', {}).get('id')}")
            return None

        text = message.get("text")
        attachments = message.get("attachments", [])

        # If message has no text and no parseable attachments, log it but don't skip
        # Instagram sent this webhook for a reason - show the user something was received
        if not text and not attachments:
            # Log the full message to debug what Instagram is sending
            logger.warning(f"Message with no text or attachments - logging raw data. Full message: {message}")
            # Use placeholder text so the message appears in the UI
            text = "[Unsupported attachment or message type]"

        # Extract required fields
        sender_id = messaging_event.get("sender", {}).get("id")
        recipient_id = messaging_event.get("recipient", {}).get("id")
        message_id = message.get("mid")
        timestamp_ms = messaging_event.get("timestamp")

        # Validate required fields (text is now optional)
        if not all([sender_id, recipient_id, message_id, timestamp_ms]):
            missing = []
            if not sender_id: missing.append("sender_id")
            if not recipient_id: missing.append("recipient_id")
            if not message_id: missing.append("message_id (mid)")
            if not timestamp_ms: missing.append("timestamp")
            logger.warning(f"⚠️ Missing required fields in message event: {missing}. Keys present: {list(messaging_event.keys())}, message keys: {list(message.keys())}")
            return None

        # Convert timestamp from milliseconds to datetime (UTC timezone-aware)
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)

        # Build message data
        message_data = {
            "id": message_id,
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "text": text,  # Can be None for media-only messages
            "timestamp": timestamp
        }

        # Extract attachments data if present
        if attachments:
            message_data["attachments"] = []
            for idx, attachment in enumerate(attachments):
                media_type = attachment.get("type")  # "image", "video", "audio", "file", "like_heart"
                media_url = attachment.get("payload", {}).get("url")

                if media_type and media_url:
                    message_data["attachments"].append({
                        "index": idx,
                        "media_type": media_type,
                        "media_url": media_url
                    })
                else:
                    # Log full attachment structure to debug unsupported file types
                    logger.warning(f"Invalid attachment at index {idx}: missing type or URL. Full attachment: {attachment}")

            if message_data["attachments"]:
                logger.info(f"Message has {len(message_data['attachments'])} attachment(s)")
            else:
                # Instagram sent attachments but we couldn't parse any of them
                # Add placeholder text if there's no existing text
                if not message_data["text"]:
                    message_data["text"] = "[Unsupported file type]"
                    logger.warning(f"Could not parse any attachments from message {message_data['id']}")

        return message_data

    except Exception as e:
        logger.error(f"Error extracting message data: {e}", exc_info=True)
        return None


async def _bind_channel_id(db: AsyncSession, messaging_channel_id: str) -> None:
    """
    Bind messaging_channel_id to an account.

    This function is called for EVERY webhook entry to capture the stable
    messaging channel ID (entry.id) and associate it with an account.

    The channel ID is the ONLY reliable way to route messages when multiple
    accounts are authorized. It comes from webhook entry.id, NOT from OAuth.

    Args:
        db: Database session
        messaging_channel_id: The entry.id from webhook (messaging channel identifier)

    Note:
        - Idempotent: Safe to call multiple times with same channel_id
        - If channel_id already bound, does nothing
        - If not bound, tries to bind to first account without a channel_id
        - Logs warning if cannot bind (no available accounts)
    """
    try:
        # Check if this channel ID is already bound to an account
        result = await db.execute(
            select(Account).where(Account.messaging_channel_id == messaging_channel_id)
        )
        existing_account = result.scalar_one_or_none()

        if existing_account:
            # Already bound - nothing to do
            logger.debug(f"Channel ID {messaging_channel_id} already bound to account {existing_account.id}")
            return

        # Channel ID not bound - try to bind to an account without a channel ID
        # Prefer accounts that match this channel ID as their instagram_account_id
        # (in case OAuth profile ID == messaging channel ID, though this is rare)
        result = await db.execute(
            select(Account).where(
                Account.instagram_account_id == messaging_channel_id
            )
        )
        matching_account = result.scalar_one_or_none()

        if matching_account and not matching_account.messaging_channel_id:
            # Bind to matching account
            matching_account.messaging_channel_id = messaging_channel_id
            await db.commit()
            logger.info(
                f"✅ Bound channel ID {messaging_channel_id} to account {matching_account.id} "
                f"(@{matching_account.username}) - matched by instagram_account_id"
            )
            return

        # No matching account - bind to first account without a channel ID
        result = await db.execute(
            select(Account).where(Account.messaging_channel_id.is_(None))
        )
        available_account = result.scalars().first()

        if available_account:
            # Bind to first available account
            available_account.messaging_channel_id = messaging_channel_id
            await db.commit()
            logger.info(
                f"✅ Bound channel ID {messaging_channel_id} to account {available_account.id} "
                f"(@{available_account.username}) - first available account"
            )
        else:
            logger.warning(
                f"⚠️ Cannot bind channel ID {messaging_channel_id} - no available accounts. "
                f"All accounts already have channel IDs or no accounts exist."
            )

    except Exception as e:
        # Log error but don't fail webhook processing
        logger.error(f"Error binding channel ID {messaging_channel_id}: {e}", exc_info=True)
        # Rollback failed transaction
        await db.rollback()


async def _forward_to_crm_domain(message, messaging_channel_id: str) -> None:
    """
    Forward inbound message to CRM webhook (Task 9).

    Adapted to work with domain Message entities from app.domain.entities.

    Looks up account configuration and forwards message to CRM webhook
    if configured. This enables the CRM chat window to receive customer messages.

    Creates its own database session and HTTP client to avoid race conditions
    when used as a fire-and-forget background task.

    Args:
        message: Domain Message entity (from app.domain.entities)
        messaging_channel_id: The stable messaging channel ID from webhook entry.id

    Note:
        - Errors are logged but don't fail the webhook handler
        - No retries in MVP (Priority 3, Task 17)
        - Instagram webhook always returns 200 regardless of CRM delivery
        - Safe to use with asyncio.create_task() - manages its own resources
    """
    # Import here to avoid circular dependency
    from app.db.connection import async_session_maker
    from app.core.interfaces import Message as LegacyMessage

    try:
        # Create our own database session (request-scoped session is not available in background task)
        async with async_session_maker() as db:
            # Look up account by messaging_channel_id (stable routing identifier)
            result = await db.execute(
                select(Account).where(Account.messaging_channel_id == messaging_channel_id)
            )
            account = result.scalar_one_or_none()

            if not account:
                logger.warning(
                    f"No account configuration found for messaging_channel_id {messaging_channel_id}, "
                    f"skipping CRM webhook forwarding - message will not reach CRM. "
                    f"This may happen if the account hasn't received a webhook yet to bind the channel ID."
                )
                return

            if not account.crm_webhook_url:
                logger.warning(
                    f"No CRM webhook URL configured for account {account.id}, "
                    f"skipping forwarding - message will not reach CRM"
                )
                return

            # Decrypt webhook secret (Fernet AES-128 encryption)
            try:
                webhook_secret = decrypt_credential(account.webhook_secret, settings.session_secret)
            except Exception as decode_error:
                logger.error(
                    f"❌ Failed to decrypt webhook secret for account {account.id}: {decode_error}. "
                    f"Webhook secret may be corrupted in database.",
                    exc_info=True
                )
                return

            # Convert domain Message to legacy Message format for WebhookForwarder
            # WebhookForwarder expects the old interface, will be updated in future iteration
            legacy_message = LegacyMessage(
                id=message.id.value,
                sender_id=message.sender_id.value,
                recipient_id=message.recipient_id.value,
                message_text=message.message_text,
                direction=message.direction,
                timestamp=message.timestamp
            )

            # Create our own HTTP client (request-scoped client is not available in background task)
            async with httpx.AsyncClient() as http_client:
                # Forward message to CRM webhook
                forwarder = WebhookForwarder(http_client)
                success = await forwarder.forward_message(legacy_message, account, webhook_secret)

                if success:
                    logger.info(
                        f"✅ Message forwarded to CRM - "
                        f"message_id: {message.id.value}, account: {account.id}"
                    )
                else:
                    logger.warning(
                        f"⚠️ Failed to forward message to CRM - "
                        f"message_id: {message.id.value}, account: {account.id}"
                    )

    except Exception as e:
        # Log error but don't fail webhook processing
        # Instagram webhook should always return 200
        logger.error(
            f"❌ Error forwarding message to CRM - "
            f"message_id: {message.id.value if hasattr(message.id, 'value') else message.id}, error: {e}",
            exc_info=True
        )


# ============================================================================
# Note: Send message API moved to /api/v1/messages/send (OAuth-based)
# Legacy /webhooks/send endpoint removed - use multi-account OAuth system
# ============================================================================
