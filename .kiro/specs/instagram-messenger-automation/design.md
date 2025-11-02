# Design Document

## Overview

The Instagram Messenger Automation system is a Python-based webhook server that receives Instagram Direct Messages via Facebook's Messenger Platform API and automatically responds to customers. The system uses FastAPI for high-performance async webhook handling, MySQL for persistent storage, and is designed to support multiple Instagram business accounts with proper interface abstractions. The architecture is built around clean interfaces (IMessageReceiver, IMessageSender) that separate concerns and enable easy testing and future enhancements.

### Key Design Principles
- **Multi-Account First**: Support multiple Instagram business accounts from the start
- **Interface-Driven**: Program to interfaces (IMessageReceiver, IMessageSender), not implementations
- **Database-First**: All configuration stored in MySQL, not environment variables
- **Account-Scoped**: All operations linked to specific Instagram business accounts
- **Loose Coupling**: Components communicate through well-defined contracts
- **Fail-safe**: Always acknowledge webhooks within 20 seconds, even if processing fails
- **Secure by Default**: Encrypted credential storage, account isolation

### Modularity Benefits
This design allows you to:
- Replace the response engine (keyword → AI) without touching other components
- Swap databases (PostgreSQL → MongoDB) by implementing the repository interface
- Switch messaging platforms (Instagram → WhatsApp) by implementing the client interface
- Test components in isolation with mocked dependencies
- Understand exactly what breaks when you change a component

### MVP Scope (What We're Building)
✅ Webhook verification and message reception
✅ Basic keyword-based response matching
✅ Send replies via Instagram API
✅ Store messages in PostgreSQL
✅ Simple conversation tracking
✅ Environment-based configuration
✅ Basic error logging

### Out of Scope (Add Later If Needed)
❌ Admin dashboard
❌ Analytics and reporting
❌ Multi-language support
❌ Rich media (images, buttons)
❌ Human handoff/escalation
❌ Rate limiting middleware
❌ Message queuing system
❌ Sentiment analysis
❌ Advanced retry logic with circuit breakers

## Architecture

### High-Level Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Webhook API   │────│  Message Router  │────│ Instagram APIs  │
│  (per account)  │    │  (IMessageRcvr)  │    │ (IMessageSndr)  │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         └──────────────│ Account Manager │──────────────┘
                        │  (Repository)   │
                        └─────────────────┘
                                 │
                        ┌─────────────────┐
                        │ MySQL Database  │
                        │ - Accounts      │
                        │ - Messages      │
                        │ - Conversations │
                        │ - Rules         │
                        └─────────────────┘
```

### Component Layers

1. **API Layer** (FastAPI)
   - Webhook endpoints (account-aware verification & message handling)
   - Account management endpoints (CRUD for Instagram accounts)
   - Health check endpoints

2. **Interface Layer** (Abstractions)
   - IMessageReceiver: Webhook processing interface
   - IMessageSender: Message sending interface
   - IAccountRepository: Account data access interface

3. **Business Logic Layer**
   - Account-scoped message processor
   - Account-specific response rules engine
   - Message routing logic

4. **Data Layer**
   - MySQL database with SQLAlchemy ORM
   - Account repository (encrypted credentials)
   - Message repository (account-scoped)
   - Conversation repository (account-scoped)

5. **Infrastructure Layer**
   - Configuration management (minimal env vars)
   - Credential encryption/decryption
   - Logging and monitoring
   - Error handling middleware

## Components and Interfaces

### Module Structure

```
app/
├── core/                    # Core abstractions and interfaces
│   ├── interfaces.py        # Abstract base classes (contracts)
│   ├── config.py           # Configuration management
│   └── dependencies.py     # Dependency injection setup
├── api/                    # API layer (FastAPI routes)
│   └── webhooks.py         # Webhook endpoints
├── services/               # Business logic implementations
│   ├── message_processor.py
│   └── response_engine.py
├── clients/                # External API clients
│   └── instagram_client.py
├── repositories/           # Data access layer
│   ├── message_repository.py
│   ├── conversation_repository.py
│   └── rule_repository.py
├── models/                 # Database models (SQLAlchemy)
│   └── models.py
└── utils/                  # Utilities
    ├── signature_validator.py
    └── logger.py
```

### Core Interfaces (`app/core/interfaces.py`)

These abstract base classes define the contracts that all implementations must follow:

```python
from abc import ABC, abstractmethod
from typing import List, Optional

# Account-Aware Message Receiver Interface
class IMessageReceiver(ABC):
    @abstractmethod
    async def receive_webhook(self, account_id: str, payload: dict) -> None:
        """Process incoming webhook for specific account"""
        pass
    
    @abstractmethod
    async def validate_signature(self, account_id: str, signature: str, body: str) -> bool:
        """Validate webhook signature using account-specific secret"""
        pass
    
    @abstractmethod
    async def process_message(self, account_id: str, message: InboundMessage) -> None:
        """Handle a single incoming message for specific account"""
        pass

# Account-Aware Message Sender Interface
class IMessageSender(ABC):
    @abstractmethod
    async def send_message(
        self, 
        account_id: str,
        recipient_id: str, 
        message_text: str
    ) -> SendMessageResponse:
        """Send message using specific account credentials"""
        pass
    
    @abstractmethod
    async def send_template(
        self, 
        account_id: str,
        recipient_id: str, 
        template_id: str,
        params: dict
    ) -> SendMessageResponse:
        """Send template message using specific account"""
        pass

# Account Repository Interface
class IAccountRepository(ABC):
    @abstractmethod
    async def get_by_id(self, account_id: str) -> Optional[InstagramBusinessAccount]:
        """Get account by ID"""
        pass
    
    @abstractmethod
    async def get_by_username(self, username: str) -> Optional[InstagramBusinessAccount]:
        """Get account by username"""
        pass
    
    @abstractmethod
    async def create(self, account: InstagramBusinessAccount) -> InstagramBusinessAccount:
        """Create new account"""
        pass
    
    @abstractmethod
    async def update(self, account: InstagramBusinessAccount) -> InstagramBusinessAccount:
        """Update existing account"""
        pass
    
    @abstractmethod
    async def get_active_accounts(self) -> List[InstagramBusinessAccount]:
        """Get all active accounts"""
        pass

# Message Repository Interface (Account-Scoped)
class IMessageRepository(ABC):
    @abstractmethod
    async def create(self, account_id: str, message: Message) -> Message:
        """Store message for specific account"""
        pass
    
    @abstractmethod
    async def get_conversation_history(
        self, 
        account_id: str,
        conversation_id: str, 
        limit: int = 10
    ) -> List[Message]:
        """Get conversation history for specific account"""
        pass

# Conversation Repository Interface (Account-Scoped)
class IConversationRepository(ABC):
    @abstractmethod
    async def get_or_create(
        self, 
        account_id: str,
        participant_id: str
    ) -> Conversation:
        """Get or create conversation for specific account"""
        pass
    
    @abstractmethod
    async def update_last_message_time(
        self, 
        account_id: str,
        conversation_id: str
    ) -> None:
        """Update last message timestamp"""
        pass

# Rule Repository Interface (Account-Scoped)
class IRuleRepository(ABC):
    @abstractmethod
    async def get_active_rules(self, account_id: str) -> List[ResponseRule]:
        """Get active rules for specific account"""
        pass
    
    @abstractmethod
    async def find_matching_rule(
        self, 
        account_id: str,
        message_text: str
    ) -> Optional[ResponseRule]:
        """Find matching rule for specific account"""
        pass
```

### 1. Webhook Handler (`app/api/webhooks.py`)

**Responsibilities:**
- Handle GET requests for webhook verification
- Handle POST requests for incoming messages
- Delegate processing to message processor
- Acknowledge requests within 20 seconds

**Dependencies (Injected):**
- `IMessageProcessor`: Processes webhook events
- `IMessagingClient`: Validates webhook signatures
- `Settings`: Configuration

**Key Methods:**
```python
async def verify_webhook(
    mode: str,
    token: str,
    challenge: str,
    settings: Settings = Depends(get_settings)
) -> Response

async def handle_webhook(
    request: Request,
    signature: str,
    message_processor: IMessageProcessor = Depends(get_message_processor),
    messaging_client: IMessagingClient = Depends(get_messaging_client)
) -> Response
```

**Interface Contract:**
- Input: HTTP requests from Facebook
- Output: HTTP 200 responses
- Side Effects: Triggers async message processing
- Error Handling: Always returns 200, logs errors internally

### 2. Message Processor (`app/services/message_processor.py`)

**Implementation:** `MessageProcessor` implements `IMessageProcessor`

**Responsibilities:**
- Parse webhook payload
- Extract message data (sender, text, timestamp)
- Store messages in database
- Trigger response generation
- Handle different message types (text, media, story replies)

**Dependencies (Injected via Constructor):**
```python
class MessageProcessor(IMessageProcessor):
    def __init__(
        self,
        message_repo: IMessageRepository,
        conversation_repo: IConversationRepository,
        response_engine: IResponseEngine,
        messaging_client: IMessagingClient,
        logger: Logger
    ):
        self._message_repo = message_repo
        self._conversation_repo = conversation_repo
        self._response_engine = response_engine
        self._messaging_client = messaging_client
        self._logger = logger
```

**Key Methods:**
```python
async def process_webhook_event(self, event: dict) -> None
async def extract_messages(self, payload: dict) -> List[IncomingMessage]
async def handle_message(self, message: IncomingMessage) -> None
```

**Interface Contract:**
- Input: Webhook event payload (dict)
- Output: None (side effects: DB writes, API calls)
- Error Handling: Catches all exceptions, logs, continues processing
- Guarantees: Always completes within 20 seconds

**Swappable:** Can replace with `AIMessageProcessor` that adds intent classification without changing other components

### 3. Response Engine (`app/services/response_engine.py`)

**Implementation:** `KeywordResponseEngine` implements `IResponseEngine`

**Responsibilities:**
- Match incoming messages against response rules (simple keyword contains)
- Provide fallback response if no match

**Dependencies (Injected via Constructor):**
```python
class KeywordResponseEngine(IResponseEngine):
    def __init__(
        self,
        rule_repo: IRuleRepository,
        logger: Logger
    ):
        self._rule_repo = rule_repo
        self._logger = logger
```

**Key Methods:**
```python
async def generate_response(
    self,
    message: IncomingMessage,
    conversation_history: List[Message]
) -> str
```

**Interface Contract:**
- Input: IncomingMessage, conversation history
- Output: Response text (string)
- Error Handling: Returns fallback response on any error
- Guarantees: Always returns a valid response string

**MVP Note:** Simple case-insensitive keyword matching. No regex, no priority, no complex logic. Add later if needed.

**Swappable:** Later replace with `AIResponseEngine` for GPT-based responses

### 4. Instagram Client (`app/clients/instagram_client.py`)

**Implementation:** `InstagramClient` implements `IMessagingClient`

**Responsibilities:**
- Send messages via Instagram Send API
- Validate webhook signatures
- Basic error handling (log and raise)

**Dependencies (Injected via Constructor):**
```python
class InstagramClient(IMessagingClient):
    def __init__(
        self,
        http_client: httpx.AsyncClient,
        settings: Settings,
        logger: Logger
    ):
        self._http_client = http_client
        self._settings = settings
        self._logger = logger
        self._api_base_url = "https://graph.facebook.com/v18.0"
```

**Key Methods:**
```python
async def send_message(
    self,
    recipient_id: str,
    message_text: str
) -> SendMessageResponse

async def validate_webhook_signature(
    self,
    payload: str,
    signature: str
) -> bool
```

**Interface Contract:**
- Input: Recipient ID, message content
- Output: SendMessageResponse with status
- Error Handling: Logs error and raises exception (no retry logic in MVP)
- Guarantees: Idempotent operations

**MVP Note:** Start with simple send + log errors. Add retry logic and rate limiting only if needed.

### 5. Database Models (`app/models/`)

**InstagramBusinessAccount Model:**
```python
class InstagramBusinessAccount(Base):
    id: str  # Instagram account ID
    username: str
    display_name: str
    access_token_encrypted: str  # Encrypted with APP_SECRET_KEY
    app_secret_encrypted: str  # Encrypted with APP_SECRET_KEY
    webhook_verify_token: str
    status: AccountStatus  # active/inactive/suspended
    settings: JSON
    created_at: datetime
    updated_at: datetime
```

**Message Model (Account-Scoped):**
```python
class Message(Base):
    id: str  # Message ID from Instagram
    account_id: str  # FK to InstagramBusinessAccount
    conversation_id: str
    sender_id: str
    recipient_id: str
    message_text: str
    message_type: MessageType
    direction: MessageDirection  # inbound/outbound
    timestamp: datetime
    status: MessageStatus
    metadata: JSON
    created_at: datetime
```

**Conversation Model (Account-Scoped):**
```python
class Conversation(Base):
    id: str  # Conversation ID
    account_id: str  # FK to InstagramBusinessAccount
    participant_id: str  # Instagram user ID
    participant_username: str
    status: ConversationStatus  # active/archived/blocked
    last_message_at: datetime
    message_count: int
    metadata: JSON
    created_at: datetime
```

**ResponseRule Model (Account-Scoped):**
```python
class ResponseRule(Base):
    id: int  # Auto-increment
    account_id: str  # FK to InstagramBusinessAccount
    name: str
    trigger_type: TriggerType  # keyword/pattern/intent
    trigger_value: str
    response_template: str
    priority: int
    is_active: bool
    conditions: JSON
    created_at: datetime
```

### 5. Repository Implementations (`app/repositories/`)

**Implementations:**
- `MessageRepository` implements `IMessageRepository`
- `ConversationRepository` implements `IConversationRepository`
- `RuleRepository` implements `IRuleRepository`

**Dependencies (Injected via Constructor):**
```python
class MessageRepository(IMessageRepository):
    def __init__(self, db_session: AsyncSession):
        self._db = db_session

class ConversationRepository(IConversationRepository):
    def __init__(self, db_session: AsyncSession):
        self._db = db_session

class RuleRepository(IRuleRepository):
    def __init__(self, db_session: AsyncSession):
        self._db = db_session
```

**Interface Contract:**
- Input: Domain objects (Message, Conversation, ResponseRule)
- Output: Domain objects or None
- Error Handling: Raises repository-specific exceptions
- Guarantees: Transactional consistency

**Swappable Implementations:**
- `SQLAlchemyMessageRepository`: Current (PostgreSQL via SQLAlchemy)
- `MongoMessageRepository`: MongoDB implementation
- `RedisMessageRepository`: Redis for caching
- `InMemoryMessageRepository`: For testing

**Example Swap:**
```python
# Easy to switch from PostgreSQL to MongoDB
# Just implement the same interface
class MongoMessageRepository(IMessageRepository):
    def __init__(self, mongo_client: MongoClient):
        self._db = mongo_client
    
    async def create(self, message: Message) -> Message:
        # MongoDB-specific implementation
        pass
```

### 6. Dependency Injection Setup (`app/core/dependencies.py`)

**Purpose:** Wire up all dependencies and enable easy swapping

```python
from functools import lru_cache
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession

# Singleton configuration
@lru_cache()
def get_settings() -> Settings:
    return Settings()

# Database session
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session

# Repositories
def get_message_repository(
    db: AsyncSession = Depends(get_db_session)
) -> IMessageRepository:
    return MessageRepository(db)

def get_conversation_repository(
    db: AsyncSession = Depends(get_db_session)
) -> IConversationRepository:
    return ConversationRepository(db)

def get_rule_repository(
    db: AsyncSession = Depends(get_db_session)
) -> IRuleRepository:
    return RuleRepository(db)

# Response Engine
def get_response_engine(
    rule_repo: IRuleRepository = Depends(get_rule_repository)
) -> IResponseEngine:
    # Easy to swap: just change the implementation here
    return KeywordResponseEngine(rule_repo, get_logger())

# Messaging Client
def get_messaging_client(
    settings: Settings = Depends(get_settings)
) -> IMessagingClient:
    http_client = httpx.AsyncClient()
    return InstagramClient(http_client, settings, get_logger())

# Message Processor
def get_message_processor(
    message_repo: IMessageRepository = Depends(get_message_repository),
    conversation_repo: IConversationRepository = Depends(get_conversation_repository),
    response_engine: IResponseEngine = Depends(get_response_engine),
    messaging_client: IMessagingClient = Depends(get_messaging_client)
) -> IMessageProcessor:
    return MessageProcessor(
        message_repo,
        conversation_repo,
        response_engine,
        messaging_client,
        get_logger()
    )
```

**Benefits:**
- Change one line to swap implementations
- Easy to mock for testing
- Clear dependency graph
- Type-safe with FastAPI's Depends

### 7. Configuration Service (`app/core/config.py`)

**Responsibilities:**
- Load minimal environment variables (database, encryption key)
- Validate required configuration
- Provide typed configuration access

**Configuration Schema:**
```python
class Settings(BaseSettings):
    # App
    app_name: str = "Instagram Messenger Automation"
    environment: str = "development"
    debug: bool = False
    
    # Database (MySQL)
    mysql_host: str
    mysql_port: int = 3306
    mysql_database: str
    mysql_username: str
    mysql_password: str
    
    # Security
    app_secret_key: str  # For encrypting account credentials
    
    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Logging
    log_level: str = "INFO"
    
    @property
    def database_url(self) -> str:
        return f"mysql+aiomysql://{self.mysql_username}:{self.mysql_password}@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
```

**Note:** Instagram account credentials (access tokens, app secrets, verify tokens) are stored in the database, not environment variables.

## Data Models

### Database Schema

**instagram_business_accounts table:**
```sql
CREATE TABLE instagram_business_accounts (
    id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(200),
    access_token_encrypted TEXT NOT NULL,
    app_secret_encrypted TEXT NOT NULL,
    webhook_verify_token VARCHAR(100) NOT NULL,
    status ENUM('active', 'inactive', 'suspended') DEFAULT 'active',
    settings JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_status (status)
);
```

**messages table:**
```sql
CREATE TABLE messages (
    id VARCHAR(100) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    conversation_id VARCHAR(100) NOT NULL,
    direction ENUM('inbound', 'outbound') NOT NULL,
    sender_id VARCHAR(50),
    recipient_id VARCHAR(50),
    message_text TEXT,
    message_type VARCHAR(50) DEFAULT 'text',
    metadata JSON,
    status VARCHAR(50) DEFAULT 'delivered',
    timestamp TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES instagram_business_accounts(id),
    INDEX idx_account_conversation (account_id, conversation_id),
    INDEX idx_timestamp (timestamp)
);
```

**conversations table:**
```sql
CREATE TABLE conversations (
    id VARCHAR(100) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    participant_id VARCHAR(50) NOT NULL,
    participant_username VARCHAR(100),
    status ENUM('active', 'archived', 'blocked') DEFAULT 'active',
    last_message_at TIMESTAMP,
    message_count INT DEFAULT 0,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES instagram_business_accounts(id),
    UNIQUE KEY unique_account_participant (account_id, participant_id),
    INDEX idx_account_id (account_id),
    INDEX idx_last_message_at (last_message_at)
);
```

**response_rules table:**
```sql
CREATE TABLE response_rules (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    name VARCHAR(200) NOT NULL,
    trigger_type ENUM('keyword', 'pattern', 'intent') NOT NULL,
    trigger_value TEXT NOT NULL,
    response_template TEXT NOT NULL,
    priority INT DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    conditions JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES instagram_business_accounts(id),
    INDEX idx_account_active (account_id, is_active)
);
```

### Message Flow Data

**Incoming Webhook Payload (from Facebook):**
```json
{
  "object": "instagram",
  "entry": [{
    "id": "page-id",
    "time": 1234567890,
    "messaging": [{
      "sender": {"id": "user-psid"},
      "recipient": {"id": "page-id"},
      "timestamp": 1234567890,
      "message": {
        "mid": "message-id",
        "text": "Hello, I want to order a product"
      }
    }]
  }]
}
```

**Outgoing Send API Request:**
```json
{
  "recipient": {"id": "user-psid"},
  "message": {
    "text": "Hi! Thanks for reaching out. How can I help you today?"
  }
}
```

## Error Handling

### Error Categories and Strategies

1. **Webhook Validation Errors**
   - Invalid signature → Return 401, log security event
   - Missing parameters → Return 400, log validation error
   - Strategy: Fail fast, don't process invalid requests

2. **Message Processing Errors**
   - Database connection failure → Queue message in memory, retry
   - Parsing error → Log error, return 200 to prevent retries
   - Strategy: Always acknowledge webhook, handle errors async

3. **Send API Errors**
   - Rate limit (code 4) → Queue message, retry after window
   - Invalid token (code 190) → Alert admin, stop processing
   - Temporary failure (code 2) → Retry with exponential backoff
   - Strategy: Implement retry logic with circuit breaker

4. **Database Errors**
   - Connection timeout → Retry with exponential backoff (max 3 attempts)
   - Constraint violation → Log and skip duplicate messages
   - Strategy: Graceful degradation, continue processing

### Error Response Format

```python
class ErrorResponse(BaseModel):
    error: str
    message: str
    timestamp: datetime
    request_id: str
```

### Logging Strategy

- **Structured logging** with contextual information
- **Log levels:**
  - DEBUG: Detailed webhook payloads (dev only)
  - INFO: Message received/sent events
  - WARNING: Retry attempts, rate limits
  - ERROR: Processing failures, API errors
  - CRITICAL: System failures, security events

## Testing Strategy

### 1. Unit Tests

**Coverage Areas:**
- Signature validation logic
- Message parsing and extraction
- Response rule matching
- Configuration validation

**Tools:**
- pytest for test framework
- pytest-asyncio for async tests
- pytest-mock for mocking
- faker for test data generation

**Example Test:**
```python
async def test_signature_validation():
    validator = SignatureValidator(app_secret="test-secret")
    payload = '{"test": "data"}'
    signature = validator.generate_signature(payload)
    
    assert validator.validate(payload, signature) is True
    assert validator.validate(payload, "invalid") is False
```

### 2. Integration Tests

**Coverage Areas:**
- Webhook endpoint flow (verification + message handling)
- Database operations (CRUD for messages, conversations)
- Instagram API client (with mocked responses)

**Tools:**
- TestClient from FastAPI
- pytest fixtures for database setup
- httpx-mock for API mocking

### 3. Local Development Testing

**Setup:**
1. Run FastAPI server locally on Windows 11
2. Use ngrok to create public HTTPS tunnel
3. Configure Facebook webhook with ngrok URL
4. Test with Instagram test users

**ngrok Command:**
```bash
ngrok http 8000
```

**Webhook URL Format:**
```
https://<ngrok-id>.ngrok.io/webhooks/instagram
```

### 4. Manual Testing (MVP)

**Test Scenarios:**
1. Send message from test Instagram account
2. Verify webhook received and processed
3. Verify response sent back to Instagram
4. Check database for stored messages

**MVP Note:** Manual testing is sufficient for MVP. Skip automated E2E tests initially.

## Deployment

### Local Development (Windows 11)

**Requirements:**
- Python 3.11+
- PostgreSQL 15+
- ngrok

**Setup Steps:**
1. Install dependencies: `pip install -r requirements.txt`
2. Set up PostgreSQL database
3. Configure `.env` file with credentials
4. Run migrations: `alembic upgrade head`
5. Start server: `uvicorn app.main:app --reload`
6. Start ngrok: `ngrok http 8000`
7. Configure Facebook webhook with ngrok URL

### Railway Deployment

**Configuration:**
1. Connect GitHub repository to Railway
2. Add PostgreSQL plugin
3. Set environment variables in Railway dashboard
4. Railway auto-detects Python and deploys

**Environment Variables:**
```
FACEBOOK_APP_ID=your-app-id
FACEBOOK_APP_SECRET=your-app-secret
FACEBOOK_VERIFY_TOKEN=your-verify-token
INSTAGRAM_PAGE_ACCESS_TOKEN=your-page-token
INSTAGRAM_PAGE_ID=your-page-id
DATABASE_URL=postgresql://... (auto-provided by Railway)
ENVIRONMENT=production
LOG_LEVEL=INFO
```

### Custom Linux Server Deployment

**Requirements:**
- Ubuntu 22.04 LTS (or similar)
- Python 3.11+
- PostgreSQL 15+
- Nginx (reverse proxy)
- SSL certificate (Let's Encrypt)

**Deployment Steps:**
1. Set up PostgreSQL database
2. Clone repository
3. Create virtual environment
4. Install dependencies
5. Configure systemd service
6. Set up Nginx reverse proxy with SSL
7. Configure firewall rules

**Systemd Service Example:**
```ini
[Unit]
Description=Instagram Messenger Automation
After=network.target postgresql.service

[Service]
Type=notify
User=www-data
WorkingDirectory=/opt/instagram-automation
Environment="PATH=/opt/instagram-automation/venv/bin"
ExecStart=/opt/instagram-automation/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

## Component Swap Impact Analysis

This section demonstrates how the modular design enables component replacement with minimal impact.

### Scenario 1: Replace Response Engine (Keyword → AI)

**What Changes:**
- Create new `AIResponseEngine` class implementing `IResponseEngine`
- Update `get_response_engine()` in `dependencies.py`

**What Stays the Same:**
- Webhook handler
- Message processor
- Instagram client
- All repositories
- Database schema

**Impact:**
```python
# Before
def get_response_engine(...) -> IResponseEngine:
    return KeywordResponseEngine(rule_repo, logger)

# After
def get_response_engine(...) -> IResponseEngine:
    return AIResponseEngine(openai_client, logger)
```

**Testing Impact:** Only need to test `AIResponseEngine` implementation

### Scenario 2: Switch Database (PostgreSQL → MongoDB)

**What Changes:**
- Create new repository implementations (`MongoMessageRepository`, etc.)
- Update repository factory functions in `dependencies.py`
- Update database connection setup

**What Stays the Same:**
- All business logic (message processor, response engine)
- All API endpoints
- Instagram client
- Domain models (Message, Conversation classes)

**Impact:**
```python
# Before
def get_message_repository(db: AsyncSession) -> IMessageRepository:
    return MessageRepository(db)

# After
def get_message_repository(mongo: MongoClient) -> IMessageRepository:
    return MongoMessageRepository(mongo)
```

**Testing Impact:** Only need to test new repository implementations

### Scenario 3: Add WhatsApp Support

**What Changes:**
- Create `WhatsAppClient` implementing `IMessagingClient`
- Add WhatsApp-specific webhook handler
- Update factory to return appropriate client

**What Stays the Same:**
- Message processor (works with any `IMessagingClient`)
- Response engine
- All repositories
- Core business logic

**Impact:**
```python
class MessagingClientFactory:
    def get_client(self, platform: str) -> IMessagingClient:
        if platform == "instagram":
            return InstagramClient(...)
        elif platform == "whatsapp":
            return WhatsAppClient(...)
```

**Testing Impact:** Only need to test `WhatsAppClient` and new webhook handler

### Scenario 4: Add Caching Layer

**What Changes:**
- Create `CachedRuleRepository` implementing `IRuleRepository`
- Wrap existing repository with caching logic

**What Stays the Same:**
- Everything else (transparent to all consumers)

**Impact:**
```python
class CachedRuleRepository(IRuleRepository):
    def __init__(
        self, 
        inner_repo: IRuleRepository, 
        cache: Redis
    ):
        self._repo = inner_repo
        self._cache = cache
    
    async def get_active_rules(self) -> List[ResponseRule]:
        cached = await self._cache.get("active_rules")
        if cached:
            return cached
        rules = await self._repo.get_active_rules()
        await self._cache.set("active_rules", rules, ttl=300)
        return rules
```

**Testing Impact:** Only need to test caching logic

## Security Considerations

1. **Webhook Signature Validation**
   - Always validate X-Hub-Signature-256 header
   - Use constant-time comparison to prevent timing attacks

2. **Credential Management**
   - Never commit secrets to version control
   - Use environment variables for all sensitive data
   - Rotate access tokens periodically

3. **Rate Limiting**
   - Implement rate limiting on webhook endpoint
   - Prevent abuse from malicious actors

4. **Database Security**
   - Use connection pooling with SSL
   - Implement prepared statements (SQLAlchemy handles this)
   - Regular backups

5. **HTTPS Only**
   - Enforce HTTPS in production
   - Use valid SSL certificates

## Future Enhancements

### AI/ML Integration

**Phase 1: Intent Classification**
- Train model to classify customer intents (order inquiry, product question, complaint, etc.)
- Use classification to route to appropriate response templates

**Phase 2: Smart Response Generation**
- Integrate OpenAI GPT or similar LLM
- Generate contextual responses based on conversation history
- Maintain brand voice and tone

**Phase 3: Sentiment Analysis**
- Detect customer sentiment (positive, negative, neutral)
- Escalate negative sentiment to human agents
- Prioritize urgent inquiries

**Architecture Addition:**
```python
class AIService:
    async def classify_intent(self, message: str) -> Intent
    async def generate_response(
        self, 
        message: str, 
        context: List[Message]
    ) -> str
    async def analyze_sentiment(self, message: str) -> Sentiment
```

### Additional Features

- **Admin Dashboard**: Web UI for managing response rules
- **Analytics**: Message volume, response times, customer satisfaction
- **Multi-language Support**: Detect language and respond accordingly
- **Rich Media**: Support for sending images, quick replies, buttons
- **Human Handoff**: Escalation to human agents for complex queries
