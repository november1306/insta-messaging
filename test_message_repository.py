"""
Simple test to verify MessageRepository implementation.
"""
import asyncio
from datetime import datetime
from app.core.interfaces import Message
from app.repositories.message_repository import MessageRepository
from app.db.connection import init_db, get_db_session


async def test_message_repository():
    """Test basic save and retrieve operations."""
    print("🧪 Testing MessageRepository...")
    
    # Initialize database
    await init_db()
    print("✅ Database initialized")
    
    # Get database session
    async for db_session in get_db_session():
        # Create repository
        repo = MessageRepository(db_session)
        print("✅ Repository created")
        
        # Create test message
        test_message = Message(
            id="test_msg_123",
            sender_id="user_456",
            recipient_id="page_789",
            message_text="Hello, this is a test message!",
            direction="inbound",
            timestamp=datetime.now()
        )
        print(f"✅ Created test message: {test_message.id}")
        
        # Save message
        saved_message = await repo.save(test_message)
        print(f"✅ Saved message: {saved_message.id}")
        
        # Retrieve message
        retrieved_message = await repo.get_by_id("test_msg_123")
        
        if retrieved_message:
            print(f"✅ Retrieved message: {retrieved_message.id}")
            print(f"   Sender: {retrieved_message.sender_id}")
            print(f"   Recipient: {retrieved_message.recipient_id}")
            print(f"   Text: {retrieved_message.message_text}")
            print(f"   Direction: {retrieved_message.direction}")
            print(f"   Timestamp: {retrieved_message.timestamp}")
        else:
            print("❌ Failed to retrieve message")
            return
        
        # Test retrieving non-existent message
        non_existent = await repo.get_by_id("does_not_exist")
        if non_existent is None:
            print("✅ Correctly returned None for non-existent message")
        else:
            print("❌ Should have returned None for non-existent message")
            return
        
        print("\n🎉 All tests passed!")


if __name__ == "__main__":
    asyncio.run(test_message_repository())
