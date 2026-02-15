# Testing Instructions for Claude Code

## Overview

This document defines testing standards and practices for the Instagram Messenger Automation project. Claude Code MUST follow these instructions when writing, modifying, or running tests.

---

## Golden Rules

1. **Never skip tests** - If tests fail, fix the code or the test, never ignore failures
2. **Test behavior, not implementation** - Tests should verify WHAT the code does, not HOW
3. **One assertion per test concept** - Each test should verify one logical behavior
4. **Tests are documentation** - Test names and structure should explain the feature
5. **Fast feedback loop** - Unit tests must be fast (<100ms each)

---

## Test Pyramid

```
        /\
       /  \        E2E Tests (few)
      /----\       - Full system with real Instagram API
     /      \      - Manual or CI-only
    /--------\     Integration Tests (some)
   /          \    - API endpoints with test DB
  /------------\   - Webhook processing
 /              \  Unit Tests (many)
/________________\ - Domain logic, services, utilities
```

### Distribution Target
- **Unit tests**: 70% of test count
- **Integration tests**: 25% of test count
- **E2E tests**: 5% of test count (manual/CI-triggered)

---

## Directory Structure

```
tests/
├── conftest.py              # Shared fixtures (create if missing)
├── factories/               # Test data factories
│   ├── __init__.py
│   ├── account_factory.py
│   ├── message_factory.py
│   └── user_factory.py
├── unit/                    # Fast, isolated tests
│   ├── __init__.py
│   ├── domain/              # Domain logic tests
│   │   └── test_account_identity.py
│   ├── services/            # Service layer tests
│   │   └── test_instagram_sync_service.py
│   └── utils/               # Utility function tests
├── integration/             # Tests requiring DB or HTTP
│   ├── __init__.py
│   ├── api/                 # API endpoint tests
│   │   ├── test_accounts_api.py
│   │   ├── test_messages_api.py
│   │   └── test_webhooks_api.py
│   └── services/            # Service integration tests
└── e2e/                     # End-to-end tests (optional)
    └── test_full_workflow.py
```

---

## Naming Conventions

### Test Files
- Prefix: `test_`
- Mirror source structure: `app/services/foo.py` → `tests/unit/services/test_foo.py`

### Test Classes
- Prefix: `Test`
- Group by feature: `TestAccountIdentity`, `TestMessageSync`

### Test Functions
```python
def test_<unit>_<scenario>_<expected_result>():
    """Test pattern: test_what_when_then"""
    pass

# Examples:
def test_is_business_id_with_matching_id_returns_true():
def test_sync_account_with_empty_conversations_returns_zero():
def test_webhook_with_invalid_signature_returns_403():
```

### Markers
Use pytest markers for categorization:
```python
@pytest.mark.unit          # Fast, no I/O
@pytest.mark.integration   # Requires DB or HTTP
@pytest.mark.api           # API endpoint tests
@pytest.mark.webhooks      # Webhook processing
@pytest.mark.auth          # Authentication tests
@pytest.mark.slow          # Tests taking >1s
```

---

## Test Structure: AAA Pattern

Every test MUST follow the **Arrange-Act-Assert** pattern:

```python
async def test_detect_direction_with_business_sender_returns_outbound():
    """AccountIdentity correctly identifies outbound messages."""
    # Arrange: Set up test data and dependencies
    identity = AccountIdentity(
        account_id="acc_123",
        instagram_account_id="12345",
        messaging_channel_id="67890"
    )
    sender_id = "67890"  # Matches messaging_channel_id

    # Act: Execute the code under test
    result = identity.detect_direction(sender_id)

    # Assert: Verify the expected outcome
    assert result == "outbound"
```

### Comments in Tests
- Add section comments (`# Arrange`, `# Act`, `# Assert`) for clarity
- Add docstring explaining the business scenario being tested

---

## Fixtures

### Shared Fixtures (conftest.py)

Create `tests/conftest.py` with these essential fixtures:

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.db.models import Base

# ============================================
# Database Fixtures
# ============================================

@pytest.fixture
async def test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    await engine.dispose()


@pytest.fixture
def mock_instagram_client(mocker):
    """Mock Instagram API client."""
    client = mocker.MagicMock()
    client.get_conversations = mocker.AsyncMock(return_value=[])
    client.get_conversation_messages = mocker.AsyncMock(return_value=[])
    client.send_message = mocker.AsyncMock(return_value={"message_id": "mid_123"})
    return client


# ============================================
# Domain Object Fixtures
# ============================================

@pytest.fixture
def sample_account():
    """Create a sample Account for testing."""
    from app.db.models import Account
    from datetime import datetime, timezone

    return Account(
        id="acc_test123",
        instagram_account_id="17841478096518771",
        messaging_channel_id="17841478096518771",
        username="test_business",
        access_token_encrypted=b"encrypted_token",
        token_expires_at=datetime.now(timezone.utc)
    )


@pytest.fixture
def sample_identity(sample_account):
    """Create AccountIdentity from sample account."""
    from app.domain.account_identity import AccountIdentity
    return AccountIdentity.from_account(sample_account)
```

### Fixture Scope
- `function` (default): Fresh instance per test
- `class`: Shared across test class
- `module`: Shared across test file
- `session`: Shared across all tests (use sparingly)

---

## Mocking Strategy

### What to Mock
- **Always mock**: External APIs (Instagram, webhooks), time/dates, random values
- **Sometimes mock**: Database (use in-memory SQLite for speed)
- **Never mock**: The code under test, simple data classes

### Mock External Services
```python
@pytest.fixture
def mock_httpx_client(mocker):
    """Mock httpx for Instagram API calls."""
    mock_response = mocker.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": []}

    mock_client = mocker.MagicMock()
    mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = mocker.AsyncMock(return_value=None)
    mock_client.get = mocker.AsyncMock(return_value=mock_response)
    mock_client.post = mocker.AsyncMock(return_value=mock_response)

    mocker.patch("httpx.AsyncClient", return_value=mock_client)
    return mock_client
```

### Mock Time
```python
from freezegun import freeze_time

@freeze_time("2026-01-28 12:00:00")
async def test_token_expiration():
    # datetime.now() will return 2026-01-28 12:00:00
    pass
```

---

## Test Data Factories

Create factories for consistent test data generation:

```python
# tests/factories/message_factory.py
from datetime import datetime, timezone
from typing import Optional
import uuid

class MessageFactory:
    """Factory for creating test MessageModel instances."""

    @staticmethod
    def create(
        id: Optional[str] = None,
        account_id: str = "acc_test123",
        sender_id: str = "customer_123",
        recipient_id: str = "17841478096518771",
        message_text: str = "Test message",
        direction: str = "inbound",
        **kwargs
    ):
        from app.db.models import MessageModel

        return MessageModel(
            id=id or f"mid_{uuid.uuid4().hex[:12]}",
            account_id=account_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            message_text=message_text,
            direction=direction,
            timestamp=kwargs.get("timestamp", datetime.now(timezone.utc)),
            delivery_status=kwargs.get("delivery_status", "sent")
        )

    @staticmethod
    def create_batch(count: int, **kwargs):
        """Create multiple messages."""
        return [MessageFactory.create(**kwargs) for _ in range(count)]
```

---

## Running Tests

### Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/unit/domain/test_account_identity.py

# Run specific test class
pytest tests/unit/domain/test_account_identity.py::TestAccountIdentity

# Run specific test function
pytest tests/unit/domain/test_account_identity.py::TestAccountIdentity::test_is_business_id_returns_true

# Run by marker
pytest -m unit           # Only unit tests
pytest -m "not slow"     # Exclude slow tests
pytest -m integration    # Only integration tests

# Run with coverage
pytest --cov=app --cov-report=html

# Run and stop on first failure
pytest -x

# Run last failed tests
pytest --lf

# Run with print output visible
pytest -s
```

### Coverage Expectations
- **Minimum**: 60% overall coverage
- **Target**: 80% for critical paths (auth, webhooks, message handling)
- **Domain layer**: 90%+ coverage (AccountIdentity, value objects)

---

## Integration Test Requirements

### Database Tests
- Use in-memory SQLite or test database
- Always clean up after tests (use fixtures with cleanup)
- Never depend on test execution order

### API Tests
```python
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

@pytest.fixture
async def async_client(test_db):
    """Async client for API testing."""
    from app.main import app

    # Override database dependency
    app.dependency_overrides[get_db_session] = lambda: test_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

    app.dependency_overrides.clear()
```

### Webhook Tests
```python
import hashlib
import hmac

def generate_webhook_signature(payload: str, secret: str) -> str:
    """Generate valid Instagram webhook signature for testing."""
    return hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
```

---

## What Claude Code MUST Do

### When Writing New Code
1. **Ask**: "Should I write tests for this?"
2. If the change affects:
   - Domain logic → Write unit tests
   - API endpoints → Write integration tests
   - Bug fix → Write regression test first (TDD)

### When Fixing Bugs
1. **First**: Write a failing test that reproduces the bug
2. **Then**: Fix the bug
3. **Verify**: Test passes

### When Refactoring
1. **Ensure**: Existing tests pass before refactoring
2. **Run**: Tests after each refactoring step
3. **Do not**: Change tests and code simultaneously

### After Implementation
1. **Always run**: `pytest` before considering work complete
2. **If tests fail**: Fix immediately, do not defer
3. **Report**: Test results to user

---

## Example Test File

```python
"""
Unit tests for AccountIdentity domain class.

Tests verify:
- ID resolution (effective_channel_id)
- Business ID detection
- Direction detection
- Message ID normalization
"""

import pytest
from app.domain.account_identity import AccountIdentity


class TestAccountIdentity:
    """Tests for AccountIdentity ID resolution."""

    # ==========================================
    # effective_channel_id tests
    # ==========================================

    def test_effective_channel_id_returns_messaging_channel_when_set(self):
        """When messaging_channel_id is set, it takes precedence."""
        # Arrange
        identity = AccountIdentity(
            account_id="acc_123",
            instagram_account_id="111",
            messaging_channel_id="222"
        )

        # Act
        result = identity.effective_channel_id

        # Assert
        assert result == "222"

    def test_effective_channel_id_falls_back_to_instagram_id(self):
        """When messaging_channel_id is None, fallback to instagram_account_id."""
        # Arrange
        identity = AccountIdentity(
            account_id="acc_123",
            instagram_account_id="111",
            messaging_channel_id=None
        )

        # Act
        result = identity.effective_channel_id

        # Assert
        assert result == "111"

    # ==========================================
    # is_business_id tests
    # ==========================================

    def test_is_business_id_with_instagram_account_id_returns_true(self):
        """instagram_account_id should be recognized as business ID."""
        # Arrange
        identity = AccountIdentity(
            account_id="acc_123",
            instagram_account_id="111",
            messaging_channel_id="222"
        )

        # Act & Assert
        assert identity.is_business_id("111") is True

    def test_is_business_id_with_messaging_channel_id_returns_true(self):
        """messaging_channel_id should be recognized as business ID."""
        # Arrange
        identity = AccountIdentity(
            account_id="acc_123",
            instagram_account_id="111",
            messaging_channel_id="222"
        )

        # Act & Assert
        assert identity.is_business_id("222") is True

    def test_is_business_id_with_customer_id_returns_false(self):
        """Customer IDs should not be recognized as business ID."""
        # Arrange
        identity = AccountIdentity(
            account_id="acc_123",
            instagram_account_id="111",
            messaging_channel_id="222"
        )

        # Act & Assert
        assert identity.is_business_id("333") is False

    # ==========================================
    # detect_direction tests
    # ==========================================

    def test_detect_direction_with_business_sender_returns_outbound(self):
        """Messages from business account are outbound."""
        # Arrange
        identity = AccountIdentity(
            account_id="acc_123",
            instagram_account_id="111",
            messaging_channel_id="222"
        )

        # Act
        result = identity.detect_direction("222")

        # Assert
        assert result == "outbound"

    def test_detect_direction_with_customer_sender_returns_inbound(self):
        """Messages from customers are inbound."""
        # Arrange
        identity = AccountIdentity(
            account_id="acc_123",
            instagram_account_id="111",
            messaging_channel_id="222"
        )

        # Act
        result = identity.detect_direction("customer_456")

        # Assert
        assert result == "inbound"


class TestAccountIdentityFromAccount:
    """Tests for AccountIdentity.from_account() factory method."""

    def test_from_account_creates_identity_with_all_fields(self, sample_account):
        """Factory method should populate all fields from Account model."""
        # Act
        identity = AccountIdentity.from_account(sample_account)

        # Assert
        assert identity.account_id == sample_account.id
        assert identity.instagram_account_id == sample_account.instagram_account_id
        assert identity.messaging_channel_id == sample_account.messaging_channel_id
```

---

## E2E Testing with Playwright

E2E tests verify the complete user journey through the actual UI. We use **Playwright MCP** for browser automation.

### Two Approaches

| Approach | Use Case | How |
|----------|----------|-----|
| **Ad-hoc verification** | Quick checks during development | `/verify-ui` skill |
| **Automated E2E tests** | CI/CD, regression testing | pytest + Playwright |

### Ad-hoc Verification: `/verify-ui` Skill

For quick, interactive UI checks during development:

```bash
# Check if a message appears in chat
/verify-ui --check message --text "Test message"

# Verify authentication state
/verify-ui --check auth

# Check conversation list loads
/verify-ui --check conversations

# Verify specific element exists
/verify-ui --check element --selector ".chat-container"

# Test against VPS instead of local
/verify-ui --check message --text "Test" --target vps

# Take screenshot for debugging
/verify-ui --check layout --screenshot
```

### Automated E2E Tests: Playwright MCP Tools

For automated testing, use Playwright MCP tools directly in tests:

```python
# tests/e2e/test_chat_workflow.py
"""
E2E tests for chat functionality using Playwright MCP.

These tests verify complete user workflows through the actual UI.
Requires: Frontend and backend running (use /dev-environment start)
"""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.slow]


class TestChatWorkflow:
    """E2E tests for the chat interface."""

    async def test_login_and_view_conversations(self, playwright_page):
        """User can log in and see conversation list."""
        # Arrange - Navigate to login
        await playwright_page.navigate("http://localhost:5173/chat/")

        # Act - Login
        await playwright_page.fill_form([
            {"name": "username", "type": "textbox", "value": "admin"},
            {"name": "password", "type": "textbox", "value": "test_password"}
        ])
        await playwright_page.click("Sign In button")

        # Assert - Conversations visible
        snapshot = await playwright_page.snapshot()
        assert "Conversations" in snapshot or "No conversations" in snapshot

    async def test_send_message_appears_in_chat(self, playwright_page):
        """Sent message appears in the chat interface."""
        # ... test implementation
        pass
```

### Playwright MCP Tool Reference

| Tool | Purpose |
|------|---------|
| `mcp__playwright__browser_navigate` | Navigate to URL |
| `mcp__playwright__browser_snapshot` | Get accessibility tree (better than screenshot for assertions) |
| `mcp__playwright__browser_click` | Click element by ref |
| `mcp__playwright__browser_type` | Type text into input |
| `mcp__playwright__browser_fill_form` | Fill multiple form fields |
| `mcp__playwright__browser_wait_for` | Wait for text/element |
| `mcp__playwright__browser_take_screenshot` | Capture screenshot |

### E2E Test Fixtures

```python
# tests/conftest.py - Add E2E fixtures

@pytest.fixture
async def playwright_page():
    """
    Provides Playwright page for E2E tests.

    Note: This is a simplified fixture. In practice, you'd use
    Playwright MCP tools directly in the test.
    """
    # For Playwright MCP, we don't need a fixture -
    # Claude Code calls MCP tools directly
    yield None


@pytest.fixture
def e2e_base_url():
    """Base URL for E2E tests."""
    return "http://localhost:5173"
```

### When to Write E2E Tests

Write E2E tests for:
- **Critical user journeys**: Login, send message, view conversations
- **Cross-component interactions**: Webhook → UI update
- **Visual regressions**: Layout changes after deployment

Do NOT write E2E tests for:
- Individual component behavior (use unit tests)
- API contract testing (use integration tests)
- Edge cases (too slow, use unit tests)

### Running E2E Tests

```bash
# Ensure dev environment is running
/dev-environment start

# Run E2E tests only
pytest -m e2e -v

# Run with visible browser (for debugging)
pytest -m e2e -v --headed

# Skip E2E in quick test runs
pytest -m "not e2e"
```

### E2E Test Workflow with Skills

Typical E2E verification during development:

```bash
# 1. Start the environment
/dev-environment start

# 2. Send a test webhook
/test-webhook --message "E2E test message"

# 3. Verify it appears in UI
/verify-ui --check message --text "E2E test message"

# 4. Check overall layout
/verify-ui --check layout --screenshot
```

---

## CI/CD Integration

### GitHub Actions Workflow
Tests should run on every PR and push to main:

```yaml
# .github/workflows/test.yml
name: Tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest-cov

      - name: Run tests
        run: pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
```

---

## Quick Reference

### Pytest Commands

| Task | Command |
|------|---------|
| Run all tests | `pytest` |
| Run unit tests only | `pytest -m unit` |
| Run integration tests | `pytest -m integration` |
| Run E2E tests | `pytest -m e2e` |
| Skip slow tests | `pytest -m "not slow"` |
| Run with coverage | `pytest --cov=app` |
| Run specific file | `pytest tests/unit/domain/test_account_identity.py` |
| Run and show prints | `pytest -s` |
| Stop on first fail | `pytest -x` |
| Run last failed | `pytest --lf` |

### E2E Verification Skills

| Task | Skill Command |
|------|---------------|
| Check message in UI | `/verify-ui --check message --text "..."` |
| Check auth state | `/verify-ui --check auth` |
| Check conversations | `/verify-ui --check conversations` |
| Take screenshot | `/verify-ui --check layout --screenshot` |
| Test on VPS | `/verify-ui --check auth --target vps` |

---

## Checklist for Claude Code

Before marking any coding task complete:

### Mandatory (All Changes)
- [ ] Unit tests written/updated for domain logic
- [ ] All tests pass (`pytest -m unit` shows green)
- [ ] Tests follow AAA pattern
- [ ] Test names are descriptive

### If API Changed
- [ ] Integration tests updated
- [ ] `pytest -m integration` passes (with server running)

### If UI Changed
- [ ] Verify with `/verify-ui --check layout`
- [ ] E2E smoke test passes if critical flow affected

### Coverage
- [ ] No skipped tests without documented reason
- [ ] Test coverage maintained or improved
