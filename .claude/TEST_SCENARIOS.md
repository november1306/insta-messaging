# Test Scenarios & Coverage Matrix

This document tracks test coverage from a **business perspective**. Each scenario describes a user story or system behavior that must be verified.

---

## Coverage Summary

| Area | Scenarios | Covered | Percentage |
|------|-----------|---------|------------|
| Account Identity | 6 | 6 | 100% |
| Message Sync | 5 | 0 | 0% |
| Authentication | 4 | 3 | 75% |
| Webhooks | 5 | 0 | 0% |
| API Endpoints | 6 | 3 | 50% |
| UI/E2E | 4 | 0 | 0% |
| **Total** | **30** | **12** | **40%** |

*Last updated: 2026-01-28*

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Covered by automated test |
| ⚠️ | Partially covered |
| ❌ | Not covered |
| 🔧 | Manual testing only |

---

## 1. Account Identity (ID Resolution)

Business context: The system uses multiple ID types (instagram_account_id, messaging_channel_id). Correct resolution is critical for message routing and filtering.

| ID | Scenario | Status | Test Location |
|----|----------|--------|---------------|
| AI-1 | **Effective channel ID uses messaging_channel_id when set** | ✅ | `tests/unit/domain/test_account_identity.py::TestEffectiveChannelId::test_returns_messaging_channel_id_when_set` |
| AI-2 | **Effective channel ID falls back to instagram_account_id when channel is null** | ✅ | `tests/unit/domain/test_account_identity.py::TestEffectiveChannelId::test_falls_back_to_instagram_account_id_when_channel_is_none` |
| AI-3 | **Business ID detection recognizes instagram_account_id** | ✅ | `tests/unit/domain/test_account_identity.py::TestIsBusinessId::test_returns_true_for_instagram_account_id` |
| AI-4 | **Business ID detection recognizes messaging_channel_id** | ✅ | `tests/unit/domain/test_account_identity.py::TestIsBusinessId::test_returns_true_for_messaging_channel_id` |
| AI-5 | **Business ID detection rejects customer IDs** | ✅ | `tests/unit/domain/test_account_identity.py::TestIsBusinessId::test_returns_false_for_customer_id` |
| AI-6 | **Direction detection: business sender = outbound** | ✅ | `tests/unit/domain/test_account_identity.py::TestDetectDirection::test_returns_outbound_when_sender_is_business` |

---

## 2. Message Sync (InstagramSyncService)

Business context: Messages sent from Instagram native app must sync to our system via API polling.

| ID | Scenario | Status | Test Location |
|----|----------|--------|---------------|
| MS-1 | **Sync fetches conversations from last 24 hours only** | ❌ | `tests/unit/services/test_instagram_sync_service.py` (TODO) |
| MS-2 | **Duplicate messages are skipped (deduplication by message ID)** | ❌ | `tests/unit/services/test_instagram_sync_service.py` (TODO) |
| MS-3 | **Customer is correctly identified from conversation participants** | ❌ | `tests/unit/services/test_instagram_sync_service.py` (TODO) |
| MS-4 | **Retry logic handles transient Instagram API failures** | ❌ | `tests/unit/services/test_instagram_sync_service.py` (TODO) |
| MS-5 | **Sync result contains accurate statistics** | ❌ | `tests/unit/services/test_instagram_sync_service.py` (TODO) |

---

## 3. Authentication

Business context: Users authenticate via username/password and receive JWT tokens. API keys are used for CRM integration.

| ID | Scenario | Status | Test Location |
|----|----------|--------|---------------|
| AUTH-1 | **User can register with valid credentials** | ✅ | `tests/test_integration_third_party.py::TestThirdPartyIntegration::test_001_complete_workflow_new_user` |
| AUTH-2 | **User can generate API token after login** | ✅ | `tests/test_integration_third_party.py::TestThirdPartyIntegration::test_001_complete_workflow_new_user` |
| AUTH-3 | **API token works across multiple sessions** | ✅ | `tests/test_integration_third_party.py::TestThirdPartyIntegration::test_002_token_reuse_across_sessions` |
| AUTH-4 | **Token permissions update when accounts are linked/unlinked** | ✅ | `tests/test_integration_third_party.py::TestThirdPartyIntegration::test_003_token_permissions_dynamic` |

---

## 4. Webhooks (Instagram → System)

Business context: Instagram sends webhook notifications for new messages. System must validate, route, and store them.

| ID | Scenario | Status | Test Location |
|----|----------|--------|---------------|
| WH-1 | **Valid webhook signature is accepted** | ❌ | `tests/integration/api/test_webhooks_api.py` (TODO) |
| WH-2 | **Invalid webhook signature is rejected with 403** | ❌ | `tests/integration/api/test_webhooks_api.py` (TODO) |
| WH-3 | **Webhook routes to correct account by messaging_channel_id** | ❌ | `tests/integration/api/test_webhooks_api.py` (TODO) |
| WH-4 | **Webhook falls back to instagram_account_id for new accounts** | ❌ | `tests/integration/api/test_webhooks_api.py` (TODO) |
| WH-5 | **Inbound message triggers SSE broadcast to UI** | ❌ | `tests/integration/api/test_webhooks_api.py` (TODO) |

---

## 5. API Endpoints

Business context: CRM systems integrate via REST API for sending messages and retrieving data.

| ID | Scenario | Status | Test Location |
|----|----------|--------|---------------|
| API-1 | **GET /accounts/me returns linked accounts with effective_channel_id** | ⚠️ | `tests/test_integration_third_party.py` (partial) |
| API-2 | **POST /messages/send queues message and returns pending status** | ❌ | `tests/integration/api/test_messages_api.py` (TODO) |
| API-3 | **GET /messages/{id}/status returns delivery status** | ❌ | `tests/integration/api/test_messages_api.py` (TODO) |
| API-4 | **Unauthorized request returns 401** | ❌ | `tests/integration/api/test_auth_api.py` (TODO) |
| API-5 | **Invalid account_id returns 403** | ❌ | `tests/integration/api/test_messages_api.py` (TODO) |
| API-6 | **POST /ui/sync fetches and stores messages from Instagram** | ❌ | `tests/integration/api/test_sync_api.py` (TODO) |

---

## 6. UI/E2E Workflows

Business context: End-users interact with the chat UI to view and respond to customer messages.

| ID | Scenario | Status | Test Location |
|----|----------|--------|---------------|
| E2E-1 | **User can log in and see conversation list** | ❌ | `tests/e2e/test_chat_workflow.py` (TODO) |
| E2E-2 | **Clicking conversation shows message history** | ❌ | `tests/e2e/test_chat_workflow.py` (TODO) |
| E2E-3 | **Sending message appears in chat immediately** | ❌ | `tests/e2e/test_chat_workflow.py` (TODO) |
| E2E-4 | **New inbound message appears via SSE without refresh** | ❌ | `tests/e2e/test_chat_workflow.py` (TODO) |

---

## Scenario Template

When adding new scenarios, use this template:

```markdown
| ID | Scenario | Status | Test Location |
|----|----------|--------|---------------|
| XX-N | **Brief description of expected behavior** | ❌ | `tests/path/to/test_file.py::TestClass::test_function` (TODO) |
```

After implementing:
1. Change status from ❌ to ✅
2. Update test location with actual path
3. Remove "(TODO)" suffix
4. Update coverage summary at top

---

## Priority Matrix

### P0 - Critical (Must Have)
- AI-1 to AI-6: Account identity (✅ Complete)
- AUTH-1 to AUTH-4: Authentication (✅ Complete)
- WH-1, WH-2: Webhook validation (❌ TODO)

### P1 - High (Should Have)
- MS-1 to MS-5: Message sync (❌ TODO)
- API-1 to API-3: Core API endpoints (⚠️ Partial)
- WH-3 to WH-5: Webhook routing (❌ TODO)

### P2 - Medium (Nice to Have)
- API-4 to API-6: Edge cases (❌ TODO)
- E2E-1 to E2E-4: UI workflows (❌ TODO)

---

## How to Use This Document

### For Claude Code
1. Before implementing a feature, check if scenarios exist
2. After implementing, write tests that cover relevant scenarios
3. Update this document with test locations
4. Update coverage summary

### For Manual Testing
1. Use scenarios as a checklist
2. Mark 🔧 if only manually tested
3. Create automated test to convert 🔧 to ✅

### For Code Review
1. Verify new code has corresponding scenarios
2. Check that test locations match actual files
3. Ensure coverage summary is accurate

---

## Appendix: Test File Index

| Test File | Scenarios Covered |
|-----------|-------------------|
| `tests/unit/domain/test_account_identity.py` | AI-1 to AI-6 |
| `tests/test_integration_third_party.py` | AUTH-1 to AUTH-4, API-1 (partial) |
| `tests/unit/services/test_instagram_sync_service.py` | MS-1 to MS-5 (TODO) |
| `tests/integration/api/test_webhooks_api.py` | WH-1 to WH-5 (TODO) |
| `tests/integration/api/test_messages_api.py` | API-2, API-3, API-5 (TODO) |
| `tests/e2e/test_chat_workflow.py` | E2E-1 to E2E-4 (TODO) |
