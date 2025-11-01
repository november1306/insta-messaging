# Implementation Plan

This plan is organized to prioritize getting a working MVP deployed and tested as quickly as possible. We'll build the minimal webhook receiver + response sender first, deploy it immediately, then add database and other features incrementally.

## Phase 1: Minimal Viable Solution (Receive + Respond)

- [x] 1. Create minimal FastAPI webhook server



  - Create basic FastAPI project structure (app/main.py, app/api/webhooks.py)
  - Implement GET /webhooks/instagram for webhook verification (validate verify_token, return challenge)
  - Implement POST /webhooks/instagram to receive messages (log payload, return 200)
  - Add basic environment variable loading (FACEBOOK_VERIFY_TOKEN, INSTAGRAM_PAGE_ACCESS_TOKEN, FACEBOOK_APP_SECRET)
  - Add simple console logging
  - _Requirements: 1.1, 1.3, 1.5, 2.4, 4.1, 4.2_

- [ ] 2. Implement webhook signature validation
  - Create signature validation function using HMAC SHA256
  - Validate X-Hub-Signature-256 header in POST webhook
  - Return 401 if signature invalid, otherwise continue
  - _Requirements: 2.1, 2.2_

- [ ] 3. Implement basic message parsing and response
  - Extract sender ID and message text from webhook payload
  - Create hardcoded response logic (e.g., "Thanks for your message! We'll get back to you soon.")
  - Call Instagram Send API to send response using httpx
  - Log success/failure
  - _Requirements: 2.3, 3.1, 3.2, 3.4_

- [ ] 4. Add requirements.txt and basic README
  - Create requirements.txt (fastapi, uvicorn, httpx, python-dotenv)
  - Create .env.example with required variables
  - Create README with quick start instructions
  - _Requirements: 4.1, 8.4_

## Phase 2: Deployment and Testing Pipeline

- [ ] 5. Set up local development with ngrok
  - Document ngrok setup in README
  - Test webhook verification locally
  - Test receiving and responding to messages from Instagram test account
  - _Requirements: 8.1, 8.4_

- [ ] 6. Deploy to Railway (or alternative)
  - Create Railway project and connect repository
  - Configure environment variables in Railway
  - Deploy and get public HTTPS URL
  - Configure Facebook webhook with Railway URL
  - Test end-to-end with real Instagram messages
  - _Requirements: 4.6, 8.1_

- [ ] 7. Add health check endpoint
  - Create GET /health endpoint (returns {"status": "ok"})
  - Use for monitoring deployment status
  - _Requirements: 7.6_

## Phase 3: Add Database and Persistence

- [ ] 8. Set up database models and migrations
  - [ ] 8.1 Add SQLAlchemy and asyncpg dependencies
    - Update requirements.txt
    - _Requirements: 5.1_
  - [ ] 8.2 Create database models (Message, Conversation, ResponseRule)
    - Define Message model with essential fields
    - Define Conversation model for tracking users
    - Define ResponseRule model for keyword matching
    - _Requirements: 5.1, 5.2, 5.5_
  - [ ] 8.3 Set up Alembic migrations
    - Initialize Alembic
    - Create initial migration
    - _Requirements: 5.1_

- [ ] 9. Implement repository layer
  - [ ] 9.1 Create MessageRepository
    - Implement create() to store messages
    - Implement get_conversation_history()
    - _Requirements: 5.1, 5.3_
  - [ ] 9.2 Create ConversationRepository
    - Implement get_or_create()
    - Implement update_last_message_time()
    - _Requirements: 5.4_
  - [ ] 9.3 Create RuleRepository
    - Implement get_active_rules()
    - Implement find_matching_rule()
    - _Requirements: 6.1, 6.4_

- [ ] 10. Integrate database into message flow
  - Store incoming messages in database
  - Store outgoing messages in database
  - Track conversations
  - _Requirements: 5.1, 5.2_

## Phase 4: Enhanced Response Logic

- [ ] 11. Implement keyword-based response engine
  - Replace hardcoded response with keyword matching
  - Query ResponseRule table for matching keywords
  - Return matched response or fallback
  - _Requirements: 6.1, 6.3, 6.4_

- [ ] 12. Add seed data for response rules
  - Create seed script for common e-commerce responses
  - Add rules for: order status, product info, contact, fallback
  - _Requirements: 6.1_

- [ ] 13. Add conversation context to responses
  - Retrieve conversation history when processing messages
  - Pass history to response engine (for future AI integration)
  - _Requirements: 5.3, 6.1_

## Phase 5: Production Readiness (Optional)

- [ ]* 14. Add structured logging
  - Replace console logging with structlog
  - Add request IDs and contextual information
  - _Requirements: 7.1_

- [ ]* 15. Improve error handling
  - Add retry logic for Send API failures
  - Add exponential backoff
  - Handle rate limiting
  - _Requirements: 3.5, 7.2, 7.3_

- [ ]* 16. Add monitoring and alerts
  - Set up error alerting
  - Add performance monitoring
  - _Requirements: 7.5_

- [ ]* 17. Refactor to modular architecture
  - Extract interfaces (IMessageProcessor, IResponseEngine, etc.)
  - Implement dependency injection
  - Enable component swapping
  - _Requirements: 4.1_
