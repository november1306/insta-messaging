"""
Manual test script to verify webhook message parsing.

This script tests the webhook endpoint with a sample Instagram message payload.
"""
import asyncio
import sys
from datetime import datetime
from app.db.connection import init_db, get_db_session
from app.repositories.message_repository import MessageRepository
from app.core.interfaces import Message


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


def extract_message_data(messaging_event: dict) -> dict | None:
    """
    Extract message data from a messaging event.
    (Copy of the function from webhooks.py for testing)
    """
    try:
        if "message" not in messaging_event:
            return None
        
        message = messaging_event["message"]
        
        if "text" not in message:
            return None
        
        sender_id = messaging_event.get("sender", {}).get("id")
        recipient_id = messaging_event.get("recipient", {}).get("id")
        message_id = message.get("mid")
        message_text = message.get("text")
        timestamp_ms = messaging_event.get("timestamp")
        
        if not all([sender_id, recipient_id, message_id, message_text, timestamp_ms]):
            return None
        
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000.0)
        
        return {
            "id": message_id,
            "sender_id": sender_id,
            "recipient_id": recipient_id,
            "text": message_text,
            "timestamp": timestamp
        }
        
    except Exception as e:
        print(f"Error extracting message data: {e}")
        return None


async def test_webhook_parsing():
    """Test webhook message parsing and storage."""
    print("🧪 Testing webhook message parsing...\n")
    
    # Initialize database
    await init_db()
    print("✅ Database initialized\n")
    
    # Get database session
    async for db in get_db_session():
        message_repo = MessageRepository(db)
        
        # Parse webhook payload
        messages_processed = 0
        for entry in SAMPLE_WEBHOOK_PAYLOAD.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                message_data = extract_message_data(messaging_event)
                
                if message_data:
                    print(f"📨 Extracted message data:")
                    print(f"   ID: {message_data['id']}")
                    print(f"   Sender: {message_data['sender_id']}")
                    print(f"   Recipient: {message_data['recipient_id']}")
                    print(f"   Text: {message_data['text']}")
                    print(f"   Timestamp: {message_data['timestamp']}\n")
                    
                    # Create Message object
                    message = Message(
                        id=message_data["id"],
                        sender_id=message_data["sender_id"],
                        recipient_id=message_data["recipient_id"],
                        message_text=message_data["text"],
                        direction="inbound",
                        timestamp=message_data["timestamp"]
                    )
                    
                    # Save to database
                    await message_repo.save(message)
                    messages_processed += 1
                    print(f"✅ Saved message to database\n")
        
        print(f"✅ Test completed! Processed {messages_processed} messages\n")
        
        # Verify message was saved by retrieving it
        retrieved_message = await message_repo.get_by_id("test_message_id_001")
        if retrieved_message:
            print(f"✅ Verification: Message retrieved from database")
            print(f"   ID: {retrieved_message.id}")
            print(f"   Sender: {retrieved_message.sender_id}")
            print(f"   Text: {retrieved_message.message_text}")
            print(f"   Direction: {retrieved_message.direction}")
        else:
            print(f"❌ Verification failed: Could not retrieve message")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(test_webhook_parsing())
