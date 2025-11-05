"""Instagram webhook endpoints"""
from fastapi import APIRouter, Request, Query, HTTPException, status
from app.config import settings
import logging

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
async def handle_webhook(request: Request):
    """
    Webhook endpoint for receiving Instagram messages.
    
    Facebook sends POST requests with message data.
    We log the payload and return 200 to acknowledge receipt.
    """
    try:
        # Get the raw request body
        body = await request.json()

        # Log only metadata, never log message content or personal data
        entry_count = len(body.get("entry", []))
        object_type = body.get("object", "unknown")

        logger.info(f"📨 Webhook POST request received - object: {object_type}, entries: {entry_count}")

        # For now, just acknowledge receipt
        # Message processing will be implemented in Task 2 & 3
        return {"status": "ok"}

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        # Always return 200 to prevent Facebook from retrying
        return {"status": "error", "message": str(e)}
