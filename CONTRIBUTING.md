# Contributing to Instagram Messenger Automation

Thank you for contributing! This guide will help you get started.

## 🚀 Quick Start

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR_USERNAME/insta-auto.git
cd insta-auto
```

### 2. Set Up Development Environment

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install development dependencies
pip install ruff black mypy pytest pytest-asyncio pytest-cov

# Set up pre-commit hooks (optional)
pip install pre-commit
pre-commit install
```

### 3. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

## 📝 Development Workflow

### Making Changes

1. **Write Code**: Follow the architecture principles (see below)
2. **Format Code**: Run `black .` before committing
3. **Lint Code**: Run `ruff check .` to catch issues
4. **Type Check**: Run `mypy app` to verify types
5. **Test**: Write tests for new functionality

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app --cov-report=html

# Run specific test file
pytest tests/test_interfaces.py
```

### Code Quality Checks

```bash
# Format code
black .

# Lint code
ruff check . --fix

# Type checking
mypy app --ignore-missing-imports

# Security scan
bandit -r app
```

## 🏗️ Architecture Principles

### 1. Account-Scoped Operations
All operations must include `account_id` parameter:

```python
# ✅ Good
async def send_message(account_id: str, recipient_id: str, text: str):
    account = await account_repo.get_by_id(account_id)
    # Use account-specific credentials

# ❌ Bad
async def send_message(recipient_id: str, text: str):
    # Uses global credentials - doesn't support multiple accounts
```

### 2. Interface-Driven Design
Program to interfaces, not implementations:

```python
# ✅ Good
class InstagramMessageSender(IMessageSender):
    async def send_message(self, account_id: str, ...):
        pass

# ❌ Bad
class InstagramMessageSender:  # No interface
    def send_message(self, ...):  # Not async
        pass
```

### 3. Encrypted Credentials
Never store or log credentials in plain text:

```python
# ✅ Good
account.access_token_encrypted = encrypt_token(token, secret_key)
logger.info(f"Account {account.id} updated")

# ❌ Bad
account.access_token = token  # Plain text
logger.info(f"Token: {token}")  # Logged!
```

### 4. Error Handling for Webhooks
Always return 200 to webhooks, handle errors internally:

```python
# ✅ Good
@router.post("/webhooks/instagram")
async def handle_webhook(request: Request):
    try:
        await process_webhook(request)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    return {"status": "ok"}  # Always 200

# ❌ Bad
@router.post("/webhooks/instagram")
async def handle_webhook(request: Request):
    await process_webhook(request)  # May raise exception
    return {"status": "ok"}
```

## 📋 Pull Request Process

### 1. Before Opening PR

- [ ] Code is formatted with Black
- [ ] Linting passes (Ruff)
- [ ] Type checking passes (MyPy)
- [ ] Tests are written and passing
- [ ] Documentation is updated

### 2. PR Title Format

Use conventional commits:

```
feat: Add multi-account message routing
fix: Resolve webhook signature validation
docs: Update architecture documentation
test: Add tests for message sender
refactor: Simplify account repository
```

### 3. PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows project architecture
- [ ] All operations are account-scoped
- [ ] Credentials are encrypted
- [ ] Error handling is proper
- [ ] Documentation is updated
```

### 4. Automated Reviews

Your PR will automatically get:

1. **Code Quality Checks**
   - Linting (Ruff)
   - Formatting (Black)
   - Type checking (MyPy)
   - Security scan (Bandit)
   - Complexity analysis (Radon)

3. **Test Coverage**
   - Unit test execution
   - Coverage report

### 5. Addressing Review Comments

```bash
# Make changes based on feedback
git add .
git commit -m "fix: Address review comments"
git push origin feature/your-feature-name

# Reviews will automatically re-run
```

## 🧪 Testing Guidelines

### Unit Tests

```python
# tests/test_message_sender.py
import pytest
from app.core.interfaces import IMessageSender
from app.services.message_sender import InstagramMessageSender

@pytest.mark.asyncio
async def test_send_message_success(mock_account_repo):
    sender = InstagramMessageSender(mock_account_repo)
    result = await sender.send_message(
        account_id="test_account",
        recipient_id="test_user",
        message_text="Hello"
    )
    assert result.success is True
```

### Integration Tests

```python
# tests/integration/test_webhook_flow.py
@pytest.mark.asyncio
async def test_webhook_to_response_flow(test_client, test_db):
    # Send webhook
    response = await test_client.post(
        "/webhooks/instagram/test_account",
        json=webhook_payload
    )
    assert response.status_code == 200
    
    # Verify message stored
    messages = await message_repo.get_conversation_history(
        "test_account", "conv_123"
    )
    assert len(messages) == 1
```

## 📚 Documentation

### Code Documentation

```python
async def send_message(
    self,
    account_id: str,
    recipient_id: str,
    message_text: str
) -> SendMessageResponse:
    """
    Send a message using account-specific credentials.
    
    Args:
        account_id: Instagram business account ID
        recipient_id: Instagram-scoped ID of recipient
        message_text: Text content of the message
    
    Returns:
        SendMessageResponse with success status and message ID
    
    Raises:
        AccountNotFoundError: If account_id doesn't exist
        InvalidTokenError: If account credentials are invalid
    """
```

### Architecture Documentation

Update relevant docs when making architectural changes:
- `ARCHITECTURE.md` - Overall architecture
- `REFACTORING_PLAN.md` - Migration strategy
- `app/core/README.md` - Core interfaces
- `.kiro/specs/*/design.md` - Detailed design

## 🐛 Reporting Issues

### Bug Reports

Include:
1. Description of the bug
2. Steps to reproduce
3. Expected behavior
4. Actual behavior
5. Environment (OS, Python version)
6. Relevant logs

### Feature Requests

Include:
1. Description of the feature
2. Use case / problem it solves
3. Proposed solution
4. Alternative solutions considered

## 💬 Getting Help

- **Questions**: Open a GitHub Discussion
- **Bugs**: Open a GitHub Issue
- **Security**: Email security concerns privately

## 📜 Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Focus on the code, not the person
- Help others learn and grow

## 🎉 Recognition

Contributors will be:
- Listed in CONTRIBUTORS.md
- Mentioned in release notes
- Credited in documentation

Thank you for contributing! 🚀
