"""Instagram webhook endpoints"""
from fastapi import APIRouter, Request, Query, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.db.connection import get_db_session
from app.repositories.message_repository import MessageRepository
from app.core.interfaces import Message
from app.clients import InstagramClient
from app.rules.reply_rules import should_reply, get_reply_text
from datetime import datetime, timezone
import logging
import httpx

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
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
    """
    logger.info(f"Webhook verification request received - mode: {hub_mode}")
    
    # Verify the token matches our configured token
    if hub_mode == "subscribe" and hub_verify_token == settings.facebook_verify_token:
        logger.info("✅ Webhook verification successful")
        # Return the challenge to complete verification
        return int(hub_challenge)
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
    
    TODO (Task 9): Implement webhook signature validation before processing
                   https://developers.facebook.com/docs/messenger-platform/webhooks#security
    """
    messages_processed = 0
    
    try:
        # Get the raw request body
        body = await request.json()
        
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
        message_repo = MessageRepository(db)

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
                            timestamp=message_data["timestamp"]
                        )
                        
                        # Save to database (handle duplicates from webhook retries)
                        try:
                            await message_repo.save(message)
                            messages_processed += 1
                            logger.info(f"✅ Stored message {message.id} from {message.sender_id}")
                            
                            # Check for trigger keyword and send auto-reply
                            await _handle_auto_reply(message, message_repo, db)
                            
                        except ValueError:
                            # Message already exists - this is ok for webhook retries
                            logger.info(f"ℹ️ Message {message.id} already exists, skipping")
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
    db: AsyncSession
) -> None:
    """
    Handle auto-reply logic for inbound messages.
    
    Uses user-defined rules from app.rules.reply_rules to determine
    if and how to reply to messages.
    
    Args:
        inbound_message: The inbound message that was just received
        message_repo: Repository for storing outbound messages
        db: Database session for transaction management
    """
    try:
        # Check if message should trigger a reply (user-defined rule)
        if not should_reply(inbound_message.message_text):
            logger.info(f"No reply rule matched, skipping auto-reply")
            return
        
        # Get reply text from user-defined rules
        reply_text = get_reply_text(inbound_message.message_text)
        
        if not reply_text:
            logger.warning(f"Reply rule matched but no reply text defined")
            return
        
        logger.info(f"📤 Sending auto-reply...")
        
        # Send reply using Instagram API
        async with httpx.AsyncClient() as http_client:
            instagram_client = InstagramClient(
                http_client=http_client,
                settings=settings,
                logger_instance=logger
            )
            
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
        logger.error(f"❌ Error in auto-reply handler: {e}", exc_info=True)


def _extract_message_data(messaging_event: dict) -> dict | None:
    """
    Extract message data from a messaging event.
    
    Args:
        messaging_event: A single messaging event from the webhook payload
        
    Returns:
        Dictionary with message data if it's a text message, None otherwise
    """
    try:
        # Check if this is a message event (not delivery, read, etc.)
        if "message" not in messaging_event:
            return None
        
        message = messaging_event["message"]
        
        # Only process text messages for now
        if "text" not in message:
            message_type = "image" if "attachments" in message else "unknown"
            logger.info(f"Skipping non-text message type: {message_type}")
            return None
        
        # Extract required fields
        sender_id = messaging_event.get("sender", {}).get("id")
        recipient_id = messaging_event.get("recipient", {}).get("id")
        message_id = message.get("mid")
        message_text = message.get("text")
        timestamp_ms = messaging_event.get("timestamp")
        
        # Validate required fields
        if not all([sender_id, recipient_id, message_id, message_text, timestamp_ms]):
            logger.warning("Missing required fields in message event")
            return None
        
        # Convert timestamp from milliseconds to datetime (UTC timezone-aware)
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)
        
        return {
            "id": message_id,
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "text": message_text,
            "timestamp": timestamp
        }
        
    except Exception as e:
        logger.error(f"Error extracting message data: {e}", exc_info=True)
        return None
