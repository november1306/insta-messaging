"""
Test webhook parsing with edge cases and error scenarios.
"""
import asyncio
from datetime import datetime
from app.db.connection import init_db, get_db_session
from app.repositories.message_repository import MessageRepository
from app.core.interfaces import Message


# Test payload with multiple messages and edge cases
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


def extract_message_data(messaging_event: dict) -> dict | None:
    """Extract message data from a messaging event."""
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


async def test_complex_webhook():
    """Test webhook with multiple messages and edge cases."""
    print("🧪 Testing complex webhook payload...\n")
    
    await init_db()
    
    async for db in get_db_session():
        message_repo = MessageRepository(db)
        
        messages_processed = 0
        messages_skipped = 0
        
        for entry in COMPLEX_WEBHOOK_PAYLOAD.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                message_data = extract_message_data(messaging_event)
                
                if message_data:
                    message = Message(
                        id=message_data["id"],
                        sender_id=message_data["sender_id"],
                        recipient_id=message_data["recipient_id"],
                        message_text=message_data["text"],
                        direction="inbound",
                        timestamp=message_data["timestamp"]
                    )
                    
                    await message_repo.save(message)
                    messages_processed += 1
                    print(f"✅ Processed: {message_data['id']} - '{message_data['text']}'")
                else:
                    messages_skipped += 1
                    print(f"⏭️  Skipped: Non-text message or unsupported event")
        
        print(f"\n📊 Results:")
        print(f"   Processed: {messages_processed} messages")
        print(f"   Skipped: {messages_skipped} events")
        
        # Verify both messages were saved
        msg1 = await message_repo.get_by_id("msg_001")
        msg3 = await message_repo.get_by_id("msg_003")
        
        if msg1 and msg3:
            print(f"\n✅ All text messages stored successfully!")
        else:
            print(f"\n❌ Some messages were not stored")


if __name__ == "__main__":
    asyncio.run(test_complex_webhook())
