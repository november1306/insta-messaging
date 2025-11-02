# Implementation Plan

This plan implements a proper multi-account architecture with clean interfaces, MySQL database storage, and separation of configuration from code.

## Phase 1: Core Infrastructure and Database Setup

- [ ] 1. Set up MySQL database and models
  - Add MySQL dependencies (aiomysql, SQLAlchemy, Alembic)
  - Create database connection management with connection pooling
  - Define SQLAlchemy models (InstagramBusinessAccount, Message, Conversation, ResponseRule)
  - Initialize Alembic for migrations
  - Create initial migration with all tables
  - _Requirements: 5.1, 5.2_

- [ ] 2. Implement credential encryption service
  - Create encryption/decryption utilities using cryptography library
  - Use APP_SECRET_KEY from environment for encryption
  - Implement encrypt_token() and decrypt_token() functions
  - Add validation for encrypted data integrity
  - _Requirements: 4.3, 4.4_

- [ ] 3. Create core domain models and interfaces
  - Define InstagramBusinessAccount domain model
  - Define Message, Conversation, ResponseRule domain models
  - Create IMessageReceiver interface
  - Create IMessageSender interface
  - Create IAccountRepository interface
  - Create IMessageRepository, IConversationRepository, IRuleRepository interfaces
  - _Requirements: 4.1, 4.2_

## Phase 2: Account Management Layer

- [ ] 4. Implement Account Repository
  - Create AccountRepository implementing IAccountRepository
  - Implement get_by_id() with credential decryption
  - Implement get_by_username()
  - Implement create() with credential encryption
  - Implement update() with credential encryption
  - Implement get_active_accounts()
  - _Requirements: 4.1, 4.2_

- [ ] 5. Create Account Management API endpoints
  - POST /accounts - Create new Instagram business account
  - GET /accounts - List all accounts
  - GET /accounts/{account_id} - Get account details
  - PUT /accounts/{account_id} - Update account
  - DELETE /accounts/{account_id} - Deactivate account
  - Add request/response models with Pydantic
  - _Requirements: 4.1, 4.2_

- [ ] 6. Create account seeding script
  - Create script to add initial Instagram account (@ser_bain)
  - Encrypt and store access token, app secret, verify token
  - Validate account credentials against Instagram API
  - _Requirements: 4.1, 4.2_

## Phase 3: Message Receiving Interface

- [ ] 7. Implement IMessageReceiver interface
  - Create InstagramMessageReceiver implementing IMessageReceiver
  - Implement receive_webhook(account_id, payload)
  - Implement validate_signature(account_id, signature, body) using account-specific app secret
  - Implement process_message(account_id, message) to parse and store messages
  - Extract sender ID, message text, timestamp from webhook payload
  - _Requirements: 2.1, 2.2, 2.3_

- [ ] 8. Implement Message and Conversation repositories
  - Create MessageRepository implementing IMessageRepository
  - Implement create() to store messages with account_id
  - Implement get_conversation_history() scoped to account
  - Create ConversationRepository implementing IConversationRepository
  - Implement get_or_create() scoped to account
  - Implement update_last_message_time()
  - _Requirements: 5.1, 5.2, 5.3, 5.4_

- [ ] 9. Update webhook endpoints for account-aware processing
  - Modify GET /webhooks/instagram to accept account_id parameter
  - Validate verify token against specific account from database
  - Modify POST /webhooks/instagram to accept account_id parameter
  - Route webhook to correct account using IMessageReceiver
  - Validate signature using account-specific app secret
  - Store incoming messages with account_id
  - _Requirements: 1.1, 1.3, 2.1, 2.2, 2.3_

## Phase 4: Message Sending Interface

- [ ] 10. Implement IMessageSender interface
  - Create InstagramMessageSender implementing IMessageSender
  - Implement send_message(account_id, recipient_id, message_text)
  - Retrieve account credentials from database
  - Use account-specific access token for Instagram Graph API
  - Implement send_template(account_id, recipient_id, template_id, params)
  - Add error handling and logging
  - _Requirements: 3.1, 3.2, 3.4_

- [ ] 11. Integrate message sending into webhook flow
  - After receiving message, generate response (hardcoded for now)
  - Call IMessageSender.send_message() with correct account_id
  - Store outgoing message in database
  - Handle Send API errors gracefully
  - _Requirements: 3.1, 3.2, 3.4_

- [ ] 12. Update test script for account-based sending
  - Remove hardcoded user IDs from test_send_message.py
  - Accept account_id or username as parameter
  - Retrieve account credentials from database
  - Look up recipient by username (add user lookup table or API)
  - Send message using IMessageSender interface
  - _Requirements: 3.1, 3.2_

## Phase 5: Response Rules Engine (Account-Scoped)

- [ ] 13. Implement Rule Repository
  - Create RuleRepository implementing IRuleRepository
  - Implement get_active_rules(account_id)
  - Implement find_matching_rule(account_id, message_text)
  - Support simple keyword matching (case-insensitive contains)
  - _Requirements: 6.1, 6.4_

- [ ] 14. Create Response Engine
  - Create ResponseEngine class
  - Implement generate_response(account_id, message, conversation_history)
  - Query rules for specific account
  - Match message text against rule triggers
  - Return matched response or fallback
  - _Requirements: 6.1, 6.3, 6.4_

- [ ] 15. Integrate Response Engine into message flow
  - After receiving message, call ResponseEngine.generate_response()
  - Pass account_id and conversation history
  - Send generated response using IMessageSender
  - Log which rule was matched
  - _Requirements: 6.1, 6.3, 6.4_

## Phase 6: Configuration and Deployment

- [ ] 16. Update configuration management
  - Remove Instagram credentials from environment variables
  - Keep only database connection and APP_SECRET_KEY in .env
  - Update .env.example with new structure
  - Add configuration validation on startup
  - _Requirements: 4.1, 4.2, 4.3_

- [ ] 17. Add health check and monitoring endpoints
  - Create GET /health endpoint
  - Check database connectivity
  - Check active accounts count
  - Return system status
  - _Requirements: 7.6_

- [ ] 18. Create deployment documentation
  - Document MySQL setup requirements
  - Document account registration process
  - Document webhook configuration per account
  - Update README with new architecture
  - _Requirements: 8.4_

## Phase 7: Testing and Validation

- [ ]* 19. Add unit tests for core components
  - Test credential encryption/decryption
  - Test account repository operations
  - Test message receiver signature validation
  - Test message sender with mocked Instagram API
  - Test response engine rule matching
  - _Requirements: 8.1, 8.2_

- [ ]* 20. Add integration tests
  - Test webhook flow end-to-end with test account
  - Test account creation and retrieval
  - Test message storage and retrieval
  - Test multi-account message routing
  - _Requirements: 8.1, 8.3_

## Notes

- All tasks build incrementally on previous tasks
- Each task references specific requirements from requirements.md
- Optional tasks (marked with *) focus on testing and can be skipped for MVP
- Core functionality prioritizes multi-account support and proper interfaces
- Configuration is stored in database, not environment variables
- All operations are account-scoped for security and isolation
