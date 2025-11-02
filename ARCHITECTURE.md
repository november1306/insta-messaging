# Instagram Messenger Automation - Architecture

## Current Issues with MVP Implementation

### ❌ **Problems to Solve:**
1. **Hardcoded Configuration**: User IDs, tokens in test scripts and code
2. **Single Account Limitation**: Only supports one Instagram business account
3. **No Data Persistence**: No database for messages, conversations, or account data
4. **Tight Coupling**: Direct API calls without proper abstraction
5. **Configuration Management**: Environment variables scattered and hardcoded

## Target Architecture

### **Core Principles:**
- **Multi-tenant**: Support multiple Instagram business accounts
- **Interface-driven**: Clean abstractions for all external dependencies
- **Database-first**: All configuration and data stored in MySQL
- **Account-scoped**: All operations tied to specific Instagram accounts
- **Configurable**: No hardcoded values in application code

## Component Architecture

### 1. **Account Management Layer**

```python
class InstagramBusinessAccount:
    account_id: str
    username: str
    access_token: str (encrypted)
    webhook_verify_token: str
    app_secret: str (encrypted)
    status: AccountStatus
    settings: Dict[str, Any]
```

**Responsibilities:**
- Store encrypted credentials per account
- Manage account lifecycle and status
- Provide account-specific configuration
- Handle token refresh and validation

### 2. **Message Processing Interfaces**

#### IMessageReceiver
```python
class IMessageReceiver:
    async def receive_webhook(self, account_id: str, payload: dict) -> None
    async def validate_signature(self, account_id: str, signature: str, body: str) -> bool
    async def process_message(self, account_id: str, message: InboundMessage) -> None
```

#### IMessageSender  
```python
class IMessageSender:
    async def send_message(self, account_id: str, recipient_id: str, message: str) -> MessageResult
    async def send_template(self, account_id: str, recipient_id: str, template_id: str, params: dict) -> MessageResult
```

### 3. **Database Models**

#### InstagramBusinessAccount
```sql
CREATE TABLE instagram_business_accounts (
    id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    display_name VARCHAR(200),
    access_token_encrypted TEXT NOT NULL,
    app_secret_encrypted TEXT NOT NULL,
    webhook_verify_token VARCHAR(100) NOT NULL,
    status ENUM('active', 'inactive', 'suspended') DEFAULT 'active',
    settings JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

#### Messages
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES instagram_business_accounts(id)
);
```

#### Conversations
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
    FOREIGN KEY (account_id) REFERENCES instagram_business_accounts(id)
);
```

#### ResponseRules
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
    FOREIGN KEY (account_id) REFERENCES instagram_business_accounts(id)
);
```

## Implementation Plan

### Phase 2: Architecture Refactoring (Current)
1. **Create account management system**
2. **Implement proper interfaces**
3. **Set up MySQL database**
4. **Migrate hardcoded values to database**

### Phase 3: Multi-Account Support
1. **Account-aware webhook routing**
2. **Account-specific message processing**
3. **Account management API**

### Phase 4: Enhanced Features
1. **Response rule engine per account**
2. **Conversation management**
3. **Analytics and reporting**

## Configuration Management

### Environment Variables (Minimal)
```env
# Database
MYSQL_HOST=localhost
MYSQL_PORT=3306
MYSQL_DATABASE=instagram_automation
MYSQL_USERNAME=app_user
MYSQL_PASSWORD=secure_password

# Application
APP_SECRET_KEY=your-app-secret-for-encryption
ENVIRONMENT=development
```

### Account-Specific Configuration (Database)
- Instagram access tokens (encrypted)
- Facebook app secrets (encrypted)  
- Webhook verify tokens
- Account-specific settings
- Response rules and templates

## Benefits of New Architecture

### ✅ **Scalability**
- Support unlimited Instagram business accounts
- Horizontal scaling with database
- Account isolation and security

### ✅ **Maintainability**
- Clean interfaces and separation of concerns
- Configuration in database, not code
- Easy testing with interface mocks

### ✅ **Security**
- Encrypted credential storage
- Account-specific access control
- Audit trail for all operations

### ✅ **Flexibility**
- Account-specific business logic
- Configurable response rules
- Easy integration with existing systems
