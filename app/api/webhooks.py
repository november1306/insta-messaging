"""Instagram webhook endpoints"""
from fastapi import APIRouter, Request, Query, HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.config import settings
from app.db.connection import get_db_session
from app.db.models import Account
from app.repositories.message_repository import MessageRepository
from app.core.interfaces import Message, Attachment
from app.clients import InstagramClient
from app.services.media_downloader import MediaDownloader
from app.clients.instagram_client import InstagramAPIError
from app.rules.reply_rules import get_reply_text
from app.services.webhook_forwarder import WebhookForwarder
from app.api.accounts import decrypt_credential
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


@router.get("/instagram")
async def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge")
):
    """
    Webhook verification endpoint for Facebook/Instagram.
    
    Facebook sends a GET request with verification parameters.
    We validate the verify_token and return the challenge.
    
    Note: Facebook does not sign GET requests during webhook verification,
    only POST requests with actual webhook data are signed.
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


@router.post("/instagram")
async def handle_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Webhook endpoint for receiving Instagram messages.
    
    Facebook sends POST requests with message data.
    We parse the payload, extract messages, and store them in the database.
    
    Security: Validates X-Hub-Signature-256 header to ensure requests come from Facebook.
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

        # Initialize repository
        message_repo = MessageRepository(db, request.app.state.crm_pool)

        # Create HTTP client and Instagram client once for all auto-replies
        async with httpx.AsyncClient() as http_client:
            instagram_client = InstagramClient(
                http_client=http_client,
                settings=settings,
                logger_instance=logger
            )
            
            # Parse and store messages from webhook payload
            for entry in body.get("entry", []):
                # Each entry can contain multiple messaging events
                for messaging_event in entry.get("messaging", []):
                    try:
                        # Extract message data
                        message_data = _extract_message_data(messaging_event)

                        if message_data:
                            # Create domain Message object
                            message = Message(
                                id=message_data["id"],
                                sender_id=message_data["sender_id"],
                                recipient_id=message_data["recipient_id"],
                                message_text=message_data["text"],
                                direction="inbound",  # Webhooks only receive inbound messages
                                timestamp=message_data["timestamp"],
                                attachments=[]  # Will populate if media present
                            )

                            # Download and process attachments (if any)
                            if "attachments" in message_data and message_data["attachments"]:
                                downloader = MediaDownloader()

                                for att_data in message_data["attachments"]:
                                    try:
                                        # Download media from Instagram CDN (URL expires in 7 days)
                                        media_file = await downloader.download_media(
                                            instagram_url=att_data["media_url"],
                                            message_id=message.id,
                                            attachment_index=att_data["index"],
                                            account_id=message.recipient_id,  # Instagram business account ID
                                            sender_id=message.sender_id,
                                            media_type=att_data["media_type"]
                                        )

                                        # Create Attachment domain object
                                        attachment = Attachment(
                                            id=f"{message.id}_{att_data['index']}",
                                            message_id=message.id,
                                            attachment_index=att_data["index"],
                                            media_type=att_data["media_type"],
                                            media_url=att_data["media_url"],
                                            media_url_local=media_file.local_path,
                                            media_mime_type=media_file.mime_type
                                        )
                                        message.attachments.append(attachment)

                                    except Exception as download_error:
                                        # Log error but continue - save message with URL only
                                        logger.error(
                                            f"❌ Failed to download attachment {att_data['index']} "
                                            f"for message {message.id}: {download_error}"
                                        )
                                        # Create attachment with URL only (no local copy)
                                        attachment = Attachment(
                                            id=f"{message.id}_{att_data['index']}",
                                            message_id=message.id,
                                            attachment_index=att_data["index"],
                                            media_type=att_data["media_type"],
                                            media_url=att_data["media_url"],
                                            media_url_local=None,  # Download failed
                                            media_mime_type=None
                                        )
                                        message.attachments.append(attachment)

                            # Save to database (handle duplicates from webhook retries)
                            try:
                                await message_repo.save(message)
                                messages_processed += 1

                                attachment_summary = f" with {len(message.attachments)} attachment(s)" if message.attachments else ""
                                logger.info(f"✅ Stored message {message.id} from {message.sender_id}{attachment_summary}")

                                # Broadcast to SSE clients (real-time UI update)
                                try:
                                    # Build attachments data for frontend
                                    attachments_data = []
                                    if message.attachments:
                                        for att in message.attachments:
                                            attachments_data.append({
                                                "id": att.id,
                                                "index": att.attachment_index,
                                                "media_type": att.media_type,
                                                "media_url": att.media_url,
                                                "media_url_local": att.media_url_local,
                                                "media_mime_type": att.media_mime_type
                                            })

                                    await broadcast_new_message({
                                        "id": message.id,
                                        "sender_id": message.sender_id,
                                        "sender_name": message.sender_id,  # TODO: Fetch actual name
                                        "text": message.message_text,
                                        "direction": "inbound",
                                        "timestamp": message.timestamp.isoformat() if message.timestamp else None,
                                        "instagram_account_id": message.recipient_id,
                                        "attachments": attachments_data  # NEW: Array of attachments
                                    })
                                except Exception as sse_error:
                                    logger.error(f"Failed to broadcast SSE message: {sse_error}")

                                # Handle auto-reply ONLY for newly saved messages (not duplicates)
                                # Wrapped in try/except to ensure CRM forwarding happens even if auto-reply fails
                                try:
                                    # Reuse instagram_client for all messages in this webhook batch
                                    await _handle_auto_reply(message, message_repo, instagram_client)
                                except Exception as auto_reply_error:
                                    # Log error but continue to CRM forwarding
                                    logger.error(
                                        f"⚠️ Auto-reply failed for message {message.id}, "
                                        f"continuing with CRM forwarding: {auto_reply_error}",
                                        exc_info=True
                                    )

                                # Forward to CRM webhook (Task 9 - CRITICAL for CRM chat window)
                                # Fire-and-forget to avoid blocking Instagram webhook response
                                # _forward_to_crm creates its own DB session and HTTP client to avoid race conditions
                                asyncio.create_task(_forward_to_crm(message))

                            except ValueError:
                                # Message already exists - this is ok for webhook retries
                                # Rollback the failed transaction to clean up session state
                                await db.rollback()
                                # Skip auto-reply to prevent duplicate responses
                                logger.info(f"ℹ️ Message {message.id} already exists, skipping auto-reply")
                                continue
                            except Exception as save_error:
                                # Other database errors (connection issues, etc.)
                                logger.error(f"Failed to save message {message.id}: {save_error}", exc_info=True)
                                continue
                        else:
                            # Non-text message or unsupported event type
                            logger.info(f"ℹ️ Skipped non-text message or unsupported event")
                    
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


async def _handle_auto_reply(
    inbound_message: Message,
    message_repo: MessageRepository,
    instagram_client: InstagramClient
) -> None:
    """
    Handle auto-reply logic for inbound messages.
    
    Uses user-defined rules from app.rules.reply_rules to determine
    if and how to reply to messages.
    
    This function is called AFTER the inbound message is saved to avoid
    transaction rollback if reply fails.
    
    Args:
        inbound_message: The inbound message that was just received
        message_repo: Repository for storing outbound messages
        instagram_client: Instagram API client (reused to avoid creating multiple instances)
    """
    try:
        # Check if message should trigger a reply (without username first)
        reply_text = get_reply_text(inbound_message.message_text)
        
        if not reply_text:
            logger.info(f"No reply rule matched, skipping auto-reply")
            return
        
        # Only fetch username if reply contains {username} placeholder
        if "{username}" in reply_text:
            profile = await instagram_client.get_user_profile(inbound_message.sender_id)
            if profile and "username" in profile:
                username = profile["username"]
                logger.info(f"👤 Retrieved username: @{username}")
                # Replace placeholder with actual username
                reply_text = reply_text.replace("{username}", f"@{username}")
            else:
                # Fallback: remove placeholder if profile fetch failed
                reply_text = reply_text.replace("{username}", "")
        
        logger.info(f"📤 Sending auto-reply...")
        
        # Send message (sender becomes recipient for reply)
        response = await instagram_client.send_message(
            recipient_id=inbound_message.sender_id,
            message_text=reply_text
        )
        
        if response.success:
            # Create outbound message record
            outbound_message = Message(
                id=response.message_id,
                sender_id=inbound_message.recipient_id,  # Our page ID
                recipient_id=inbound_message.sender_id,  # Customer ID
                message_text=reply_text,
                direction="outbound",
                timestamp=datetime.now(timezone.utc)
            )
            
            # Store outbound message in database
            await message_repo.save(outbound_message)
            logger.info(f"✅ Auto-reply sent and stored: {response.message_id}")
        else:
            logger.error(f"❌ Failed to send auto-reply: {response.error_message}")
            
    except Exception as e:
        # Log error but don't fail the webhook processing
        # Inbound message is already saved, so webhook won't be retried
        logger.error(f"❌ Error in auto-reply handler: {e}", exc_info=True)


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
            logger.warning("Missing required fields in message event")
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


async def _forward_to_crm(message: Message) -> None:
    """
    Forward inbound message to CRM webhook (Task 9).

    Looks up account configuration and forwards message to CRM webhook
    if configured. This enables the CRM chat window to receive customer messages.

    Creates its own database session and HTTP client to avoid race conditions
    when used as a fire-and-forget background task.

    Args:
        message: The inbound message to forward

    Note:
        - Errors are logged but don't fail the webhook handler
        - No retries in MVP (Priority 3, Task 17)
        - Instagram webhook always returns 200 regardless of CRM delivery
        - Safe to use with asyncio.create_task() - manages its own resources
    """
    # Import here to avoid circular dependency
    from app.db.connection import async_session_maker

    try:
        # Create our own database session (request-scoped session is not available in background task)
        async with async_session_maker() as db:
            # Look up account by Instagram account ID (recipient is our business account)
            result = await db.execute(
                select(Account).where(Account.instagram_account_id == message.recipient_id)
            )
            account = result.scalar_one_or_none()

            if not account:
                logger.warning(
                    f"No account configuration found for {message.recipient_id}, "
                    f"skipping CRM webhook forwarding - message will not reach CRM"
                )
                return

            if not account.crm_webhook_url:
                logger.warning(
                    f"No CRM webhook URL configured for account {account.id}, "
                    f"skipping forwarding - message will not reach CRM"
                )
                return

            # Decode webhook secret (MVP: base64-encoded)
            try:
                webhook_secret = decrypt_credential(account.webhook_secret)
            except Exception as decode_error:
                logger.error(
                    f"❌ Failed to decode webhook secret for account {account.id}: {decode_error}. "
                    f"Webhook secret may be corrupted in database.",
                    exc_info=True
                )
                return

            # Create our own HTTP client (request-scoped client is not available in background task)
            async with httpx.AsyncClient() as http_client:
                # Forward message to CRM webhook
                forwarder = WebhookForwarder(http_client)
                success = await forwarder.forward_message(message, account, webhook_secret)

                if success:
                    logger.info(
                        f"✅ Message forwarded to CRM - "
                        f"message_id: {message.id}, account: {account.id}"
                    )
                else:
                    logger.warning(
                        f"⚠️ Failed to forward message to CRM - "
                        f"message_id: {message.id}, account: {account.id}"
                    )

    except Exception as e:
        # Log error but don't fail webhook processing
        # Instagram webhook should always return 200
        logger.error(
            f"❌ Error forwarding message to CRM - "
            f"message_id: {message.id}, error: {e}",
            exc_info=True
        )


# ============================================================================
# Send Message API Endpoint
# ============================================================================

class SendMessageRequest(BaseModel):
    """Request model for sending messages"""
    recipient_id: str
    message_text: str

class SendMessageResponse(BaseModel):
    """Response model for send message endpoint"""
    success: bool
    message_id: str | None = None
    error: str | None = None


@router.post("/send", response_model=SendMessageResponse)
async def send_message_api(
    send_request: SendMessageRequest,
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    """
    API endpoint to send a message from the business account to a user.

    Usage:
        POST /webhooks/send
        {
            "recipient_id": "1558635688632972",
            "message_text": "Hello from the business!"
        }

    Returns:
        {
            "success": true,
            "message_id": "message_id_from_instagram",
            "error": null
        }
    """
    logger.info(f"📤 API request to send message to {send_request.recipient_id}")
    
    try:
        # Create Instagram client (MVP: one client per request)
        async with httpx.AsyncClient() as http_client:
            instagram_client = InstagramClient(
                http_client=http_client,
                settings=settings,
                logger_instance=logger
            )
            
            # Send message via Instagram API
            response = await instagram_client.send_message(
                recipient_id=send_request.recipient_id,
                message_text=send_request.message_text
            )

            if response.success:
                # Store outbound message in database
                message_repo = MessageRepository(db, request.app.state.crm_pool)

                outbound_message = Message(
                    id=response.message_id,
                    sender_id=settings.instagram_business_account_id,
                    recipient_id=send_request.recipient_id,
                    message_text=send_request.message_text,
                    direction="outbound",
                    timestamp=datetime.now(timezone.utc)
                )
                
                try:
                    await message_repo.save(outbound_message)
                    logger.info(f"✅ Message sent and stored - ID: {response.message_id}")
                    
                    return SendMessageResponse(
                        success=True,
                        message_id=response.message_id,
                        error=None
                    )
                except Exception as db_error:
                    # Message was sent successfully but failed to store in DB
                    # Log the error but still return success since Instagram API succeeded
                    logger.error(f"⚠️ Message sent but failed to store in DB: {db_error}", exc_info=True)
                    
                    return SendMessageResponse(
                        success=True,
                        message_id=response.message_id,
                        error=f"Message sent but not stored: {str(db_error)}"
                    )
            else:
                logger.error(f"❌ Failed to send message: {response.error_message}")
                raise HTTPException(
                    status_code=502,
                    detail=f"Failed to send message: {response.error_message}"
                )
                
    except InstagramAPIError as e:
        logger.error(f"❌ Instagram API error: {e.message}")
        raise HTTPException(
            status_code=502,
            detail=f"Failed to send message: {e.message}"
        )
    except Exception as e:
        logger.error(f"❌ Unexpected error in send message API: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
