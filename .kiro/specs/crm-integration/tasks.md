# Implementation Plan

This plan implements the CRM integration feature using a **skeleton-first approach**: deploy a minimal working API quickly, then add robustness incrementally. The OpenAPI spec (`api-spec.yaml`) defines the contract - implement just enough to make it work, test on deployment, then iterate.

## ⚠️ PRIORITY REEVALUATION

**Core MVP Logic:** The primary purpose of this integration is to enable a CRM chat window. This requires:
1. **Inbound flow (CRITICAL):** Instagram → Router → CRM webhook (so CRM can display customer messages)
2. **Outbound flow (CRITICAL):** CRM → Router API → Instagram (so CRM can send replies)

**Current Status:**
- ✅ Outbound flow is complete (Tasks 1-8)
- ❌ Inbound flow is NOT implemented (was deprioritized to Priority 3)

**Correction:** Tasks 16-18 (webhook forwarding) should be Priority 1, not Priority 3. Without them, the CRM chat window cannot receive messages.

---

## Priority 1: MINIMAL HAPPY PATH (Deploy & Test First)

Goal: Get bidirectional messaging working - CRM can send AND receive messages. No error handling, no retries, no edge cases - just the core flow.

- [x] 1. Integrate OpenAPI spec and set up Swagger UI




  - Copy api-spec.yaml to app/static/ directory
  - Configure FastAPI to serve OpenAPI spec from file
  - Mount Swagger UI at /docs endpoint
  - Test that all endpoints are documented
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

- [x] 2. Create minimal database models




  - Create accounts table (id, instagram_account_id, username, access_token_encrypted, crm_webhook_url, webhook_secret)
  - Create outbound_messages table (id, account_id, recipient_id, message_text, idempotency_key, status, created_at)
  - Create Account and OutboundMessage SQLAlchemy models
  - Run Alembic migration
  - _Requirements: 7.1, 7.3_

- [x] 3. Implement stub authentication (hardcoded for now)



  - Create simple verify_api_key dependency that accepts any "Bearer test_key"
  - Add Authorization header requirement to endpoints
  - Return 401 if header missing
  - TODO: Replace with real auth later





  - _Requirements: 9.1, 9.2_

- [x] 4. Implement POST /api/v1/accounts (minimal)
  - Create Pydantic models from OpenAPI spec (CreateAccountRequest, AccountResponse)
  - Store account in database (encrypt access_token with simple encryption)
  - Return 201 with account_id
  - Skip Instagram token validation for now
  - _Requirements: 5.1, 5.2_

- [x] 5. Implement POST /api/v1/messages/send (happy path only)
  - Create Pydantic models from OpenAPI spec (SendMessageRequest, SendMessageResponse)
  - Check idempotency_key - return existing if duplicate
  - Create outbound_messages record with status="pending"
  - Return 202 Accepted with message_id immediately
  - Skip account validation for now
  - _Requirements: 1.1, 1.3, 1.5_

- [x] 6. Implement simple Instagram delivery (synchronous for now)


  - After creating message record, immediately call Instagram Send API
  - Use existing InstagramClient from main app
  - Update message status to "sent" or "failed"
  - Log success/failure
  - Skip async queue and retries for now
  - _Requirements: 1.4_



- [x] 7. Implement GET /api/v1/messages/{message_id}/status (minimal)

  - Create Pydantic model from OpenAPI spec (MessageStatusResponse)
  - Query outbound_messages by message_id
  - Return 404 if not found
  - Return current status
  - Skip permission checking for now
  - _Requirements: 4.1, 4.2, 4.3_



- [x] 8. Implement GET /health endpoint

  - Return {"status": "healthy", "timestamp": "..."}
  - Skip dependency checks for now
  - _Requirements: 11.5_


- [x] 9. Implement simple webhook forwarding to CRM (CRITICAL - moved from Priority 3)


  - Add CRM_WEBHOOK_URL to config (from account or global setting)
  - When Instagram message received, forward to CRM webhook immediately
  - Generate HMAC-SHA256 signature using webhook_secret
  - Send POST to CRM with InboundMessageWebhook payload
  - Include X-Hub-Signature-256 header
  - Log success/failure (no retries yet)
  - _Requirements: 2.1, 2.2, 2.6, 6.1, 6.2_

- [x] 10. Test Gentoo deployment compatibility


  - Create Docker container with Gentoo base or use local Gentoo VM
  - Test fresh deployment using deploy.sh (pip + venv, no conda)
  - Verify all dependencies install correctly on Gentoo
  - Test uvicorn server starts and serves /docs
  - Document any Gentoo-specific setup requirements
  - _Requirements: All Priority 1_

- [ ] 11. Deploy and test end-to-end CRM chat flow on 1gb remote
  - Deploy to 1gb remote server (Gentoo)
  - Test via Swagger UI at /docs
  - Create test account via POST /api/v1/accounts
  - Send test message via POST /api/v1/messages/send (CRM → Instagram)
  - Verify message sent to Instagram
  - Send Instagram message to business account (Instagram → CRM)
  - Verify CRM webhook receives message
  - Check status via GET /api/v1/messages/{id}/status
  - _Requirements: All Priority 1_

## Priority 2: ADD ROBUSTNESS (After skeleton works)

Goal: Add error handling, retries, proper auth, and edge cases. Test each addition on deployment.

- [ ] 12. Implement proper API key authentication
  - Create api_keys table with key_hash and account_ids
  - Implement bcrypt hashing for API keys
  - Update verify_api_key to check database
  - Add permission checking (account access)
  - Generate admin API key for testing
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

- [ ] 13. Add Instagram token validation to account creation
  - Call Instagram API to validate access_token
  - Return 400 if token invalid
  - Store validation result
  - _Requirements: 5.3, 5.4_

- [ ] 14. Implement async message delivery with queue
  - Create background worker that polls pending messages
  - Move Instagram API call to background task
  - Add retry logic with exponential backoff (3 attempts)
  - Update message status after each attempt
  - _Requirements: 1.6, 1.7_

- [ ] 15. Add comprehensive error handling
  - Create ErrorResponse model from OpenAPI spec
  - Add error handling middleware
  - Return proper HTTP status codes (400, 401, 403, 404)
  - Add correlation_id to all responses
  - Log all errors
  - _Requirements: 11.1, 11.2, 11.7_

- [ ] 16. Implement GET /api/v1/accounts/{account_id}
  - Return account details without credentials
  - Verify API key has access
  - _Requirements: 5.7_

- [ ] 17. Implement PUT /api/v1/accounts/{account_id}
  - Allow updating crm_webhook_url and webhook_secret
  - Support access_token rotation
  - Re-encrypt credentials if updated
  - _Requirements: 5.5, 5.6_

## Priority 3: INBOUND WEBHOOKS - ADVANCED (After basic forwarding works)

Goal: Add robustness to webhook forwarding - retries, DLQ, tracking.

- [ ] 18. Create webhook delivery tracking system
  - Create webhook_deliveries table
  - Create WebhookDelivery SQLAlchemy model
  - Track delivery attempts and status
  - _Requirements: 6.1, 6.2, 7.1, 7.3_

- [ ] 19. Implement webhook retry logic
  - Create WebhookDeliveryService with retry queue
  - Implement exponential backoff (5 retries)
  - Create background worker for retries
  - Don't retry on 401 errors
  - _Requirements: 2.3, 2.4, 6.5, 8.2, 8.6_

- [ ] 20. Add delivery status webhooks
  - Create DeliveryStatusWebhook payload from OpenAPI spec
  - Send webhook when outbound message status changes
  - Include message_id, status, timestamp
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.7_

- [ ] 21. Implement dead letter queue for failed webhooks
  - Move failed webhooks to DLQ after 24 hours
  - Create GET /api/v1/admin/dlq/webhooks endpoint
  - Create POST /api/v1/admin/dlq/webhooks/{id}/retry endpoint
  - _Requirements: 2.5, 8.3, 8.4_

## Priority 4: ADVANCED FEATURES (Optional)

Goal: Add monitoring, admin features, and documentation.

- [ ] 22. Add structured logging
  - Log all API requests
  - Log message send/receive events
  - Log webhook delivery attempts
  - Never log message content or credentials
  - _Requirements: 11.1, 11.2, 11.3, 11.6_

- [ ] 23. Add performance monitoring
  - Track API response times
  - Track webhook delivery latency
  - Warn if latency > 5 seconds
  - _Requirements: 11.4_

- [ ]* 24. Create integration tests
  - Test outbound message flow
  - Test inbound webhook forwarding
  - Test idempotency
  - Test webhook retry logic
  - _Requirements: All_

- [ ]* 25. Create deployment documentation
  - Document environment variables
  - Document API key generation
  - Create curl examples
  - Document webhook signature validation for CRM devs
  - _Requirements: 10.1, 10.2, 10.3_

## Notes

**Approach:**
- **Priority 1 (Tasks 1-11)**: Minimal bidirectional flow - CRM can send AND receive messages, test Gentoo deployment
- **Priority 2 (Tasks 12-17)**: Add robustness to outbound - proper auth, retries, error handling
- **Priority 3 (Tasks 18-21)**: Add robustness to inbound - webhook retries, DLQ, status updates
- **Priority 4 (Tasks 22-25)**: Advanced features - monitoring, logging, docs

**Key Principles:**
- OpenAPI spec (`api-spec.yaml`) is the contract - implement to match it
- Deploy after each priority level and test on real environment
- Start with hardcoded/stub implementations, replace with real logic incrementally
- Skip edge cases and error handling in Priority 1 - just make it work
- Add "meat" (retries, validation, logging) in Priority 2+

**Testing Strategy:**
- Use Swagger UI at /docs for manual testing
- Test each endpoint immediately after implementation
- Deploy to test environment after Priority 1 completion
- Iterate based on real-world testing

Tasks marked with * are optional and can be deferred indefinitely.
