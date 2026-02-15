"""
Shared pytest fixtures for Instagram Messenger Automation tests.

This module provides:
- Database fixtures (in-memory SQLite)
- Mock Instagram client
- Sample domain objects
- API test client

Usage:
    Fixtures are automatically discovered by pytest.
    Import specific fixtures in test files as needed.
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import AsyncGenerator
from unittest.mock import MagicMock, AsyncMock

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Account, User, UserAccount, MessageModel


# ============================================
# Database Fixtures
# ============================================

@pytest.fixture
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Create an in-memory SQLite database for testing.

    Yields:
        AsyncSession connected to fresh in-memory database.
        Database is destroyed after test completes.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_factory() as session:
        yield session

    await engine.dispose()


# ============================================
# Mock Fixtures
# ============================================

@pytest.fixture
def mock_instagram_client():
    """
    Mock Instagram API client for testing without real API calls.

    Returns:
        MagicMock with common Instagram client methods mocked.
    """
    client = MagicMock()

    # Async methods
    client.get_conversations = AsyncMock(return_value=[])
    client.get_conversation_messages = AsyncMock(return_value=[])
    client.get_user_profile = AsyncMock(return_value=None)
    client.send_message = AsyncMock(return_value={"message_id": "mid_test123"})
    client.get_business_account_profile = AsyncMock(return_value={
        "id": "17841478096518771",
        "username": "test_business",
        "account_type": "BUSINESS"
    })

    return client


@pytest.fixture
def mock_httpx_client(mocker):
    """
    Mock httpx.AsyncClient for external HTTP calls.

    Use this when testing code that makes HTTP requests.
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": []}

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.post = AsyncMock(return_value=mock_response)

    mocker.patch("httpx.AsyncClient", return_value=mock_client)
    return mock_client, mock_response


# ============================================
# Domain Object Fixtures
# ============================================

@pytest.fixture
def sample_account() -> Account:
    """
    Create a sample Account model for testing.

    Returns:
        Account with realistic test data.
    """
    return Account(
        id="acc_test123456",
        instagram_account_id="17841478096518771",
        messaging_channel_id="17841478096518771",
        username="test_business",
        access_token_encrypted=b"encrypted_test_token",
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=60),
        profile_picture_url="https://example.com/pic.jpg",
        account_type="BUSINESS"
    )


@pytest.fixture
def sample_account_no_channel() -> Account:
    """
    Create an Account without messaging_channel_id set.

    Simulates a newly linked account before first webhook.
    """
    return Account(
        id="acc_newaccount",
        instagram_account_id="24370771369265571",
        messaging_channel_id=None,  # Not yet set
        username="new_business",
        access_token_encrypted=b"encrypted_test_token",
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=60)
    )


@pytest.fixture
def sample_identity(sample_account):
    """
    Create AccountIdentity from sample account.

    Returns:
        AccountIdentity instance for testing ID resolution.
    """
    from app.domain.account_identity import AccountIdentity
    return AccountIdentity.from_account(sample_account)


@pytest.fixture
def sample_user() -> User:
    """Create a sample User for testing."""
    return User(
        id=1,
        username="testuser",
        password_hash="$2b$12$test_hash",
        created_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_message() -> MessageModel:
    """Create a sample inbound message for testing."""
    return MessageModel(
        id="mid_test_inbound_123",
        account_id="acc_test123456",
        sender_id="customer_98765",
        recipient_id="17841478096518771",
        message_text="Hello, I have a question",
        direction="inbound",
        timestamp=datetime.now(timezone.utc),
        delivery_status="received"
    )


# ============================================
# API Test Fixtures
# ============================================

@pytest.fixture
def auth_headers():
    """
    Generate mock authorization headers.

    Returns:
        Dict with Bearer token header.
    """
    return {"Authorization": "Bearer sk_user_test_token_12345"}


@pytest.fixture
def webhook_payload():
    """
    Sample Instagram webhook payload for testing.

    Returns:
        Dict mimicking Instagram's webhook format.
    """
    return {
        "object": "instagram",
        "entry": [{
            "id": "17841478096518771",
            "time": 1706443200000,
            "messaging": [{
                "sender": {"id": "customer_98765"},
                "recipient": {"id": "17841478096518771"},
                "timestamp": 1706443200000,
                "message": {
                    "mid": "mid_webhook_test_456",
                    "text": "Hi, I want to order"
                }
            }]
        }]
    }


# ============================================
# Utility Fixtures
# ============================================

@pytest.fixture
def freeze_time(mocker):
    """
    Fixture to freeze datetime.now() to a specific time.

    Usage:
        def test_something(freeze_time):
            freeze_time("2026-01-28 12:00:00")
            # datetime.now() will return the frozen time
    """
    from datetime import datetime

    def _freeze(time_str: str):
        frozen = datetime.fromisoformat(time_str)
        mocker.patch("datetime.datetime.now", return_value=frozen)
        return frozen

    return _freeze


# ============================================
# Seeded Database Fixture
# ============================================

# Stable test secret for deterministic encryption in tests
TEST_SESSION_SECRET = "test-session-secret-for-pytest-only"


@pytest.fixture
async def seeded_db() -> AsyncGenerator[dict, None]:
    """
    In-memory database pre-seeded with test preconditions.

    Creates a fresh database, runs seed_preconditions (test user + @el_dmytr
    account + link), and yields the result dict along with the session.

    Yields:
        Dict with keys: "user", "account", "db", "session_secret"
    """
    from app.db.seed import seed_preconditions

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_factory = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_factory() as session:
        result = await seed_preconditions(session, TEST_SESSION_SECRET)
        yield {
            **result,
            "db": session,
            "session_secret": TEST_SESSION_SECRET,
        }

    await engine.dispose()
