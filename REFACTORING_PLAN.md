# Architecture Refactoring Plan

## Overview

This document outlines the refactoring from the MVP implementation to a production-ready, multi-account architecture.

## Current Issues (MVP)

### ❌ **Problems:**
1. **Hardcoded User IDs**: Test script has hardcoded Instagram user IDs
2. **Single Account**: Only supports one Instagram business account (@ser_bain)
3. **Environment Variables**: Credentials stored in .env file
4. **No Database**: No persistence for messages, conversations, or accounts
5. **Tight Coupling**: Direct API calls without abstraction
6. **No Interfaces**: No proper separation of concerns

### Current MVP Code Structure:
```
app/
├── main.py              # FastAPI app
├── config.py            # Loads env variables
└── api/
    └── webhooks.py      # Webhook endpoints

test_send_message.py     # Hardcoded user IDs
.env                     # All credentials here
```

## Target Architecture

### ✅ **Solutions:**
1. **Multi-Account Support**: Store multiple Instagram business accounts in database
2. **Proper Interfaces**: IMessageReceiver, IMessageSender abstractions
3. **Database-First**: MySQL storage for accounts, messages, conversations
4. **Encrypted Credentials**: Store tokens encrypted in database
5. **Account-Scoped Operations**: All operations linked to specific accounts
6. **Clean Separation**: Repository pattern, dependency injection

### Target Code Structure:
```
app/
├── core/
│   ├── interfaces.py         # IMessageReceiver, IMessageSender, etc.
│   ├── config.py             # Minimal env vars (DB, encryption key)
│   └── dependencies.py       # Dependency injection
├── models/
│   └── models.py             # SQLAlchemy models
├── repositories/
│   ├── account_repository.py
│   ├── message_repository.py
│   └── conversation_repository.py
├── services/
│   ├── message_receiver.py   # Implements IMessageReceiver
│   ├── message_sender.py     # Implements IMessageSender
│   └── response_engine.py
├── api/
│   ├── webhooks.py           # Account-aware webhooks
│   └── accounts.py           # Account management API
└── utils/
    └── encryption.py         # Credential encryption

alembic/                      # Database migrations
```

## Key Changes

### 1. Configuration Management

**Before (MVP):**
```env
FACEBOOK_VERIFY_TOKEN=my_token
FACEBOOK_APP_SECRET=my_secret
INSTAGRAM_PAGE_ACCESS_TOKEN=my_access_token
```

**After (Target):**
```env
# Only database and encryption key
MYSQL_HOST=localhost
MYSQL_DATABASE=instagram_automation
MYSQL_USERNAME=app_user
MYSQL_PASSWORD=secure_password
APP_SECRET_KEY=encryption-key
```

Instagram credentials stored in database (encrypted).

### 2. Message Sending

**Before (MVP):**
```python
# test_send_message.py
USER_IDS = {
    "@ser_bain": "1180376147344794",
    "@tol1306": "1558635688632972",
}

async def send_test_message(recipient_username: str, message_text: str):
    recipient_id = USER_IDS[recipient_username]
    url = "https://graph.instagram.com/v21.0/me/messages"
    headers = {
        "Authorization": f"Bearer {settings.instagram_page_access_token}"
    }
    # Direct API call
```

**After (Target):**
```python
# Using IMessageSender interface
class InstagramMessageSender(IMessageSender):
    async def send_message(
        self, 
        account_id: str,
        recipient_id: str, 
        message_text: str
    ) -> MessageResult:
        # Get account from database
        account = await account_repo.get_by_id(account_id)
        # Decrypt token
        token = decrypt_token(account.access_token_encrypted)
        # Send using account-specific credentials
        ...

# Usage
await message_sender.send_message(
    account_id="ser_bain_account_id",
    recipient_id="1558635688632972",
    message_text="Hello!"
)
```

### 3. Webhook Processing

**Before (MVP):**
```python
@router.post("/instagram")
async def handle_webhook(request: Request):
    body = await request.json()
    # Process with hardcoded credentials
    # No signature validation
    # No account routing
```

**After (Target):**
```python
@router.post("/instagram/{account_id}")
async def handle_webhook(
    account_id: str,
    request: Request,
    message_receiver: IMessageReceiver = Depends(get_message_receiver)
):
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")
    
    # Validate signature using account-specific secret
    if not await message_receiver.validate_signature(account_id, signature, body):
        raise HTTPException(status_code=401)
    
    # Process message for specific account
    await message_receiver.receive_webhook(account_id, body)
```

### 4. Database Models

**New Tables:**

```sql
-- Store multiple Instagram accounts
CREATE TABLE instagram_business_accounts (
    id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    access_token_encrypted TEXT NOT NULL,
    app_secret_encrypted TEXT NOT NULL,
    webhook_verify_token VARCHAR(100) NOT NULL,
    status ENUM('active', 'inactive') DEFAULT 'active',
    ...
);

-- Messages linked to accounts
CREATE TABLE messages (
    id VARCHAR(100) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    conversation_id VARCHAR(100) NOT NULL,
    direction ENUM('inbound', 'outbound'),
    message_text TEXT,
    ...
    FOREIGN KEY (account_id) REFERENCES instagram_business_accounts(id)
);

-- Conversations per account
CREATE TABLE conversations (
    id VARCHAR(100) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    participant_id VARCHAR(50) NOT NULL,
    ...
    FOREIGN KEY (account_id) REFERENCES instagram_business_accounts(id)
);

-- Response rules per account
CREATE TABLE response_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    trigger_value TEXT NOT NULL,
    response_template TEXT NOT NULL,
    ...
    FOREIGN KEY (account_id) REFERENCES instagram_business_accounts(id)
);
```

## Implementation Phases

### Phase 1: Core Infrastructure (Tasks 1-3)
- Set up MySQL database
- Create SQLAlchemy models
- Implement credential encryption
- Define core interfaces

### Phase 2: Account Management (Tasks 4-6)
- Implement AccountRepository
- Create account management API
- Seed initial account data

### Phase 3: Message Receiving (Tasks 7-9)
- Implement IMessageReceiver
- Create message/conversation repositories
- Update webhook endpoints for account routing

### Phase 4: Message Sending (Tasks 10-12)
- Implement IMessageSender
- Integrate into webhook flow
- Update test script

### Phase 5: Response Engine (Tasks 13-15)
- Implement account-scoped rule repository
- Create response engine
- Integrate into message flow

### Phase 6: Configuration & Deployment (Tasks 16-18)
- Update configuration management
- Add health checks
- Create deployment documentation

### Phase 7: Testing (Tasks 19-20) - Optional
- Unit tests for core components
- Integration tests for workflows

## Migration Strategy

### Step 1: Keep MVP Running
- Don't break existing functionality
- Run both old and new code paths in parallel

### Step 2: Migrate Data
- Create database tables
- Seed with existing @ser_bain account
- Encrypt and store current credentials

### Step 3: Switch Over
- Update webhook URLs to use new endpoints
- Deprecate old environment variables
- Remove hardcoded values

### Step 4: Cleanup
- Remove old code paths
- Update documentation
- Archive MVP implementation

## Benefits of New Architecture

### ✅ **Scalability**
- Support unlimited Instagram business accounts
- Each account isolated and secure
- Easy to add new accounts via API

### ✅ **Maintainability**
- Clean interfaces enable easy testing
- Repository pattern separates data access
- Dependency injection makes components swappable

### ✅ **Security**
- Encrypted credential storage
- Account-specific access control
- Audit trail for all operations

### ✅ **Flexibility**
- Account-specific business logic
- Configurable response rules per account
- Easy integration with existing systems

## Next Steps

1. Review and approve this refactoring plan
2. Start with Phase 1: Database setup
3. Implement incrementally, testing each phase
4. Migrate existing @ser_bain account to database
5. Test multi-account support with second account
6. Deploy to production

## Questions to Consider

1. **MySQL Setup**: Do you have MySQL installed locally? Need setup instructions?
2. **Existing Database**: Will you use an existing MySQL database or create new one?
3. **Account Migration**: Should we migrate @ser_bain account first or start fresh?
4. **Testing Strategy**: Want to implement tests (Phase 7) or skip for MVP?
5. **Deployment**: Railway or custom Linux server for production?
