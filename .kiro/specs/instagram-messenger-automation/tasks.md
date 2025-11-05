# Implementation Plan

This plan implements a simple POC for receiving and sending Instagram messages. We start with a single-account setup using SQLite, then can evolve to multi-account with MySQL later.

## Phase 1: Core Infrastructure and Database Setup ✅

- [x] 1. Set up SQLite database and models
  - ✅ Add SQLite dependencies (aiosqlite, SQLAlchemy, Alembic)
  - ✅ Create database connection management (app/db/connection.py)
  - ✅ Define SQLAlchemy MessageModel (app/db/models.py)
  - ✅ Initialize Alembic for migrations
  - ✅ Reorganized DB files into app/db/ directory
  - _Requirements: 5.1, 5.2_

- [x] 2. Create basic webhook endpoints
  - ✅ Implement GET /webhooks/instagram for verification
  - ✅ Implement POST /webhooks/instagram for receiving messages
  - ✅ Basic logging of incoming webhooks
  - _Requirements: 1.1, 2.1_

- [x] 3. Create core domain models and interfaces
  - ✅ Define Message domain model (app/core/interfaces.py)
  - ✅ Create IMessageRepository interface
  - _Requirements: 4.1, 4.2_

## Phase 2: Message Processing (POC)

- [x] 4. Implement Message Repository



  - Create MessageRepository implementing IMessageRepository
  - Implement save() to store incoming messages
  - Implement get_by_id() to retrieve messages
  - Use SQLAlchemy with async session
  - _Requirements: 5.1, 5.2_

- [x] 5. Parse and store incoming webhook messages



  - Extract message data from webhook payload (sender_id, text, timestamp)
  - Create Message domain object from webhook data
  - Save message to database using MessageRepository
  - Handle webhook payload structure (entry[].messaging[])
  - Add error handling for malformed payloads
  - _Requirements: 2.1, 2.3, 5.1_

## Phase 3: Message Sending (POC)

- [x] 6. Create Instagram API client







  - Create InstagramClient class for API calls
  - Implement send_message(recipient_id, message_text) method
  - Use httpx for async HTTP requests
  - Call Instagram Send API: POST https://graph.facebook.com/v21.0/me/messages
  - Use INSTAGRAM_PAGE_ACCESS_TOKEN from config
  - Add basic error handling and logging
  - _Requirements: 3.1, 3.2_

- [ ] 7. Implement simple auto-reply logic
  - After receiving and storing a message, generate a simple response
  - For POC: hardcoded response like "Thanks for your message! We'll get back to you soon."
  - Call InstagramClient.send_message() to send reply
  - Store outgoing message in database
  - Handle Send API errors gracefully
  - _Requirements: 3.1, 3.2, 3.4_

## Phase 4: Testing and Validation (POC)

- [ ] 8. Test end-to-end message flow
  - Set up ngrok tunnel for local testing
  - Configure Instagram webhook with ngrok URL
  - Send test message from Instagram account
  - Verify message is received, stored, and auto-reply sent
  - Check database for stored messages
  - _Requirements: 8.1, 8.3_

- [ ] 9. Add webhook signature validation
  - Implement signature validation using X-Hub-Signature-256 header
  - Use FACEBOOK_APP_SECRET from config
  - Validate signature before processing webhook
  - Return 401 for invalid signatures
  - _Requirements: 2.2, 4.3_

## Phase 5: Enhanced Features (Post-POC)

- [ ] 10. Add keyword-based response rules
  - Create ResponseRule model in database
  - Implement simple keyword matching (case-insensitive contains)
  - Match incoming message against rules
  - Send matched response instead of hardcoded reply
  - Add fallback response for no matches
  - _Requirements: 6.1, 6.3, 6.4_

- [ ] 11. Add conversation history tracking
  - Create Conversation model in database
  - Link messages to conversations
  - Retrieve last N messages for context
  - Track conversation status (active/archived)
  - _Requirements: 5.3, 5.4_

## Phase 6: Multi-Account Support (Future)

- [ ] 12. Migrate to MySQL database
  - Add MySQL dependencies (aiomysql)
  - Update database connection for MySQL
  - Create migration scripts
  - Update models for MySQL-specific features
  - _Requirements: 5.1, 5.2_

- [ ] 13. Add InstagramBusinessAccount model
  - Create account table in database
  - Store account credentials (encrypted)
  - Implement account repository
  - Add account management API endpoints
  - _Requirements: 4.1, 4.2, 4.3_

- [ ] 14. Make all operations account-scoped
  - Update webhook endpoints to accept account_id
  - Validate tokens per account
  - Route messages to correct account
  - Store messages with account_id
  - _Requirements: 1.3, 2.1, 4.1_

## Phase 7: Testing and Documentation

- [ ]* 15. Add unit tests for core components
  - Test message repository operations
  - Test webhook signature validation
  - Test Instagram client with mocked API
  - Test response rule matching
  - _Requirements: 8.1, 8.2_

- [ ]* 16. Create deployment documentation
  - Document local development setup
  - Document ngrok configuration
  - Document Instagram app setup
  - Document environment variables
  - Update README with architecture
  - _Requirements: 8.4_

## Notes

- **POC Focus**: Phases 1-4 create a working single-account POC
- **Phase 5**: Adds smarter responses with keyword rules
- **Phase 6**: Scales to multi-account architecture
- **Phase 7**: Testing and documentation
- Optional tasks (marked with *) can be skipped for MVP
- Each task builds incrementally on previous tasks
- All tasks reference specific requirements from requirements.md
