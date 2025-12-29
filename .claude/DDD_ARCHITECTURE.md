# Instagram Messenger Automation - DDD Architecture

**Version**: 2.0 (Post-Refactoring)
**Last Updated**: December 2025
**Status**: ✅ Production-Ready

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Domain-Driven Design Layers](#domain-driven-design-layers)
3. [Core Components](#core-components)
4. [Data Flow Patterns](#data-flow-patterns)
5. [Transaction Management](#transaction-management)
6. [Multi-Account Support](#multi-account-support)
7. [Security Architecture](#security-architecture)
8. [Design Decisions](#design-decisions)
9. [Integration Points](#integration-points)

---

## Architecture Overview

The Instagram Messenger Automation system uses **Domain-Driven Design (DDD)** principles to create a maintainable, testable, and scalable architecture for handling Instagram direct messages across multiple business accounts.

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                             │
├─────────────────────────────────────────────────────────────┤
│  • CRM System (API Client)                                   │
│  • Vue.js Web UI                                             │
│  • Instagram Platform (Webhooks)                             │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                  API/PRESENTATION LAYER                      │
├─────────────────────────────────────────────────────────────┤
│  • FastAPI Endpoints (app/api/)                              │
│    - /webhooks/instagram (receive messages)                  │
│    - /api/v1/messages/send (send messages)                   │
│    - /ui/conversations (web UI)                              │
│    - /api/v1/events/stream (SSE real-time)                   │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│               APPLICATION LAYER                              │
├─────────────────────────────────────────────────────────────┤
│  • MessageService (app/application/message_service.py)       │
│    - Business logic orchestration                            │
│    - Instagram API coordination                              │
│    - Idempotency handling                                    │
│    - Message routing                                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│                  DOMAIN LAYER                                │
├─────────────────────────────────────────────────────────────┤
│  • Entities (app/domain/entities.py)                         │
│    - Message (aggregate root)                                │
│    - Attachment (entity)                                     │
│    - Conversation (read model)                               │
│                                                              │
│  • Value Objects (app/domain/value_objects.py)               │
│    - AccountId, InstagramUserId, MessageId                   │
│    - AttachmentId, IdempotencyKey, MessagingChannelId        │
│                                                              │
│  • Unit of Work (app/domain/unit_of_work.py)                 │
│    - Transaction boundaries                                  │
│    - Repository coordination                                 │
│    - Post-commit hooks                                       │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│              INFRASTRUCTURE LAYER                            │
├─────────────────────────────────────────────────────────────┤
│  • Repositories (app/repositories/)                          │
│    - MessageRepository (SQLAlchemy async)                    │
│    - AccountRepository (account lookup)                      │
│                                                              │
│  • External Clients (app/clients/)                           │
│    - InstagramClient (Graph API)                             │
│                                                              │
│  • Services (app/infrastructure/)                            │
│    - CacheService (TTL + LRU)                                │
│    - EncryptionService (credentials)                         │
│    - MediaDownloader (attachments)                           │
│                                                              │
│  • Database (app/db/)                                        │
│    - SQLite (primary storage)                                │
│    - MySQL (optional CRM sync)                               │
└─────────────────────────────────────────────────────────────┘
```

---

## Domain-Driven Design Layers

### 1. **Domain Layer** (Core Business Logic)

**Location**: `app/domain/`

**Purpose**: Contains business rules, entities, and value objects. This layer is **framework-agnostic** and has no dependencies on FastAPI, SQLAlchemy, or external services.

**Components**:

#### **Entities** (`entities.py`)
- **Message** (Aggregate Root)
  - Enforces invariants: must have text OR attachments, valid direction
  - Owns Attachment entities (cascade delete)
  - Business methods: `mark_as_sent()`, `mark_as_failed()`, `is_within_response_window()`

- **Attachment** (Entity)
  - Part of Message aggregate
  - Validates media type, index consistency
  - Property: `is_downloaded` (checks if local copy exists)

- **Conversation** (Read Model)
  - Computed from messages, not persisted directly
  - For UI display purposes

**Domain Exceptions**:
- `AccountNotFoundError`
- `DuplicateMessageError`
- `InvalidMessageError`

#### **Value Objects** (`value_objects.py`)

Immutable, self-validating types that prevent ID confusion:

| Value Object | Format | Purpose |
|--------------|--------|---------|
| `AccountId` | `acc_xxxx` | Database account ID (internal) |
| `InstagramUserId` | Numeric (17-20 digits) | Instagram PSID |
| `MessagingChannelId` | Numeric | Webhook routing ID |
| `MessageId` | Instagram format | Message identifier |
| `AttachmentId` | `{msg_id}_{index}` | Attachment identifier |
| `IdempotencyKey` | String | Duplicate detection |

**Example**:
```python
# Type safety prevents bugs
account_id = AccountId("acc_123")  # ✅ Valid
account_id = AccountId("123")      # ❌ ValueError: must start with 'acc_'

user_id = InstagramUserId("12345678901234567")  # ✅ Valid
user_id = InstagramUserId("not-numeric")        # ❌ ValueError
```

#### **Unit of Work** (`unit_of_work.py`)

Manages transaction boundaries and coordinates repositories:

```python
async with SQLAlchemyUnitOfWork(db) as uow:
    # All operations in single transaction
    message = await uow.messages.save(message)

    # Schedule side effects AFTER commit
    uow.add_post_commit_hook(lambda: broadcast_sse())

    # Commit triggers post-commit hooks
    await uow.commit()
```

**Key Features**:
- Atomic transactions (all-or-nothing)
- Post-commit hooks prevent race conditions
- Repository access: `uow.messages`, `uow.accounts`

---

### 2. **Application Layer** (Orchestration)

**Location**: `app/application/`

**Purpose**: Orchestrates domain logic, infrastructure, and external services. Contains use case implementations.

#### **MessageService** (`message_service.py`)

Central orchestration service for message operations:

**Methods**:
- `send_message()` - Send outbound message to Instagram user
- `receive_webhook_message()` - Process inbound webhook message
- `get_conversations()` - Fetch conversations with username enrichment
- `auto_reply_to_message()` - Automatic reply logic

**Responsibilities**:
1. Account lookup and token decryption
2. Instagram client creation (per-account)
3. Message validation and persistence
4. Idempotency handling
5. Error handling and failed message tracking

**Example Flow**:
```python
message_service = MessageService()

async with SQLAlchemyUnitOfWork(db) as uow:
    sent_message = await message_service.send_message(
        uow=uow,
        account_id=AccountId("acc_123"),
        recipient_id=InstagramUserId("999888777666"),
        message_text="Thanks for your order!",
        attachment_url="/media/outbound/acc_123/image.jpg",
        attachment_mime_type="image/jpeg",
        idempotency_key=IdempotencyKey("req_xyz")
    )
    # Returns Message domain entity
```

---

### 3. **Infrastructure Layer** (Implementation Details)

**Location**: `app/infrastructure/`, `app/repositories/`, `app/clients/`

**Purpose**: Implements persistence, external API clients, and cross-cutting concerns.

#### **Repositories**

**MessageRepository** (`repositories/message_repository.py`):
- Converts between domain entities and ORM models
- Handles dual storage (SQLite + optional MySQL)
- Query methods: `get_by_id()`, `get_by_idempotency_key()`, `get_conversations_for_account()`

**AccountRepository** (`repositories/account_repository.py`):
- Account lookups by: ID, Instagram ID, messaging channel ID
- Supports multi-account routing

#### **External Clients**

**InstagramClient** (`clients/instagram_client.py`):
- Instagram Graph API integration
- Methods: `send_message()`, `send_message_with_attachment()`, `get_user_profile()`
- Token passed in constructor (per-account instantiation)
- Signature validation for webhooks

#### **Infrastructure Services**

**CacheService** (`infrastructure/cache_service.py`):
- TTL-based cache with LRU eviction
- Default: 24-hour expiration, 10,000 entry limit
- Used for username caching (reduces Instagram API calls)
- Thread-safe with asyncio locks

**EncryptionService** (`services/encryption_service.py`):
- Encrypts/decrypts OAuth tokens and secrets
- Uses session secret from environment

**MediaDownloader** (`services/media_downloader.py`):
- Downloads Instagram CDN media (7-day expiration)
- Stores local copies for persistence

---

### 4. **API/Presentation Layer** (External Interface)

**Location**: `app/api/`

**Purpose**: HTTP endpoints, authentication, request/response handling.

#### **Key Endpoints**

| Endpoint | Purpose | Authentication |
|----------|---------|----------------|
| `POST /webhooks/instagram` | Receive Instagram messages | Signature validation |
| `POST /api/v1/messages/send` | Send message (CRM API) | API Key |
| `GET /ui/conversations` | List conversations (Web UI) | JWT |
| `GET /api/v1/events/stream` | Real-time SSE updates | JWT |
| `POST /ui/session` | Login to web UI | Basic Auth |

**Endpoint Responsibilities** (Simplified Post-Refactoring):
1. Request validation (Pydantic models)
2. Authentication/authorization
3. Call application service (MessageService)
4. Handle HTTP-specific concerns (status codes, responses)
5. Coordinate side effects (SSE broadcasts, CRM tracking)

**Example** (Clean Endpoint Pattern):
```python
@router.post("/send")
async def send_message(
    account_id: str,
    recipient_id: str,
    message: str,
    idempotency_key: str,
    api_key: APIKey = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db_session)
):
    # Create CRM tracking record
    outbound_message = CRMOutboundMessage(...)
    db.add(outbound_message)

    # Delegate to application service
    async with SQLAlchemyUnitOfWork(db) as uow:
        message_service = MessageService()

        sent_message = await message_service.send_message(
            uow=uow,
            account_id=AccountId(account_id),
            recipient_id=InstagramUserId(recipient_id),
            message_text=message,
            idempotency_key=IdempotencyKey(idempotency_key)
        )

        # Update tracking
        outbound_message.status = "sent"
        outbound_message.instagram_message_id = sent_message.id.value

        await uow.commit()

    # Commit CRM tracking
    await db.commit()

    return SendMessageResponse(...)
```

---

## Data Flow Patterns

### Inbound Message Flow (Instagram → System → CRM)

```
┌──────────────┐
│  Instagram   │
│  Platform    │
└──────┬───────┘
       │ POST /webhooks/instagram
       │ (HMAC signature validation)
       ▼
┌──────────────────────┐
│  webhooks.py         │
│  - Validate signature│
│  - Parse payload     │
└──────┬───────────────┘
       │
       ▼
┌───────────────────────────────┐
│  MessageService               │
│  .receive_webhook_message()   │
│  - Route by messaging_channel │
│  - Download attachments       │
│  - Create Message entity      │
└──────┬────────────────────────┘
       │
       ▼
┌────────────────────────┐
│  Unit of Work          │
│  - uow.messages.save() │
│  - Attach SSE hook     │
│  - Commit              │
└──────┬─────────────────┘
       │
       ▼
┌────────────────────────┐
│  Database (SQLite)     │
│  - messages table      │
│  - message_attachments │
└──────┬─────────────────┘
       │ (post-commit)
       ▼
┌────────────────────────┐
│  WebhookForwarder      │
│  - Forward to CRM      │
│  - HMAC signature      │
└────────────────────────┘
       │
       ▼
┌────────────────────────┐
│  SSE Broadcast         │
│  - Real-time UI update │
└────────────────────────┘
```

### Outbound Message Flow (CRM → System → Instagram)

```
┌──────────────┐
│  CRM System  │
└──────┬───────┘
       │ POST /api/v1/messages/send
       │ (Bearer token auth)
       ▼
┌──────────────────────┐
│  messages.py         │
│  - Validate API key  │
│  - Handle file upload│
│  - Create tracking   │
└──────┬───────────────┘
       │
       ▼
┌───────────────────────────────┐
│  MessageService               │
│  .send_message()              │
│  - Check idempotency          │
│  - Get account + decrypt      │
│  - Create Instagram client    │
│  - Detect media type          │
│  - Validate attachment path   │
└──────┬────────────────────────┘
       │
       ▼
┌────────────────────────┐
│  InstagramClient       │
│  - Call Graph API      │
│  - POST /me/messages   │
└──────┬─────────────────┘
       │
       ▼
┌───────────────────────────────┐
│  MessageService               │
│  - Create Message entity      │
│  - Mark as sent/failed        │
└──────┬────────────────────────┘
       │
       ▼
┌────────────────────────┐
│  Unit of Work          │
│  - uow.messages.save() │
│  - Attach SSE hook     │
│  - Commit              │
└──────┬─────────────────┘
       │
       ▼
┌────────────────────────┐
│  Database (SQLite)     │
│  - messages table      │
│  - message_attachments │
└──────┬─────────────────┘
       │ (post-commit)
       ▼
┌────────────────────────┐
│  SSE Broadcast         │
│  - Real-time UI update │
└────────────────────────┘
       │
       ▼
┌────────────────────────┐
│  Endpoint              │
│  - Commit CRM tracking │
│  - Return response     │
└────────────────────────┘
```

---

## Transaction Management

### Unit of Work Pattern

The system uses the **Unit of Work pattern** to ensure:
1. **Atomic operations** - All changes commit together or rollback
2. **Post-commit hooks** - Side effects run AFTER successful commit
3. **Repository coordination** - Single transaction across multiple repositories

**Transaction Lifecycle**:

```python
# 1. Create UoW context
async with SQLAlchemyUnitOfWork(db) as uow:

    # 2. Perform domain operations
    message = await uow.messages.save(message)
    account = await uow.accounts.get_by_id(account_id)

    # 3. Register side effects (run AFTER commit)
    uow.add_post_commit_hook(async_function)

    # 4. Commit (triggers post-commit hooks)
    await uow.commit()

    # Post-commit hooks execute here:
    # - SSE broadcasts
    # - CRM webhook notifications
    # - Cache invalidation
```

**Why Post-Commit Hooks?**

❌ **Problem** (Before):
```python
await db.commit()
await broadcast_sse()  # Race condition! SSE might fire before commit completes
```

✅ **Solution** (After):
```python
uow.add_post_commit_hook(broadcast_sse)
await uow.commit()  # SSE fires AFTER commit success
```

### Dual Storage Pattern

For CRM integration, the system supports dual persistence:

1. **Primary**: SQLite (local, fast, always available)
2. **Secondary**: MySQL (CRM database, network-dependent, best-effort)

**Implementation**:
```python
# MessageRepository handles dual storage
await message_repo.save(message)
# → Writes to SQLite (ACID transaction)
# → Writes to MySQL (best-effort, errors logged but don't fail)
```

**Benefits**:
- CRM gets real-time data in their database
- System remains functional if CRM MySQL is down
- No tight coupling between systems

---

## Multi-Account Support

### Account Routing

The system supports multiple Instagram Business Accounts owned by different users (multi-tenant SaaS model).

**Key Challenge**: Instagram webhooks don't identify which OAuth user owns an account when multiple users link the same Business Account.

**Solution**: Use `messaging_channel_id` for routing.

#### **ID Types** (See `.claude/ACCOUNT_ID_GUIDE.md`)

| ID Type | Format | Source | Purpose |
|---------|--------|--------|---------|
| `account_id` | `acc_xxx` | Database PK | Internal user account |
| `instagram_account_id` | Numeric | OAuth API | Business account ID |
| `messaging_channel_id` | Numeric | Webhook `entry.id` | Routing identifier |
| `sender_id` / `recipient_id` | Numeric | Message payload | Instagram user PSID |

**Routing Logic**:
```python
# Webhook arrives with messaging_channel_id
account = await uow.accounts.get_by_messaging_channel_id(channel_id)

# If not found, fallback to instagram_account_id
if not account:
    account = await uow.accounts.get_by_instagram_id(recipient_id)
```

### Per-Account OAuth Tokens

Each account has its own encrypted access token:

```python
# Account model
class Account(Base):
    id: str  # acc_xxx
    instagram_account_id: str  # Business account ID
    messaging_channel_id: str  # Routing ID (unique)
    access_token_encrypted: str  # OAuth token (encrypted)
    webhook_secret: str  # For signature validation
```

**Instagram Client Creation** (Per-Account):
```python
# Decrypt token
access_token = decrypt_credential(
    account.access_token_encrypted,
    settings.session_secret
)

# Create client with account's token
async with httpx.AsyncClient() as http_client:
    instagram_client = InstagramClient(
        http_client=http_client,
        access_token=access_token,  # Account-specific
        logger_instance=logger
    )

    # Use for this account's operations
    await instagram_client.send_message(...)
```

---

## Security Architecture

### 1. **Credential Encryption**

All sensitive credentials are encrypted at rest:

```python
# Storage
account.access_token_encrypted = encrypt_credential(
    token,
    settings.session_secret
)

# Retrieval
token = decrypt_credential(
    account.access_token_encrypted,
    settings.session_secret
)
```

**Encryption Method**:
- Development: Base64 (placeholder)
- Production: TODO - Fernet symmetric encryption

### 2. **Webhook Signature Validation**

Instagram webhooks are validated using HMAC-SHA256:

```python
def verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    expected = hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(f"sha256={expected}", signature)
```

**Protection Against**:
- Replay attacks
- Unauthorized webhook calls
- Payload tampering

### 3. **Path Traversal Protection**

Attachment paths are validated to prevent directory traversal:

```python
def validate_attachment_path(url: str) -> Optional[str]:
    # Must start with /media/outbound/
    if not url.startswith('/media/outbound/'):
        return None

    # Normalize and check still within safe directory
    normalized = Path(url).resolve()
    if not str(normalized).startswith('/media/outbound/'):
        logger.warning(f"Path traversal attempt: {url}")
        return None

    # Reject paths with .. segments
    if '..' in normalized:
        return None

    return normalized
```

### 4. **Authentication Methods**

| Layer | Method | Use Case |
|-------|--------|----------|
| CRM API | API Key (Bearer token) | `/api/v1/messages/send` |
| Web UI | JWT Session Token | `/ui/conversations` |
| Webhooks | HMAC Signature | `/webhooks/instagram` |

### 5. **Input Validation**

- **Pydantic models** for request validation
- **Value objects** enforce business rules (e.g., AccountId format)
- **File upload limits** (8MB images, 25MB video/audio)
- **MIME type validation** (whitelist of allowed types)

---

## Design Decisions

### 1. **Why Domain-Driven Design?**

**Problem**: Original codebase had "fat controllers" with business logic scattered across endpoints.

**Solution**: DDD provides:
- Clear separation of concerns
- Testable business logic (domain layer has no framework dependencies)
- Maintainability (changes localized to appropriate layers)
- Domain language (ubiquitous language: Message, Attachment, Account)

### 2. **Why Unit of Work Pattern?**

**Problem**: Managing transaction boundaries and side effects was error-prone.

**Solution**: UoW provides:
- Single responsibility for transaction management
- Post-commit hooks prevent race conditions
- Repository coordination
- Easier testing (mock UoW instead of database)

### 3. **Why Value Objects for IDs?**

**Problem**: Mixing up different ID types caused subtle bugs:
```python
# Before (error-prone)
send_message(recipient_id="acc_123")  # Wrong! Passed account ID instead of user ID
```

**Solution**: Value objects provide type safety:
```python
# After (compile-time safety)
send_message(recipient_id=InstagramUserId("123"))  # ✅
send_message(recipient_id=AccountId("acc_123"))   # ❌ Type error
```

### 4. **Why MessageService Creates Instagram Client?**

**Problem**: Endpoint creating client coupled API layer to infrastructure details.

**Solution**: MessageService creates client per-account:
- Supports multi-account (different tokens per account)
- Encapsulates Instagram API details
- Easier to test (mock MessageService, not Instagram client)

### 5. **Why Single Commit Point?**

**Problem**: Multiple commits created inconsistent transaction states.

**Solution**: Single commit after UoW ensures:
- Atomic operations
- Clear transaction boundaries
- Easier debugging (one commit to audit)

---

## Integration Points

### External Systems

1. **Instagram Graph API**
   - Inbound: Webhooks at `/webhooks/instagram`
   - Outbound: REST API at `https://graph.facebook.com/v18.0/me/messages`
   - Authentication: Per-account OAuth tokens

2. **CRM System**
   - Receives: Forwarded webhooks (HMAC-signed)
   - Sends: POST `/api/v1/messages/send` (API Key auth)
   - Optional: Direct MySQL access (dual storage)

3. **Web UI**
   - Framework: Vue 3 + Vite + Tailwind CSS
   - API: RESTful endpoints + SSE for real-time updates
   - Authentication: JWT tokens

### Internal Integrations

1. **Database**
   - Primary: SQLite (async via aiosqlite)
   - Optional: MySQL (CRM sync)
   - Migrations: Alembic

2. **Caching**
   - Username cache: 24-hour TTL, 10K entry LRU
   - Reduces Instagram API calls for profile lookups

3. **Media Storage**
   - Inbound: Downloaded from Instagram CDN → `media/inbound/`
   - Outbound: Uploaded by CRM → `media/outbound/{account_id}/`
   - Served by: FastAPI static file middleware

---

## Performance Characteristics

### Latency

| Operation | Target | Notes |
|-----------|--------|-------|
| Receive webhook | <100ms | No external API calls |
| Send message | <2s | Instagram API latency |
| Load conversations | <500ms | Cached usernames |
| SSE broadcast | <50ms | Post-commit async |

### Scalability

**Current**:
- Single-server deployment
- Async I/O handles 1000+ concurrent connections
- SQLite supports 50-100 writes/sec

**Future** (if needed):
- Horizontal scaling with Redis for shared cache
- PostgreSQL for higher write throughput
- Message queue (RabbitMQ) for async processing

### Caching Strategy

```python
# Username Cache
TTL: 24 hours
Max Size: 10,000 entries
Eviction: LRU (Least Recently Used)
Hit Rate Target: >80%
```

---

## Testing Strategy

### Unit Tests (Domain Layer)

```python
# test_entities.py
def test_message_must_have_content():
    with pytest.raises(ValueError, match="must have text or attachments"):
        Message(
            id=MessageId("mid_123"),
            account_id=AccountId("acc_123"),
            sender_id=InstagramUserId("999"),
            recipient_id=InstagramUserId("888"),
            message_text=None,  # No text
            direction="inbound",
            timestamp=datetime.now(),
            attachments=[]  # No attachments
        )
```

### Integration Tests (Application Layer)

```python
# test_message_service.py
@pytest.mark.asyncio
async def test_send_message_idempotency():
    # Arrange
    service = MessageService()
    idempotency_key = IdempotencyKey("test_123")

    # Act - send twice with same key
    msg1 = await service.send_message(..., idempotency_key=idempotency_key)
    msg2 = await service.send_message(..., idempotency_key=idempotency_key)

    # Assert - returns same message
    assert msg1.id == msg2.id
```

### API Tests (E2E)

```python
# test_messages_api.py
@pytest.mark.asyncio
async def test_send_message_endpoint():
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/messages/send",
            headers={"Authorization": "Bearer test_key"},
            json={
                "account_id": "acc_123",
                "recipient_id": "999888777",
                "message": "Test",
                "idempotency_key": "test_123"
            }
        )
        assert response.status_code == 200
        assert response.json()["status"] == "sent"
```

---

## Deployment Architecture

### Production Deployment (VPS)

```
┌─────────────────────────────────────┐
│  Nginx (Reverse Proxy)              │
│  - SSL termination                  │
│  - Static file serving              │
│  - Rate limiting                    │
└─────────┬───────────────────────────┘
          │
┌─────────▼───────────────────────────┐
│  FastAPI (Uvicorn)                  │
│  - Port 8000                        │
│  - 4 worker processes               │
│  - Auto-reload disabled             │
└─────────┬───────────────────────────┘
          │
┌─────────▼───────────────────────────┐
│  SQLite Database                    │
│  - WAL mode (concurrent reads)      │
│  - Automatic backups                │
└─────────────────────────────────────┘
```

### Environment Configuration

**Development**:
```
DATABASE_URL=sqlite+aiosqlite:///./dev.db
LOG_LEVEL=DEBUG
PUBLIC_BASE_URL=https://abc123.ngrok.io
```

**Production**:
```
DATABASE_URL=sqlite+aiosqlite:///./data/production.db
LOG_LEVEL=INFO
PUBLIC_BASE_URL=https://yourdomain.com
SESSION_SECRET=<secure-random-string>
```

---

## Monitoring & Observability

### Logging

```python
logger.info(f"📨 Received webhook message: {message.id}")
logger.info(f"📤 Sent to Instagram: message_id={ig_response.message_id}")
logger.warning(f"⚠️ Path traversal attempt detected: {url}")
logger.error(f"❌ Failed to send message: {error}")
```

**Log Levels**:
- DEBUG: Development only
- INFO: Production (normal operations)
- WARNING: Security events, retryable errors
- ERROR: Failed operations, exceptions

### Metrics (Future)

- Message throughput (messages/minute)
- Instagram API latency
- Cache hit rate
- Error rate by type
- Active SSE connections

---

## Future Enhancements

### Planned (Priority 2)

1. **Enhanced Encryption**
   - Replace Base64 with Fernet symmetric encryption
   - Key rotation support

2. **Read/Unread Tracking**
   - Track message read status
   - Unread count per conversation

3. **Message Timestamps**
   - `sent_at`, `delivered_at`, `read_at` fields
   - Instagram read receipts

4. **Rate Limiting**
   - Per-account rate limits
   - Global rate limiting middleware

### Considered (Future)

1. **Event Sourcing**
   - Event log for audit trail
   - Replay capability for testing

2. **CQRS Pattern**
   - Separate read/write models
   - Optimized queries for UI

3. **Saga Pattern**
   - Distributed transaction handling
   - Compensating transactions

---

## References

- **CLAUDE.md**: Project setup and development guide
- **ACCOUNT_ID_GUIDE.md**: Detailed explanation of ID types
- **CODEBASE_ARCHITECTURE.md**: Legacy architecture documentation
- **Plan**: `C:\Users\tol13\.claude\plans\adaptive-weaving-puppy.md`

---

## Changelog

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | Dec 2025 | DDD refactoring complete, bug fixes applied |
| 1.5 | Nov 2025 | Multi-account support, OAuth integration |
| 1.0 | Nov 2025 | Initial MVP with single account |

---

**Document Maintained By**: Development Team
**Review Cycle**: Quarterly or after major architectural changes
