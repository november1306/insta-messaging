"""
Integration tests for MessageRepository.

These tests verify the repository works correctly with a real database.
"""
import pytest
from datetime import datetime
from app.core.interfaces import Message
from app.repositories.message_repository import MessageRepository
from app.db.connection import init_db, get_db_session


@pytest.mark.asyncio
async def test_save_and_retrieve_message():
    """Test saving and retrieving a message."""
    # Get database session (database initialized by fixture)
    async for db_session in get_db_session():
        # Create repository
        repo = MessageRepository(db_session)
        
        # Create test message
        test_message = Message(
            id="test_msg_123",
            sender_id="user_456",
            recipient_id="page_789",
            message_text="Hello, this is a test message!",
            direction="inbound",
            timestamp=datetime.now()
        )
        
        # Save message
        saved_message = await repo.save(test_message)
        assert saved_message.id == test_message.id
        
        # Retrieve message
        retrieved_message = await repo.get_by_id("test_msg_123")
        
        assert retrieved_message is not None
        assert retrieved_message.id == "test_msg_123"
        assert retrieved_message.sender_id == "user_456"
        assert retrieved_message.recipient_id == "page_789"
        assert retrieved_message.message_text == "Hello, this is a test message!"
        assert retrieved_message.direction == "inbound"


@pytest.mark.asyncio
async def test_get_nonexistent_message():
    """Test retrieving a message that doesn't exist."""
    async for db_session in get_db_session():
        repo = MessageRepository(db_session)
        
        # Try to retrieve non-existent message
        result = await repo.get_by_id("does_not_exist")
        
        assert result is None


@pytest.mark.asyncio
async def test_save_duplicate_message_fails():
    """Test that saving a message with duplicate ID raises ValueError."""
    # First, save a message successfully
    async for db_session in get_db_session():
        repo = MessageRepository(db_session)
        
        message1 = Message(
            id="duplicate_test",
            sender_id="user_1",
            recipient_id="page_1",
            message_text="First message",
            direction="inbound",
            timestamp=datetime.now()
        )
        await repo.save(message1)
        # Session commits here automatically
    
    # Now try to save another message with same ID in a new session
    # The ValueError should be raised
    error_raised = False
    try:
        async for db_session in get_db_session():
            repo = MessageRepository(db_session)
            
            message2 = Message(
                id="duplicate_test",
                sender_id="user_2",
                recipient_id="page_2",
                message_text="Second message",
                direction="outbound",
                timestamp=datetime.now()
            )
            
            # This should raise ValueError for duplicate ID
            await repo.save(message2)
    except ValueError as e:
        # Expected error
        assert "already exists" in str(e)
        error_raised = True
    
    assert error_raised, "Expected ValueError for duplicate message ID"
