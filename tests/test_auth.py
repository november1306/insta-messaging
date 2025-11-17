"""
Tests for API authentication system

Tests both stub mode and real database-backed authentication.
"""
import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime, timezone

from app.api.auth import verify_api_key, _verify_api_key_stub
from app.services.api_key_service import APIKeyService
from app.db.models import Base, APIKey, APIKeyType


@pytest.fixture
def monkeypatch_stub_auth(monkeypatch):
    """Enable stub auth mode for testing"""
    monkeypatch.setenv("USE_STUB_AUTH", "true")


# ============================================
# Stub Authentication Tests
# ============================================

def test_stub_auth_with_valid_bearer_token():
    """Test that stub auth accepts valid Bearer token"""
    result = _verify_api_key_stub(authorization="Bearer test_key")
    assert result == "test_key"


def test_stub_auth_with_any_key():
    """Test that stub auth accepts any non-empty key"""
    result = _verify_api_key_stub(authorization="Bearer my_custom_key_123")
    assert result == "my_custom_key_123"


def test_stub_auth_missing_header():
    """Test that missing Authorization header returns 401"""
    with pytest.raises(HTTPException) as exc_info:
        _verify_api_key_stub(authorization=None)

    assert exc_info.value.status_code == 401
    assert "Invalid Authorization" in exc_info.value.detail


def test_stub_auth_invalid_format():
    """Test that invalid format (not Bearer) returns 401"""
    with pytest.raises(HTTPException) as exc_info:
        _verify_api_key_stub(authorization="Basic test_key")

    assert exc_info.value.status_code == 401
    assert "Invalid Authorization" in exc_info.value.detail


def test_stub_auth_empty_key():
    """Test that empty key after Bearer returns 401"""
    with pytest.raises(HTTPException) as exc_info:
        _verify_api_key_stub(authorization="Bearer ")

    assert exc_info.value.status_code == 401
    assert "Empty API key" in exc_info.value.detail


# ============================================
# Database Authentication Tests
# ============================================

@pytest_asyncio.fixture
async def test_db():
    """Create an in-memory test database"""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    yield async_session_maker

    await engine.dispose()


@pytest.mark.asyncio
async def test_api_key_generation():
    """Test API key generation format"""
    key_test = APIKeyService.generate_api_key("test")
    assert key_test.startswith("sk_test_")
    assert len(key_test) == 40  # sk_test_ (8) + 32 random chars

    key_live = APIKeyService.generate_api_key("live")
    assert key_live.startswith("sk_live_")


@pytest.mark.asyncio
async def test_create_admin_api_key(test_db):
    """Test creating an admin API key"""
    async with test_db() as db:
        api_key, db_key = await APIKeyService.create_api_key(
            db=db,
            name="Test Admin Key",
            key_type=APIKeyType.ADMIN,
            environment="test"
        )

        assert api_key.startswith("sk_test_")
        assert db_key.type == APIKeyType.ADMIN
        assert db_key.name == "Test Admin Key"
        assert db_key.is_active is True


@pytest.mark.asyncio
async def test_validate_api_key_success(test_db):
    """Test successful API key validation"""
    async with test_db() as db:
        # Create a key
        api_key, db_key = await APIKeyService.create_api_key(
            db=db,
            name="Test Key",
            key_type=APIKeyType.ADMIN,
            environment="test"
        )

        # Validate it
        validated_key = await APIKeyService.validate_api_key(db, api_key)

        assert validated_key is not None
        assert validated_key.id == db_key.id
        assert validated_key.is_active is True


@pytest.mark.asyncio
async def test_validate_api_key_invalid(test_db):
    """Test API key validation with invalid key"""
    async with test_db() as db:
        # Try to validate a non-existent key
        result = await APIKeyService.validate_api_key(db, "sk_test_InvalidKey123")

        assert result is None


@pytest.mark.asyncio
async def test_validate_api_key_inactive(test_db):
    """Test API key validation with inactive key"""
    async with test_db() as db:
        # Create and revoke a key
        api_key, db_key = await APIKeyService.create_api_key(
            db=db,
            name="Test Key",
            key_type=APIKeyType.ADMIN,
            environment="test"
        )

        await APIKeyService.revoke_api_key(db, db_key.id)

        # Try to validate the revoked key
        result = await APIKeyService.validate_api_key(db, api_key)

        assert result is None


@pytest.mark.asyncio
async def test_admin_key_has_all_permissions(test_db):
    """Test that admin keys have access to all accounts"""
    async with test_db() as db:
        # Create admin key
        _, db_key = await APIKeyService.create_api_key(
            db=db,
            name="Admin Key",
            key_type=APIKeyType.ADMIN,
            environment="test"
        )

        # Admin keys should have permission to any account
        has_permission = await APIKeyService.check_account_permission(
            db, db_key, "any_account_id"
        )

        assert has_permission is True


@pytest.mark.asyncio
async def test_account_scoped_key_permissions(test_db):
    """Test account-scoped key permissions"""
    async with test_db() as db:
        # Need to create an account first
        from app.db.models import Account
        account = Account(
            id="acc_test123",
            instagram_account_id="ig_123",
            username="testuser",
            access_token_encrypted="encrypted_token",
            crm_webhook_url="https://example.com/webhook",
            webhook_secret="secret"
        )
        db.add(account)
        await db.commit()

        # Create account-scoped key with permission to acc_test123
        _, db_key = await APIKeyService.create_api_key(
            db=db,
            name="Account Key",
            key_type=APIKeyType.ACCOUNT,
            environment="test",
            account_ids=["acc_test123"]
        )

        # Should have permission to acc_test123
        has_permission = await APIKeyService.check_account_permission(
            db, db_key, "acc_test123"
        )
        assert has_permission is True

        # Should NOT have permission to other accounts
        no_permission = await APIKeyService.check_account_permission(
            db, db_key, "acc_other456"
        )
        assert no_permission is False
